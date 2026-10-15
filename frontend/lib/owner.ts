/** Owner dashboard API calls. Every call carries the Firebase ID token. */
import { API, ApiError, Session } from "./api";
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

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await idToken();
  const res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
  return res.json();
}

export const owner = {
  me: () => call<{ uid: string; stores: string[] }>("/owner/me"),
  overview: (s: string) => call<Overview>(`/owner/${s}/overview`),
  inventory: (s: string) => call<InvRow[]>(`/owner/${s}/inventory`),
  patchInventory: (s: string, pid: string, body: { reorder_point?: number; reorder_qty?: number }) => call(`/owner/${s}/inventory/${pid}`, { method: "PATCH", body: JSON.stringify(body) }),
  count: (s: string, product_id: string, counted: number) => call(`/owner/${s}/counts`, { method: "POST", body: JSON.stringify({ product_id, counted }) }),
  reorders: (s: string) => call<Draft[]>(`/owner/${s}/reorders`),
  draft: (s: string) => call<Draft[]>(`/owner/${s}/reorders/draft`, { method: "POST" }),
  approve: (s: string, po: string, qty: Record<string, number>) => call<Draft>(`/owner/${s}/reorders/${po}/approve`, { method: "POST", body: JSON.stringify({ qty }) }),
  reject: (s: string, po: string, reason: string) => call<Draft>(`/owner/${s}/reorders/${po}/reject`, { method: "POST", body: JSON.stringify({ reason }) }),
  signals: (s: string, days = 7) => call<Signals>(`/owner/${s}/signals?days=${days}`),
  loss: (s: string) => call<Loss>(`/owner/${s}/loss`),
  settings: (s: string, body: Partial<Loss["settings"]>) => call(`/owner/${s}/settings`, { method: "PATCH", body: JSON.stringify(body) }),
  session: (s: string) => call<Session>(`/owner/${s}/session`, { method: "POST" }),
  qr: (s: string) => call<{ entrance_url: string; aisles: { aisle: string; url: string }[] }>(`/owner/${s}/qr`),
  importCsv: async (s: string, file: File, mapping: Record<string, string>) => {
    const token = await idToken();
    const form = new FormData(); form.set("file", file); form.set("mapping", JSON.stringify(mapping));
    const res = await fetch(`${API}/owner/${s}/import/csv`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
    if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
    return res.json() as Promise<{ created: number; updated: number; errors: { line: number; message: string }[] }>;
  },
};
