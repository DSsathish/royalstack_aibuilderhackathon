/** Owner dashboard API calls. Every call carries the Firebase ID token. */
import { API, ApiError, Session } from "./api";
import { authed as call } from "./authed";
import { idToken } from "./firebase";

export type Overview = { today: { orders: number; revenue: number; by_channel: Record<string, number>; avg_basket: number };
  low_stock: number; out_of_stock: number; dead_stock: number; open_drafts: number; open_flags: number; asked_not_found: number;
  series: { day: string; revenue: number }[] };
export type InvRow = { product_id: string; name: string; category: string; price: number; available: number; on_hand: number; reserved: number;
  reorder_point: number; reorder_qty: number; supplier_id: string; lead_time_days: number; avg_daily: number | null; days_of_cover: number | null;
  status: "ok" | "low" | "out" | "dead" | "overstock"; aisle: string };
export type Draft = { po_id: string; supplier_id: string; supplier_name: string; summary: string; status: string; email_text: string; reason: string;
  lines: { product_id: string; name: string; qty: number; available: number; reorder_point: number; avg_daily: number | null; reason: string }[]; created_at: string };
export type Signals = { days: number; not_carried: { query: string; count: number; source: string }[]; out_of_stock: { product_id: string; name: string; count: number; lost_sales: number }[] };
export type Loss = { summary: { total: number; clear: number; spot_check: number; flag: number; issue_confirmed: number; flag_rate: number; audit_rate: number };
  shrink: { product_id: string; name: string; system: number; counted: number; difference: number; value: number }[];
  recent: { verification_id: string; verdict: string; reasons: string[]; created_at: string; review_outcome: string | null }[];
  settings: { self_checkout_item_limit: number; high_value_threshold: number; audit_rate: number; kiosk_pin: string } };

export type Customer = { uid: string; phone_last4: string; name: string; language: string; dietary: string[]; favourite_categories: string[];
  visits: number; spend: number; points: number; segment: "new" | "regular" | "vip" | "at_risk"; last_seen: string; created_at: string };
export type OfferDoc = { offer_id: string; name: string; kind: "product" | "category" | "cart"; product_id: string; category: string; min_total: number;
  percent_off: number; amount_off: number; segment: "all" | "signed_in" | "new" | "regular" | "vip" | "at_risk"; active: boolean; starts_at: string | null; ends_at: string | null; detail: string; created_at: string };

export type StoreDoc = { store_id: string; name: string; city: string; currency: string; languages: string[]; self_checkout_item_limit: number;
  brand: { accent: string; tagline: string; greeting: string }; payments: { provider: "mock" | "razorpay"; key_id: string }; floor_map: { aisle: string }[] };

