/** Owner dashboard API calls. Every call carries the Firebase ID token. */
import { API, ApiError, Session } from "./api";
import { authed as call } from "./authed";
import { idToken } from "./firebase";

export type Overview = { today: { orders: number; revenue: number; by_channel: Record<string, number>; avg_basket: number };
  low_stock: number; out_of_stock: number; dead_stock: number; open_drafts: number; open_flags: number; asked_not_found: number;
  series: { day: string; revenue: number }[] };
export type InvRow = { product_id: string; name: string; category: string; price: number; available: number; on_hand: number; reserved: number;
  reorder_point: number; reorder_qty: number; supplier_id: string; lead_time_days: number; avg_daily: number | null; days_of_cover: number | null;
  status: "ok" | "low" | "out" | "dead" | "overstock"; aisle: string;
  sku: string; barcode: string; brand: string; mrp: number; unit: string; pack_size: string; bay: number | null; shelf: number | null; side: "left" | "right" | null };
/** Product details and edits (docs/lld/owner-product-edit.md). */
export type ProductFull = { product_id: string; sku: string; barcode: string; name: string; brand: string; category: string; subcategory: string; description: string;
  price: number; mrp: number; unit: string; image_url: string; tags: string[]; status: "active" | "inactive" | "discontinued" | "seasonal"; pack_size: string;
  cost_price: number | null; gst_rate: number | null; shelf_life_days: number | null; origin: string; available: number;
  location: { aisle: string; bay: number; shelf: number; side: "left" | "right" } | null };
export type StockDoc = { on_hand?: number; reserved?: number; reorder_point?: number; reorder_qty?: number; lead_time_days?: number; supplier_id?: string };
export type ProductDetail = { product: ProductFull; stock: StockDoc };
export type ProductEdit = Partial<{ name: string; brand: string; category: string; subcategory: string; description: string; barcode: string; price: number; mrp: number;
  cost_price: number; gst_rate: number; unit: string; pack_size: string; shelf_life_days: number; status: ProductFull["status"]; origin: string; tags: string[]; image_url: string;
  on_hand: number; reorder_point: number; reorder_qty: number; lead_time_days: number; supplier_id: string; aisle: string; bay: number; shelf: number; side: "left" | "right" }>;
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

export type SyncView = {
  settings: { webhook_url: string; feed_url: string; feed_mapping: Record<string, string>; feed_every_min: number; last_pull_at: string | null; has_secret: boolean; catalog_version: number };
  endpoints: { inventory: string; products: string; pull: string };
  log: { at: string; direction: "in" | "out"; kind: string; rows: number; changed: number; ok: boolean; error?: string; unknown?: string[]; errors?: number }[];
  outbox: { pending: number; dead: number } };

export type StoreDoc = { store_id: string; name: string; city: string; currency: string; languages: string[]; self_checkout_item_limit: number;
  brand: { accent: string; tagline: string; greeting: string }; payments: { provider: "mock" | "razorpay"; key_id: string }; floor_map: { aisle: string; x: number; y: number; w: number; h: number; floor?: number; kind?: "aisle" | "chiller" | "freezer" | "counter" }[] };

