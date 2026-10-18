/** Typed calls to the retail API. The session id in localStorage is the shopper's credential. */

import { readSse, UiEvent } from "./sse";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
const SESSION_KEY = "rs.session";

export type Session = {
  session_id: string; store_id: string; mode: "instore" | "online" | "owner";
  cart_id: string; aisle_hint: string | null; language: string; customer_id?: string | null;
};
export type BlockKind = "aisle" | "chiller" | "freezer" | "counter";
export type Aisle = { aisle: string; x: number; y: number; w: number; h: number; floor?: number; kind?: BlockKind; label?: string };
export type Store = { store_id: string; name: string; currency: string; languages: string[];
  self_checkout_item_limit: number; floor_map: Aisle[]; brand?: { accent: string; tagline: string; greeting: string }; city?: string };
export type Location = { aisle: string; bay: number; shelf: number; side: string; x: number; y: number };
export type Product = { product_id: string; name: string; brand: string; price: number; mrp: number;
  unit: string; available: number; aisle?: string; bay?: number; image_url?: string; location?: Location | null;
  substitutes?: string[]; barcode?: string; category?: string; subcategory?: string; description?: string; pack_size?: string; tags?: string[];
  bought_30d?: number; status?: string; aisle_label?: string };
export type StoreLite = { store_id: string; name: string; city: string; tagline: string };
export type HomeData = { categories: { name: string; count: number }[]; trending: Product[]; recommended: Product[]; deals: (Offer & { products: Product[] })[]; segment: string };
export type CompareRow = { provider: string; label: string; demo: boolean; status: "ok" | "unavailable" | "no_match"; name?: string; price?: number; mrp?: number; available?: number | null; note?: string; fetched_at?: string };
export type Facts = { ok: boolean; summary?: string; sources?: { title: string; url: string }[]; note?: string; error?: string; cached?: boolean;
  label?: { ingredients?: string | null; allergens?: string[]; nutrition_per_100g?: Record<string, number> | null; nutriscore?: string | null } | null };
export type CartItem = { product_id: string; name: string; qty: number; unit_price: number; mrp: number; via: string };
export type DiscountLine = { offer_id: string; name: string; amount: number };
export type CartView = { cart_id: string; items: CartItem[]; count: number; subtotal: number; savings: number; total: number; status: string;
  discounts: DiscountLine[]; discount_total: number; points_redeemed: number; points_value: number; points_balance: number | null; segment: string };
export type Offer = { offer_id: string; name: string; kind: string; detail: string; segment: string; ends_at: string | null };
export type Verification = { verification_id: string; verdict: "clear" | "spot_check" | "flag"; reasons: string[];
  layers: { receipt_ok: boolean; order_ok: boolean; count_ok: boolean | null; limit_ok: boolean; high_value: string[]; random_audit: boolean };
  vision: { confidence: number; unexpected_items: string[]; skipped: boolean } | null;
  order_summary: { items: { name: string; qty: number }[]; total: number; paid_at: string | null } | null };
export type Order = { order_id: string; items: CartItem[]; subtotal: number; savings: number; total: number;
  discounts: DiscountLine[]; discount_total: number; points_redeemed: number; points_value: number; points_earned: number;
  status: string; receipt_token: string; paid_at: string | null; created_at: string };

export function entranceParams(search: string): { store: string; token: string; aisle?: string } | null {
  const p = new URLSearchParams(search);
  const store = p.get("store");
  const token = p.get("t");
  return store && token ? { store, token, aisle: p.get("aisle") ?? undefined } : null;
}

export function money(n: number): string {
  return "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function loadSession(): Session | null {
  try { const raw = localStorage.getItem(SESSION_KEY); return raw ? JSON.parse(raw) : null; } catch { return null; }
}
export function saveSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(SESSION_KEY, JSON.stringify(s));
    else localStorage.removeItem(SESSION_KEY);
  } catch {}
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new ApiError(res.status, String(detail));
  }
  return res.json();
}
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
async function toError(res: Response): Promise<ApiError> {
  let detail = res.statusText;
  try { detail = (await res.json()).detail ?? detail; } catch {}
  return new ApiError(res.status, String(detail));
}

const h = (session?: Session) => ({ "Content-Type": "application/json", ...(session ? { "X-Session-Id": session.session_id } : {}) });