export const owner = {
  me: () => call<{ uid: string; stores: string[]; roles: Record<string, "owner" | "staff"> }>("/owner/me"),
  register: (body: { name: string; city: string; languages: string[]; currency: string }) =>
    call<{ store: StoreDoc; kiosk_pin: string }>("/owner/register", { method: "POST", body: JSON.stringify(body) }),
  store: (s: string) => call<StoreDoc>(`/stores/${s}`),
  patchStore: (s: string, body: Partial<{ name: string; city: string; tagline: string; greeting: string; accent: string; languages: string[]; currency: string; aisles: string[] }>) =>
    call<StoreDoc>(`/owner/${s}/store`, { method: "PATCH", body: JSON.stringify(body) }),
  lookup: (s: string, code: string) => call<{ found: boolean; name?: string; brand?: string; category?: string; image_url?: string }>(`/owner/${s}/lookup/${code}`),
  createProduct: (s: string, body: { barcode: string; sku?: string; name: string; brand?: string; category?: string; price: number; mrp?: number; on_hand: number; aisle?: string }) =>
    call<{ product_id: string; name: string }>(`/owner/${s}/products`, { method: "POST", body: JSON.stringify(body) }),
  team: (s: string) => call<{ owner_emails: string[]; staff_emails: string[] }>(`/owner/${s}/team`),
  verifications: (s: string, days = 7) => call<{ summary: Loss["summary"]; items: Loss["recent"] }>(`/owner/${s}/verifications?days=${days}`),
  addStaff: (s: string, email: string) => call<{ staff_emails: string[] }>(`/owner/${s}/staff`, { method: "POST", body: JSON.stringify({ email }) }),
  removeStaff: (s: string, email: string) => call<{ staff_emails: string[] }>(`/owner/${s}/staff/${encodeURIComponent(email)}`, { method: "DELETE" }),
  patchPayments: (s: string, body: { key_id?: string; key_secret?: string }) => call<{ provider: string; key_id: string }>(`/owner/${s}/payments`, { method: "PATCH", body: JSON.stringify(body) }),
  overview: (s: string) => call<Overview>(`/owner/${s}/overview`),
  inventory: (s: string) => call<InvRow[]>(`/owner/${s}/inventory`),
  patchInventory: (s: string, pid: string, body: { reorder_point?: number; reorder_qty?: number }) => call(`/owner/${s}/inventory/${pid}`, { method: "PATCH", body: JSON.stringify(body) }),
  count: (s: string, product_id: string, counted: number) => call(`/owner/${s}/counts`, { method: "POST", body: JSON.stringify({ product_id, counted }) }),
  reorders: (s: string) => call<Draft[]>(`/owner/${s}/reorders`),
  draft: (s: string) => call<Draft[]>(`/owner/${s}/reorders/draft`, { method: "POST" }),
  approve: (s: string, po: string, qty: Record<string, number>) => call<Draft>(`/owner/${s}/reorders/${po}/approve`, { method: "POST", body: JSON.stringify({ qty }) }),
  reject: (s: string, po: string, reason: string) => call<Draft>(`/owner/${s}/reorders/${po}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  customers: (s: string) => call<Customer[]>(`/owner/${s}/customers`),
  adjustPoints: (s: string, uid: string, delta: number, reason: string) => call<{ uid: string; points: number }>(`/owner/${s}/customers/${uid}/points`, { method: "POST", body: JSON.stringify({ delta, reason }) }),
  offers: (s: string) => call<OfferDoc[]>(`/owner/${s}/offers`),
  createOffer: (s: string, body: Omit<OfferDoc, "offer_id" | "detail" | "created_at" | "active" | "starts_at"> & { active?: boolean }) => call<OfferDoc>(`/owner/${s}/offers`, { method: "POST", body: JSON.stringify(body) }),
  patchOffer: (s: string, id: string, body: Partial<Pick<OfferDoc, "active" | "name" | "ends_at">>) => call<OfferDoc>(`/owner/${s}/offers/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteOffer: (s: string, id: string) => call<{ deleted: boolean }>(`/owner/${s}/offers/${id}`, { method: "DELETE" }),
  searchProducts: (s: string, q: string) => call<{ product_id: string; name: string; category: string; price: number }[]>(`/stores/${s}/search?q=${encodeURIComponent(q)}&k=6`),
  signals: (s: string, days = 7) => call<Signals>(`/owner/${s}/signals?days=${days}`),
  loss: (s: string) => call<Loss>(`/owner/${s}/loss`),
  settings: (s: string, body: Partial<Loss["settings"]>) => call(`/owner/${s}/settings`, { method: "PATCH", body: JSON.stringify(body) }),
  session: (s: string) => call<Session>(`/owner/${s}/session`, { method: "POST" }),
  qr: (s: string) => call<{ entrance_url: string; aisles: { aisle: string; url: string }[] }>(`/owner/${s}/qr`),
  propose: async (s: string, file: File) => {
    const token = await idToken();
    const form = new FormData(); form.set("file", file);
    const res = await fetch(`${API}/owner/${s}/import/propose`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
    if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
    return res.json() as Promise<{ proposal: { mapping: Record<string, string>; notes: string[]; questions: string[]; confidence: number; source: string }; header: string[]; samples: Record<string, string>[] }>;
  },
  importCsv: async (s: string, file: File, mapping: Record<string, string>) => {
    const token = await idToken();
    const form = new FormData(); form.set("file", file); form.set("mapping", JSON.stringify(mapping));
    const res = await fetch(`${API}/owner/${s}/import/csv`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
    if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
    return res.json() as Promise<{ created: number; updated: number; errors: { line: number; message: string }[] }>;
  },
};
