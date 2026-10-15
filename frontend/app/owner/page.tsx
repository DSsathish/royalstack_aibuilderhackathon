"use client";
import { useEffect, useState } from "react";
import type { User } from "firebase/auth";
import { money } from "@/lib/api";
import { signInWithGoogle, signOutOwner, watchUser } from "@/lib/firebase";
import { Draft, InvRow, Loss, Overview, Signals, owner } from "@/lib/owner";
import { useApp } from "@/lib/store";
import Chat from "@/components/Chat";
import RevenueChart from "@/components/RevenueChart";

type Tab = "overview" | "inventory" | "reorders" | "signals" | "loss" | "connectors" | "chat";
const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" }, { id: "inventory", label: "Inventory" }, { id: "reorders", label: "Reorders" },
  { id: "signals", label: "Signals" }, { id: "loss", label: "Loss" }, { id: "connectors", label: "Connectors" }, { id: "chat", label: "Ask" },
];

export default function OwnerPage() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [stores, setStores] = useState<string[]>([]);
  const [store, setStore] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");

  useEffect(() => watchUser(setUser), []);
  useEffect(() => {
    if (!user) return;
    owner.me().then((m) => { setStores(m.stores); setStore(m.stores[0] ?? ""); }).catch((e) => setError(e.message));
  }, [user]);

  if (user === undefined) return <main className="p-6 text-zinc-500">Loading…</main>;
  if (!user) return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-bold">Store owner dashboard</h1>
      <p className="text-zinc-500 max-w-sm">Sign in with the Google account registered for your store.</p>
      <button onClick={() => signInWithGoogle().catch((e) => setError(e.message))} className="rounded-lg bg-emerald-600 text-white px-5 py-2 font-semibold">Sign in with Google</button>
      {error && <p className="text-sm text-red-600 max-w-sm">{error.includes("operation-not-allowed") ? "Google sign-in is not enabled yet in the Firebase console (Authentication → Sign-in method → Google)." : error}</p>}
    </main>
  );
  if (!store) return <main className="p-6 text-zinc-500">{error || `No store is registered for ${user.email}. Ask the administrator to add your email to the store.`}</main>;

  return (
    <div className="flex flex-col h-dvh">
      <header className="flex items-center gap-3 px-4 py-2 border-b border-zinc-200 dark:border-zinc-800">
        <img src="/icon.svg" alt="" className="w-7 h-7" />
        <div className="font-semibold">Owner</div>
        {stores.length > 1 ? <select value={store} onChange={(e) => setStore(e.target.value)} className="text-sm bg-transparent border rounded px-1">{stores.map((s) => <option key={s}>{s}</option>)}</select> : <span className="text-sm text-zinc-500">{store}</span>}
        <span className="flex-1" />
        <span className="text-xs text-zinc-500 hidden sm:inline">{user.email}</span>
        <button onClick={() => signOutOwner()} className="text-xs underline">Sign out</button>
      </header>
      <nav className="flex overflow-x-auto border-b border-zinc-200 dark:border-zinc-800 text-sm">
        {TABS.map((t) => <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2 whitespace-nowrap ${tab === t.id ? "border-b-2 border-emerald-600 font-semibold" : "text-zinc-500"}`}>{t.label}</button>)}
      </nav>
      <div className="flex-1 overflow-y-auto">
        {tab === "overview" && <OverviewTab store={store} />}
        {tab === "inventory" && <InventoryTab store={store} />}
        {tab === "reorders" && <ReordersTab store={store} />}
        {tab === "signals" && <SignalsTab store={store} />}
        {tab === "loss" && <LossTab store={store} />}
        {tab === "connectors" && <ConnectorsTab store={store} />}
        {tab === "chat" && <OwnerChat store={store} />}
      </div>
    </div>
  );
}

function Tile({ label, value, tone = "" }: { label: string; value: string | number; tone?: string }) {
  return <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-3"><div className="text-xs text-zinc-500">{label}</div><div className={`text-xl font-bold ${tone}`}>{value}</div></div>;
}

function OverviewTab({ store }: { store: string }) {
  const [o, setO] = useState<Overview | null>(null);
  useEffect(() => { owner.overview(store).then(setO); const t = setInterval(() => owner.overview(store).then(setO), 15000); return () => clearInterval(t); }, [store]);
  if (!o) return <p className="p-4 text-zinc-500">Loading…</p>;
  return (
    <div className="p-4 space-y-4 max-w-4xl">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Today's revenue" value={money(o.today.revenue)} />
        <Tile label="Orders today" value={o.today.orders} />
        <Tile label="Avg basket" value={money(o.today.avg_basket)} />
        <Tile label="Asked, not found (today)" value={o.asked_not_found} tone="text-amber-600" />
        <Tile label="Low stock" value={o.low_stock} tone={o.low_stock ? "text-amber-600" : ""} />
        <Tile label="Out of stock" value={o.out_of_stock} tone={o.out_of_stock ? "text-red-600" : ""} />
        <Tile label="Reorder drafts waiting" value={o.open_drafts} />
        <Tile label="Exit flags open" value={o.open_flags} tone={o.open_flags ? "text-red-600" : ""} />
      </div>
      <RevenueChart series={o.series} />
      <div className="text-sm text-zinc-500">By channel today: {Object.entries(o.today.by_channel).map(([k, v]) => `${k} ${money(v)}`).join(" · ") || "no sales yet"}</div>
    </div>
  );
}

function InventoryTab({ store }: { store: string }) {
  const [rows, setRows] = useState<InvRow[]>([]);
  const [filter, setFilter] = useState<"all" | InvRow["status"]>("all");
  const [q, setQ] = useState("");
  const load = () => owner.inventory(store).then(setRows);
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  const shown = rows.filter((r) => (filter === "all" || r.status === filter) && r.name.toLowerCase().includes(q.toLowerCase()));
  const badge: Record<string, string> = { ok: "bg-zinc-100 text-zinc-600", low: "bg-amber-100 text-amber-800", out: "bg-red-100 text-red-800", dead: "bg-purple-100 text-purple-800", overstock: "bg-blue-100 text-blue-800" };
  async function edit(r: InvRow, field: "reorder_point" | "reorder_qty") {
    const v = window.prompt?.(`${field.replace("_", " ")} for ${r.name}`, String(r[field]));
    if (v && /^\d+$/.test(v)) { await owner.patchInventory(store, r.product_id, { [field]: Number(v) }); load(); }
  }
  async function count(r: InvRow) {
    const v = window.prompt?.(`Counted on shelf for ${r.name} (system says ${r.on_hand})`);
    if (v && /^\d+$/.test(v)) { await owner.count(store, r.product_id, Number(v)); alert?.("Count recorded. See Loss tab for discrepancies."); }
  }
  return (
    <div className="p-4 space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        {(["all", "low", "out", "dead", "overstock", "ok"] as const).map((f) => <button key={f} onClick={() => setFilter(f)} className={`rounded-full px-3 py-1 text-xs border ${filter === f ? "bg-emerald-600 text-white border-emerald-600" : ""}`}>{f}</button>)}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="ml-auto rounded-lg border px-3 py-1 text-sm bg-transparent" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-zinc-500"><tr><th className="py-1">Product</th><th>Status</th><th className="text-right">Available</th><th className="text-right">Avg/day</th><th className="text-right">Days cover</th><th className="text-right">Reorder pt</th><th className="text-right">Reorder qty</th><th>Aisle</th><th></th></tr></thead>
          <tbody>{shown.map((r) => (
            <tr key={r.product_id} className="border-t border-zinc-100 dark:border-zinc-800">
              <td className="py-1.5">{r.name}</td>
              <td><span className={`rounded-full px-2 py-0.5 text-xs ${badge[r.status]}`}>{r.status}</span></td>
              <td className="text-right">{r.available}</td><td className="text-right">{r.avg_daily ?? "–"}</td><td className="text-right">{r.days_of_cover ?? "–"}</td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_point")} className="underline decoration-dotted">{r.reorder_point}</button></td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_qty")} className="underline decoration-dotted">{r.reorder_qty}</button></td>
              <td>{r.aisle}</td>
              <td><button onClick={() => count(r)} className="text-xs text-zinc-500 underline">count</button></td>
            </tr>))}</tbody>
        </table>
      </div>
    </div>
  );
}

function ReordersTab({ store }: { store: string }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const load = () => owner.reorders(store).then(setDrafts);
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function makeDrafts() { setBusy(true); try { await owner.draft(store); await load(); } finally { setBusy(false); } }
  return (
    <div className="p-4 space-y-3 max-w-4xl">
      <div className="flex items-center gap-3">
        <button onClick={makeDrafts} disabled={busy} className="rounded-lg bg-emerald-600 disabled:bg-zinc-300 text-white px-4 py-2 text-sm font-semibold">{busy ? "Drafting with Gemini…" : "Draft reorders now"}</button>
        <span className="text-xs text-zinc-500">Nothing is sent to a supplier until you approve.</span>
      </div>
      {drafts.length === 0 && <p className="text-zinc-500 text-sm">No drafts yet.</p>}
      {drafts.map((d) => (
        <div key={d.po_id} className={`rounded-xl border p-3 space-y-2 ${d.status === "draft" ? "border-amber-300" : "border-zinc-200 dark:border-zinc-700"}`}>
          <div className="flex items-center gap-2">
            <div className="font-semibold">{d.supplier_name}</div>
            <span className={`text-xs rounded-full px-2 py-0.5 ${d.status === "approved" ? "bg-emerald-100 text-emerald-800" : d.status === "rejected" ? "bg-zinc-200 text-zinc-600" : "bg-amber-100 text-amber-800"}`}>{d.status}</span>
            <span className="text-xs text-zinc-500">{d.lines.length} lines · {new Date(d.created_at).toLocaleString()}</span>
          </div>
          <p className="text-sm italic text-zinc-600 dark:text-zinc-300">{d.summary}</p>
          <ul className="text-sm space-y-1">{d.lines.map((l) => <li key={l.product_id}><b>{l.name}</b> × {l.qty} <span className="text-zinc-500">· {l.available} left, reorder point {l.reorder_point}{l.avg_daily ? `, ${l.avg_daily}/day` : ""}</span><div className="text-xs text-zinc-500">{l.reason}</div></li>)}</ul>
          {d.status === "draft" && (
            <div className="flex gap-2">
              <button onClick={async () => { await owner.approve(store, d.po_id, {}); load(); }} className="rounded-lg bg-emerald-600 text-white px-3 py-1.5 text-sm">Approve</button>
              <button onClick={async () => { const r = window.prompt?.("Reason") ?? ""; await owner.reject(store, d.po_id, r); load(); }} className="rounded-lg border px-3 py-1.5 text-sm">Reject</button>
            </div>
          )}
          {d.status === "approved" && <button onClick={() => setOpen(open === d.po_id ? null : d.po_id)} className="text-xs underline">{open === d.po_id ? "Hide" : "Show"} supplier email</button>}
          {open === d.po_id && <pre className="text-xs whitespace-pre-wrap bg-zinc-50 dark:bg-zinc-900 rounded p-2">{d.email_text}</pre>}
        </div>
      ))}
    </div>
  );
}

function SignalsTab({ store }: { store: string }) {
  const [s, setS] = useState<Signals | null>(null);
  const [days, setDays] = useState(7);
  useEffect(() => { owner.signals(store, days).then(setS); }, [store, days]);
  if (!s) return <p className="p-4 text-zinc-500">Loading…</p>;
  return (
    <div className="p-4 space-y-4 max-w-3xl">
      <div className="flex gap-2 text-xs">{[1, 7, 30].map((d) => <button key={d} onClick={() => setDays(d)} className={`rounded-full px-3 py-1 border ${days === d ? "bg-emerald-600 text-white border-emerald-600" : ""}`}>{d === 1 ? "Today" : `${d} days`}</button>)}</div>
      <section>
        <h2 className="font-semibold">Asked for, but we don&apos;t carry it</h2>
        <p className="text-xs text-zinc-500 mb-2">Captured from shopper conversations. The assistant records these itself.</p>
        {s.not_carried.length === 0 ? <p className="text-sm text-zinc-500">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.not_carried.map((r) => <li key={r.query} className="flex justify-between border-t border-zinc-100 dark:border-zinc-800 py-1"><span>{r.query} {r.source === "agent" && <span className="text-xs text-emerald-600">· assistant</span>}</span><b>{r.count}×</b></li>)}</ul>}
      </section>
      <section>
        <h2 className="font-semibold">Asked for, but out of stock</h2>
        {s.out_of_stock.length === 0 ? <p className="text-sm text-zinc-500">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.out_of_stock.map((r) => <li key={r.product_id} className="flex justify-between border-t border-zinc-100 dark:border-zinc-800 py-1"><span>{r.name}</span><span>{r.count}× · est. lost {money(r.lost_sales)}</span></li>)}</ul>}
      </section>
    </div>
  );
}

function LossTab({ store }: { store: string }) {
  const [l, setL] = useState<Loss | null>(null);
  const [form, setForm] = useState<Partial<Loss["settings"]>>({});
  const load = () => owner.loss(store).then((x) => { setL(x); setForm(x.settings); });
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!l) return <p className="p-4 text-zinc-500">Loading…</p>;
  const s = l.summary;
  return (
    <div className="p-4 space-y-4 max-w-3xl">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Exits (7d)" value={s.total} /><Tile label="Clear" value={s.clear} /><Tile label="Spot checks" value={s.spot_check} tone="text-amber-600" /><Tile label="Flags" value={s.flag} tone="text-red-600" />
        <Tile label="Flag rate" value={`${Math.round(s.flag_rate * 100)}%`} /><Tile label="Issues confirmed" value={s.issue_confirmed} /><Tile label="Random audits" value={`${Math.round(s.audit_rate * 100)}%`} />
      </div>
      <section>
        <h2 className="font-semibold">Shrink candidates (shelf count vs system)</h2>
        {l.shrink.length === 0 ? <p className="text-sm text-zinc-500">No discrepancies. Use &quot;count&quot; on the Inventory tab to record shelf counts.</p> :
          <ul className="text-sm">{l.shrink.map((r) => <li key={r.product_id} className="flex justify-between border-t border-zinc-100 dark:border-zinc-800 py-1"><span>{r.name}</span><span>{r.counted} counted vs {r.system} · <b>{r.difference > 0 ? "+" : ""}{r.difference}</b> · {money(r.value)}</span></li>)}</ul>}
      </section>
      <section>
        <h2 className="font-semibold">Recent exits</h2>
        <ul className="text-sm">{l.recent.slice(0, 10).map((v) => <li key={v.verification_id} className="border-t border-zinc-100 dark:border-zinc-800 py-1"><span className={v.verdict === "flag" ? "text-red-600" : v.verdict === "spot_check" ? "text-amber-600" : "text-emerald-600"}>{v.verdict}</span> · {new Date(v.created_at).toLocaleTimeString()} {v.reasons.length > 0 && <span className="text-zinc-500">· {v.reasons.join("; ")}</span>}{v.review_outcome && <span className="text-xs"> · {v.review_outcome}</span>}</li>)}</ul>
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Controls</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label>Self-checkout item limit<input type="number" value={form.self_checkout_item_limit ?? ""} onChange={(e) => setForm({ ...form, self_checkout_item_limit: Number(e.target.value) })} className="w-full rounded border px-2 py-1 bg-transparent" /></label>
          <label>High-value threshold (₹)<input type="number" value={form.high_value_threshold ?? ""} onChange={(e) => setForm({ ...form, high_value_threshold: Number(e.target.value) })} className="w-full rounded border px-2 py-1 bg-transparent" /></label>
          <label>Random audit rate (0–1)<input type="number" step="0.05" value={form.audit_rate ?? ""} onChange={(e) => setForm({ ...form, audit_rate: Number(e.target.value) })} className="w-full rounded border px-2 py-1 bg-transparent" /></label>
          <label>Kiosk PIN<input value={form.kiosk_pin ?? ""} onChange={(e) => setForm({ ...form, kiosk_pin: e.target.value })} className="w-full rounded border px-2 py-1 bg-transparent" /></label>
        </div>
        <button onClick={async () => { await owner.settings(store, form); load(); }} className="rounded-lg bg-emerald-600 text-white px-4 py-1.5 text-sm">Save</button>
      </section>
    </div>
  );
}

function ConnectorsTab({ store }: { store: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({ sku: "sku", name: "name", price: "price", on_hand: "on_hand", barcode: "barcode", category: "category", aisle: "aisle" });
  const [analysis, setAnalysis] = useState<{ notes: string[]; questions: string[]; confidence: number; source: string; header: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string>("");
  const [qr, setQr] = useState<{ entrance_url: string; aisles: { aisle: string; url: string }[] } | null>(null);
  async function analyse() {
    if (!file) return;
    setBusy(true); setResult("");
    try {
      const r = await owner.propose(store, file);
      setMapping(r.proposal.mapping);
      setAnalysis({ ...r.proposal, header: r.header });
    } catch (e) { setResult(`Analysis failed: ${(e as Error).message}`); }
    setBusy(false);
  }
  async function run() {
    if (!file) return;
    const clean = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v));
    try { const r = await owner.importCsv(store, file, clean); setResult(`Created ${r.created}, updated ${r.updated}, ${r.errors.length} row errors${r.errors[0] ? ` (line ${r.errors[0].line}: ${r.errors[0].message})` : ""}.`); }
    catch (e) { setResult(`Import failed: ${(e as Error).message}`); }
  }
  const fields = ["sku", "name", "price", "on_hand", "barcode", "brand", "category", "subcategory", "mrp", "unit", "aisle", "supplier_id", "reorder_point", "reorder_qty", "lead_time_days", "tags"];
  return (
    <div className="p-4 space-y-4 max-w-3xl">
      <section className="space-y-2">
        <h2 className="font-semibold">Import products from any file</h2>
        <p className="text-xs text-zinc-500">Export from your POS, Excel, Google Sheets or Shopify as CSV. The assistant reads the header and a few rows, proposes how the columns map to ours, and you confirm. Your data is converted by the connector, not by the model.</p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setAnalysis(null); }} className="text-sm" />
          <button onClick={analyse} disabled={!file || busy} className="rounded-lg bg-emerald-600 disabled:bg-zinc-300 text-white px-4 py-1.5 text-sm">{busy ? "Analysing…" : "Analyse with AI"}</button>
        </div>
        {analysis && (
          <div className="rounded-xl border border-emerald-200 dark:border-emerald-900 p-3 text-sm space-y-1">
            <div className="flex items-center gap-2"><b>Proposed mapping</b><span className="text-xs rounded-full bg-emerald-100 text-emerald-800 px-2 py-0.5">{analysis.source === "model" ? `AI · ${Math.round(analysis.confidence * 100)}% confident` : "heuristic"}</span></div>
            {analysis.notes.map((n) => <div key={n} className="text-zinc-600 dark:text-zinc-300">· {n}</div>)}
            {analysis.questions.map((q) => <div key={q} className="text-amber-700 dark:text-amber-400">? {q}</div>)}
            <div className="text-xs text-zinc-500">Columns in your file: {analysis.header.join(", ")}</div>
          </div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
          {fields.map((k) => <label key={k} className="text-xs">{k}{["sku", "name", "price", "on_hand"].includes(k) && <span className="text-red-600">*</span>}
            {analysis ? (
              <select value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="w-full rounded border px-2 py-1 bg-transparent text-sm">
                <option value="">— not in file —</option>{analysis.header.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
            ) : <input value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="w-full rounded border px-2 py-1 bg-transparent text-sm" />}
          </label>)}
        </div>
        <button onClick={run} disabled={!file} className="rounded-lg bg-emerald-600 disabled:bg-zinc-300 text-white px-4 py-1.5 text-sm">Import with this mapping</button>
        {result && <p className="text-sm">{result}</p>}
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Printable QR codes</h2>
        <button onClick={() => owner.qr(store).then(setQr)} className="rounded-lg border px-4 py-1.5 text-sm">Show entrance and aisle links</button>
        {qr && <ul className="text-xs break-all space-y-1"><li><b>Entrance:</b> {qr.entrance_url}</li>{qr.aisles.map((a) => <li key={a.aisle}><b>{a.aisle}:</b> {a.url}</li>)}</ul>}
      </section>
    </div>
  );
}

function OwnerChat({ store }: { store: string }) {
  const { session, setSession, setStore } = useApp();
  const [err, setErr] = useState("");
  useEffect(() => {
    if (session?.mode === "owner" && session.store_id === store) return;
    owner.session(store).then((s) => { setSession(s); }).catch((e) => setErr(e.message));
    import("@/lib/api").then(({ api }) => api.store(store).then(setStore).catch(() => {}));
  }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <p className="p-4 text-red-600 text-sm">{err}</p>;
  if (session?.mode !== "owner") return <p className="p-4 text-zinc-500">Starting owner assistant…</p>;
  return <div className="h-full"><Chat /></div>;
}