export const owner = {
  me: () => call<{ uid: string; stores: string[]; roles: Record<string, "owner" | "staff"> }>("/owner/me"),
  register: (body: { name: string; city: string; languages: string[]; currency: string }) =>
    call<{ store: StoreDoc; kiosk_pin: string }>("/owner/register", { method: "POST", body: JSON.stringify(body) }),
  store: (s: string) => call<StoreDoc>(`/stores/${s}`),
  patchStore: (s: string, body: Partial<{ name: string; city: string; tagline: string; greeting: string; accent: string; languages: string[]; currency: string; aisles: string[]; floor_map: { aisle: string; x: number; y: number; w: number; h: number; floor?: number; kind?: "aisle" | "chiller" | "freezer" | "counter" }[] }>) =>
    call<StoreDoc>(`/owner/${s}/store`, { method: "PATCH", body: JSON.stringify(body) }),
  setLocation: (s: string, pid: string, body: { aisle: string; bay?: number; shelf?: number; side?: "left" | "right" }) =>
    call<{ aisle: string; bay: number }>(`/owner/${s}/products/${pid}/location`, { method: "PATCH", body: JSON.stringify(body) }),
  lookup: (s: string, code: string) => call<{ found: boolean; name?: string; brand?: string; category?: string; image_url?: string }>(`/owner/${s}/lookup/${code}`),
  inventorySchema: (s: string) => call<{ fields: InventoryField[]; sheet_template_url: string }>(`/owner/${s}/inventory/schema`),
  downloadTemplate: async (s: string) => {
    const token = await idToken();
    const res = await fetch(`${API}/owner/${s}/inventory/template.xlsx`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    if (!res.ok) throw new ApiError(res.status, res.statusText);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a"); a.href = url; a.download = "inventory-template.xlsx"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  },
  uploadInventory: (s: string, file: File, opts: { apply: boolean; allow_updates: boolean }) => {
    const form = new FormData(); form.set("file", file); form.set("apply", String(opts.apply)); form.set("allow_updates", String(opts.allow_updates));
    return multipart<UploadCheck>(`/owner/${s}/inventory/upload`, form);
  },
  createProduct: (s: string, body: { barcode?: string; sku?: string; name: string; brand?: string; category?: string; subcategory?: string; price: number; mrp?: number; unit?: string; pack_size?: string; on_hand: number; reorder_point?: number; reorder_qty?: number; aisle?: string }) =>
    call<{ product_id: string; name: string }>(`/owner/${s}/products`, { method: "POST", body: JSON.stringify(body) }),
  team: (s: string) => call<{ owner_emails: string[]; staff_emails: string[] }>(`/owner/${s}/team`),
  verifications: (s: string, days = 7) => call<{ summary: Loss["summary"]; items: Loss["recent"] }>(`/owner/${s}/verifications?days=${days}`),
  addStaff: (s: string, email: string) => call<{ staff_emails: string[] }>(`/owner/${s}/staff`, { method: "POST", body: JSON.stringify({ email }) }),
  removeStaff: (s: string, email: string) => call<{ staff_emails: string[] }>(`/owner/${s}/staff/${encodeURIComponent(email)}`, { method: "DELETE" }),
  patchPayments: (s: string, body: { key_id?: string; key_secret?: string }) => call<{ provider: string; key_id: string }>(`/owner/${s}/payments`, { method: "PATCH", body: JSON.stringify(body) }),
  overview: (s: string) => call<Overview>(`/owner/${s}/overview`),
  inventory: (s: string) => call<InvRow[]>(`/owner/${s}/inventory`),
  product: (s: string, pid: string) => call<ProductDetail>(`/owner/${s}/products/${pid}`),
  patchProduct: (s: string, pid: string, body: ProductEdit) => call<ProductDetail>(`/owner/${s}/products/${pid}`, { method: "PATCH", body: JSON.stringify(body) }),
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
  sync: (s: string) => call<SyncView>(`/owner/${s}/sync`),
  patchSync: (s: string, body: Partial<{ webhook_url: string; feed_url: string; feed_mapping: Record<string, string>; feed_every_min: number }>) => call<SyncView>(`/owner/${s}/sync`, { method: "PATCH", body: JSON.stringify(body) }),
  rotateSyncSecret: (s: string) => call<{ secret: string }>(`/owner/${s}/sync/secret`, { method: "POST" }),
  pullNow: (s: string) => call<Record<string, unknown>>(`/owner/${s}/sync/pull`, { method: "POST" }),
  testWebhook: (s: string) => call<{ ok: boolean; error?: string }>(`/owner/${s}/sync/test`, { method: "POST" }),
  searchProducts: (s: string, q: string) => call<{ product_id: string; name: string; category: string; price: number }[]>(`/stores/${s}/search?q=${encodeURIComponent(q)}&k=6`),
  signals: (s: string, days = 7) => call<Signals>(`/owner/${s}/signals?days=${days}`),
  loss: (s: string) => call<Loss>(`/owner/${s}/loss`),
  settings: (s: string, body: Partial<Loss["settings"]>) => call(`/owner/${s}/settings`, { method: "PATCH", body: JSON.stringify(body) }),
  session: (s: string) => call<Session>(`/owner/${s}/session`, { method: "POST" }),
  qr: (s: string) => call<{ entrance_url: string; aisles: { aisle: string; url: string }[] }>(`/owner/${s}/qr`),
  connectors: (s: string) => call<{ connectors: ConnectorDoc[] }>(`/owner/${s}/connectors`),
  inspectSource: (s: string, src: SourceInput, mapping?: Record<string, string>) => {
    const form = sourceForm(src); if (mapping) form.set("mapping", JSON.stringify(mapping));
    return multipart<Inspection>(`/owner/${s}/connectors/inspect`, form);
  },
  applySource: (s: string, src: SourceInput, mapping: Record<string, string>, opts: { label: string; save: boolean; every_min: number }) => {
    const form = sourceForm(src); form.set("mapping", JSON.stringify(mapping)); form.set("label", opts.label); form.set("save", String(opts.save)); form.set("every_min", String(opts.every_min));
    return multipart<{ result: ApplyResult; connector: ConnectorDoc | null }>(`/owner/${s}/connectors/apply`, form);
  },
  mcpTools: (s: string, url: string, auth: string) => call<McpTools>(`/owner/${s}/connectors/mcp/tools`, { method: "POST", body: JSON.stringify({ url, auth }) }),
  discoverTables: (s: string, dsn: string) => call<{ tables: string[] }>(`/owner/${s}/connectors/discover`, { method: "POST", body: JSON.stringify({ dsn }) }),
  runConnector: (s: string, cid: string) => call<Record<string, unknown>>(`/owner/${s}/connectors/${cid}/run`, { method: "POST" }),
  removeConnector: (s: string, cid: string) => call<{ ok: boolean }>(`/owner/${s}/connectors/${cid}`, { method: "DELETE" }),
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

/** Connector agent: a source the owner brings in (docs/lld/connector-agent.md). */
export type SourceInput = { kind: "file" | "sheet" | "api" | "db" | "mcp"; file?: File | null; url?: string; auth?: string; dsn?: string; table?: string; compare?: boolean; compare_tool?: string };
export type McpTools = { server: { name?: string; version?: string }; instructions: string; tools: { name: string; description: string }[] };
export type Inspection = {
  kind: string; columns: string[]; samples: Record<string, string>[]; row_count: number; mapping: Record<string, string>;
  proposal: { notes: string[]; questions: string[]; confidence: number; source: string } | null;
  preview: { adds: number; updates: number; restocks: number; unchanged: number; errors: number; error_samples: { line: number; message: string }[]; changes: { kind: string; sku: string; note: string }[] } | null;
  problem: string;
};
export type ApplyResult = { created: number; updated: number; errors: number; rows: number; source: string; error_samples: { line: number; message: string }[] };
export type ConnectorDoc = { connector_id: string; kind: string; label: string; url: string; table: string; mapping: Record<string, string>; every_min: number; enabled: boolean; compare?: boolean; last_run_at: string | null; last_result: Record<string, unknown> };

function sourceForm(src: SourceInput): FormData {
  const form = new FormData(); form.set("kind", src.kind);
  if (src.file) form.set("file", src.file);
  for (const k of ["url", "auth", "dsn", "table", "compare_tool"] as const) if (src[k]) form.set(k, src[k]!);
  if (src.compare) form.set("compare", "true");
  return form;
}
async function multipart<T>(path: string, form: FormData): Promise<T> {
  const token = await idToken();
  const res = await fetch(`${API}${path}`, { method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form });
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
  return res.json() as Promise<T>;
}

/** Inventory intake (docs/lld/inventory-intake.md): one field table for the template, the upload check and the form. */
export type InventoryField = { name: string; required: boolean; kind: "text" | "number" | "integer"; description: string; example: string; choices: string[] };
export type UploadCheck = {
  ok: boolean; columns: string[]; missing_required: string[]; unknown: string[]; row_count: number;
  errors: { line: number; message: string }[]; error_count: number; duplicates: { line: number; sku: string; first_line: number }[];
  preview: { adds: number; updates: number; restocks: number; unchanged: number; errors: number; changes: { kind: string; sku: string; note: string }[] } | null;
  result: { created: number; updated: number; skipped: number; errors: number; duplicates: number; file: string } | null;
};