export const api = {
  enterStore: (store_id: string, token: string, aisle?: string) =>
    fetch(`${API}/sessions/instore`, { method: "POST", headers: h(), body: JSON.stringify({ store_id, token, aisle }) }).then(json<Session>),
  onlineSession: (store_id: string) =>
    fetch(`${API}/sessions`, { method: "POST", headers: h(), body: JSON.stringify({ store_id, mode: "online" }) }).then(json<Session>),
  setAisle: (s: Session, aisle_hint: string) =>
    fetch(`${API}/sessions/${s.session_id}`, { method: "PATCH", headers: h(), body: JSON.stringify({ aisle_hint }) }).then(json<Session>),
  store: (store_id: string) => fetch(`${API}/stores/${store_id}`).then(json<Store>),
  product: (store_id: string, product_id: string) => fetch(`${API}/stores/${store_id}/products/${product_id}`).then(json<Product>),
  byBarcode: (store_id: string, code: string) => fetch(`${API}/stores/${store_id}/products/by-barcode/${code}`).then(json<Product>),
  cart: (s: Session) => fetch(`${API}/carts/${s.cart_id}`, { headers: h(s) }).then(json<CartView>),
  addItem: (s: Session, product_id: string, qty: number, via: "scan" | "vision" | "chat") =>
    fetch(`${API}/carts/${s.cart_id}/items`, { method: "POST", headers: h(s), body: JSON.stringify({ product_id, qty, via }) }).then(json<CartView>),
  removeItem: (s: Session, product_id: string) =>
    fetch(`${API}/carts/${s.cart_id}/items/${product_id}`, { method: "DELETE", headers: h(s) }).then(json<CartView>),
  offers: (store_id: string, s?: Session) => fetch(`${API}/stores/${store_id}/offers`, { headers: h(s) }).then(json<Offer[]>),
  /** Online shop (docs/lld/online-shop.md). */
  stores: () => fetch(`${API}/stores`).then(json<StoreLite[]>),
  home: (store_id: string, s?: Session) => fetch(`${API}/stores/${store_id}/home`, { headers: h(s) }).then(json<HomeData>),
  products: (store_id: string, opts: { category?: string; q?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams(Object.entries(opts).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return fetch(`${API}/stores/${store_id}/products?${qs}`).then(json<{ products: Product[]; total: number; more: boolean; section?: string | null }>);
  },
  facts: (s: Session, product_id: string, language = "auto") =>
    fetch(`${API}/stores/${s.store_id}/products/${product_id}/facts?language=${encodeURIComponent(language)}`, { headers: h(s) }).then(json<Facts>),
  compare: (s: Session, product_id: string) => fetch(`${API}/stores/${s.store_id}/products/${product_id}/compare`, { headers: h(s) }).then(json<CompareRow[]>),
  setQty: (s: Session, product_id: string, qty: number) =>
    fetch(`${API}/carts/${s.cart_id}/items/${product_id}`, { method: "PATCH", headers: h(s), body: JSON.stringify({ qty }) }).then(json<CartView>),
  /** `points` needs a token from a phone verification done in the last ten minutes. */
  checkoutIntent: (s: Session, points = 0, token?: string) =>
    fetch(`${API}/checkout/intent`, { method: "POST", headers: { ...h(), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ session_id: s.session_id, points }) })
      .then(json<{ order_id: string; amount: number; provider: "mock" | "razorpay"; razorpay_key_id?: string; razorpay_order_id?: string; discount_total: number; points_redeemed: number }>),
  checkoutConfirm: (s: Session, order_id: string, payment_id: string, signature: string) =>
    fetch(`${API}/checkout/confirm`, { method: "POST", headers: h(), body: JSON.stringify({ order_id, payment_id, signature, session_id: s.session_id }) }).then(json<Order>),
  order: (s: Session, order_id: string) => fetch(`${API}/orders/${order_id}`, { headers: h(s) }).then(json<Order>),

  exitVerify: (store_id: string, pin: string, receipt_token: string, kiosk_id: string, image?: Blob) => {
    const form = new FormData();
    form.set("receipt_token", receipt_token); form.set("kiosk_id", kiosk_id);
    if (image) form.set("image", image, "bag.jpg");
    return fetch(`${API}/exit/${store_id}/verify`, { method: "POST", headers: { "X-Kiosk-Pin": pin }, body: form }).then(json<Verification>);
  },
  exitReview: (store_id: string, pin: string, verification_id: string, outcome: "cleared" | "issue_confirmed", note = "") =>
    fetch(`${API}/exit/${store_id}/review/${verification_id}`, { method: "POST", headers: { "Content-Type": "application/json", "X-Kiosk-Pin": pin },
      body: JSON.stringify({ outcome, note }) }).then(json<Verification>),

  async *chat(s: Session, message: string, image?: Blob, language = "auto"): AsyncGenerator<UiEvent> {
    const form = new FormData();
    form.set("session_id", s.session_id);
    form.set("message", message);
    form.set("language", language);            // the language picked in the app; "auto" follows the latest message
    if (image) form.set("image", image, "photo.jpg");
    const res = await fetch(`${API}/agent/chat`, { method: "POST", body: form });
    if (!res.ok || !res.body) throw await toError(res);
    yield* readSse(res.body);
  },
  async *audio(s: Session, audio: Blob, language = "auto"): AsyncGenerator<UiEvent> {
    const form = new FormData();
    form.set("session_id", s.session_id);
    form.set("audio", audio, "voice.webm");
    form.set("language", language);            // the transcript stays in the spoken script; this is only a hint
    const res = await fetch(`${API}/agent/audio`, { method: "POST", body: form });
    if (!res.ok || !res.body) throw await toError(res);
    yield* readSse(res.body);
  },
};
