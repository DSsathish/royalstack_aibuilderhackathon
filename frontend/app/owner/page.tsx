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

  if (user === undefined) return <main className="p-6 text-muted">Loading…</main>;
  if (!user) return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 p-6 text-center">
      <div><div className="eyebrow">Royal Stack</div><h1 className="text-3xl font-semibold">Owner dashboard</h1></div>
      <p className="text-muted max-w-sm">Sign in with the Google account registered for your store.</p>
      <button onClick={() => signInWithGoogle().catch((e) => setError(e.message))} className="btn btn-primary px-6 py-3">Sign in with Google</button>
      {error && <p className="chip chip-bad max-w-sm">{error.includes("operation-not-allowed") ? "Google sign-in is not enabled yet in the Firebase console (Authentication → Sign-in method → Google)." : error}</p>}
    </main>
  );
  if (!store) return <main className="p-6 text-muted">{error || `No store is registered for ${user.email}. Ask the administrator to add your email to the store.`}</main>;

  return (
    <div className="flex flex-col h-dvh">
      <header className="flex items-center gap-3 px-4 py-2.5 border-b border-line bg-surface">
        <img src="/icon.svg" alt="" className="w-7 h-7" />
        <div><div className="eyebrow leading-none">Owner</div><div className="display font-semibold leading-tight">Royal Stack</div></div>
        {stores.length > 1 ? <select value={store} onChange={(e) => setStore(e.target.value)} className="field w-auto py-1 text-sm">{stores.map((s) => <option key={s}>{s}</option>)}</select> : <span className="chip chip-muted">{store}</span>}
        <span className="flex-1" />
        <span className="text-xs text-muted hidden sm:inline">{user.email}</span>
        <button onClick={() => signOutOwner()} className="btn btn-ghost py-1.5 text-xs">Sign out</button>
      </header>
      <nav className="flex overflow-x-auto border-b border-line text-sm bg-surface">
        {TABS.map((t) => <button key={t.id} onClick={() => setTab(t.id)} className={`px-4 py-2.5 whitespace-nowrap font-semibold ${tab === t.id ? "border-b-2 border-accent text-ink" : "text-muted"}`}>{t.label}</button>)}
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
  return <div className="card p-3"><div className="eyebrow">{label}</div><div className={`mono text-2xl font-semibold mt-1 ${tone}`}>{value}</div></div>;
}

function OverviewTab({ store }: { store: string }) {
  const [o, setO] = useState<Overview | null>(null);
  useEffect(() => { owner.overview(store).then(setO); const t = setInterval(() => owner.overview(store).then(setO), 15000); return () => clearInterval(t); }, [store]);
  if (!o) return <p className="p-4 text-muted">Loading</p>;
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
      <div className="text-sm text-muted">By channel today: {Object.entries(o.today.by_channel).map(([k, v]) => `${k} ${money(v)}`).join(" · ") || "no sales yet"}</div>
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
  const badge: Record<string, string> = { ok: "chip-muted", low: "chip-warn", out: "chip-bad", dead: "chip-accent", overstock: "chip-muted" };
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
        {(["all", "low", "out", "dead", "overstock", "ok"] as const).map((f) => <button key={f} onClick={() => setFilter(f)} className={`chip ${filter === f ? "bg-ink text-bg" : "chip-muted"}`}>{f}</button>)}
        <input id="inv-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" className="field ml-auto w-auto py-1.5 text-sm" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left eyebrow"><tr><th className="py-1">Product</th><th>Status</th><th className="text-right">Available</th><th className="text-right">Avg/day</th><th className="text-right">Days cover</th><th className="text-right">Reorder pt</th><th className="text-right">Reorder qty</th><th>Aisle</th><th></th></tr></thead>
          <tbody>{shown.map((r) => (
            <tr key={r.product_id} className="border-t border-line">
              <td className="py-1.5">{r.name}</td>
              <td><span className={`chip ${badge[r.status]}`}><span className="dot" />{r.status}</span></td>
              <td className="text-right mono">{r.available}</td><td className="text-right mono">{r.avg_daily ?? "–"}</td><td className="text-right mono">{r.days_of_cover ?? "–"}</td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_point")} className="mono underline decoration-dotted">{r.reorder_point}</button></td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_qty")} className="mono underline decoration-dotted">{r.reorder_qty}</button></td>
              <td>{r.aisle}</td>
              <td><button onClick={() => count(r)} className="text-xs text-muted underline">count</button></td>
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
        <button onClick={makeDrafts} disabled={busy} className="btn btn-primary">{busy ? "Drafting with Gemini" : "Draft reorders now"}</button>
        <span className="text-xs text-muted">Nothing is sent to a supplier until you approve.</span>
      </div>
      {drafts.length === 0 && <p className="text-muted text-sm">No drafts yet.</p>}
      {drafts.map((d) => (
        <div key={d.po_id} className={`card p-3 space-y-2 ${d.status === "draft" ? "border-accent" : ""}`}>
          <div className="flex items-center gap-2">
            <div className="font-semibold">{d.supplier_name}</div>
            <span className={`chip ${d.status === "approved" ? "chip-good" : d.status === "rejected" ? "chip-muted" : "chip-warn"}`}><span className="dot" />{d.status}</span>
            <span className="text-xs text-muted">{d.lines.length} lines · {new Date(d.created_at).toLocaleString()}</span>
          </div>
          <p className="text-sm text-muted">{d.summary}</p>
          <ul className="text-sm space-y-1">{d.lines.map((l) => <li key={l.product_id}><b>{l.name}</b> × {l.qty} <span className="text-muted mono text-xs">· {l.available} left, point {l.reorder_point}{l.avg_daily ? `, ${l.avg_daily}/day` : ""}</span><div className="text-xs text-muted">{l.reason}</div></li>)}</ul>
          {d.status === "draft" && (
            <div className="flex gap-2">
              <button onClick={async () => { await owner.approve(store, d.po_id, {}); load(); }} className="btn btn-primary py-2">Approve</button>
              <button onClick={async () => { const r = window.prompt?.("Reason") ?? ""; await owner.reject(store, d.po_id, r); load(); }} className="btn btn-ghost py-2">Reject</button>
            </div>
          )}
          {d.status === "approved" && <button onClick={() => setOpen(open === d.po_id ? null : d.po_id)} className="text-xs underline text-muted">{open === d.po_id ? "Hide" : "Show"} supplier email</button>}
          {open === d.po_id && <pre className="text-xs whitespace-pre-wrap bg-surface-2 rounded-[10px] p-3 mono">{d.email_text}</pre>}
        </div>
      ))}
    </div>
  );
}

function SignalsTab({ store }: { store: string }) {
  const [s, setS] = useState<Signals | null>(null);
  const [days, setDays] = useState(7);
  useEffect(() => { owner.signals(store, days).then(setS); }, [store, days]);
  if (!s) return <p className="p-4 text-muted">Loading</p>;
  return (
    <div className="p-4 space-y-4 max-w-3xl">
      <div className="flex gap-2 text-xs">{[1, 7, 30].map((d) => <button key={d} onClick={() => setDays(d)} className={`chip ${days === d ? "bg-ink text-bg" : "chip-muted"}`}>{d === 1 ? "Today" : `${d} days`}</button>)}</div>
      <section>
        <h2 className="text-base font-semibold">Asked for, but we don&apos;t carry it</h2>
        <p className="text-xs text-muted mb-2">Captured from shopper conversations. The assistant records these itself.</p>
        {s.not_carried.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.not_carried.map((r) => <li key={r.query} className="flex justify-between border-t border-line py-1.5"><span>{r.query} {r.source === "agent" && <span className="chip chip-accent ml-1">assistant</span>}</span><b className="mono">{r.count}×</b></li>)}</ul>}
      </section>
      <section>
        <h2 className="text-base font-semibold">Asked for, but out of stock</h2>
        {s.out_of_stock.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.out_of_stock.map((r) => <li key={r.product_id} className="flex justify-between border-t border-line py-1.5"><span>{r.name}</span><span className="mono">{r.count}× · lost {money(r.lost_sales)}</span></li>)}</ul>}
      </section>
    </div>
  );
}

function LossTab({ store }: { store: string }) {
  const [l, setL] = useState<Loss | null>(null);
  const [form, setForm] = useState<Partial<Loss["settings"]>>({});
  const load = () => owner.loss(store).then((x) => { setL(x); setForm(x.settings); });
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!l) return <p className="p-4 text-muted">Loading</p>;
  const s = l.summary;
  return (
    <div className="p-4 space-y-4 max-w-3xl">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Tile label="Exits (7d)" value={s.total} /><Tile label="Clear" value={s.clear} /><Tile label="Spot checks" value={s.spot_check} tone="text-warn" /><Tile label="Flags" value={s.flag} tone="text-bad" />
        <Tile label="Flag rate" value={`${Math.round(s.flag_rate * 100)}%`} /><Tile label="Issues confirmed" value={s.issue_confirmed} /><Tile label="Random audits" value={`${Math.round(s.audit_rate * 100)}%`} />
      </div>
      <section>
        <h2 className="text-base font-semibold">Shrink candidates (shelf count vs system)</h2>
        {l.shrink.length === 0 ? <p className="text-sm text-muted">No discrepancies. Use &quot;count&quot; on the Inventory tab to record shelf counts.</p> :
          <ul className="text-sm">{l.shrink.map((r) => <li key={r.product_id} className="flex justify-between border-t border-line py-1.5"><span>{r.name}</span><span className="mono">{r.counted} vs {r.system} · <b>{r.difference > 0 ? "+" : ""}{r.difference}</b> · {money(r.value)}</span></li>)}</ul>}
      </section>
      <section>
        <h2 className="text-base font-semibold">Recent exits</h2>
        <ul className="text-sm">{l.recent.slice(0, 10).map((v) => <li key={v.verification_id} className="border-t border-line py-1.5"><span className={`chip ${v.verdict === "flag" ? "chip-bad" : v.verdict === "spot_check" ? "chip-warn" : "chip-good"}`}>{v.verdict}</span> · {new Date(v.created_at).toLocaleTimeString()} {v.reasons.length > 0 && <span className="text-muted">· {v.reasons.join("; ")}</span>}{v.review_outcome && <span className="text-xs"> · {v.review_outcome}</span>}</li>)}</ul>
      </section>
      <section className="space-y-2">
        <h2 className="text-base font-semibold">Controls</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label>Self-checkout item limit<input type="number" value={form.self_checkout_item_limit ?? ""} onChange={(e) => setForm({ ...form, self_checkout_item_limit: Number(e.target.value) })} className="field mt-1" /></label>
          <label>High-value threshold (₹)<input type="number" value={form.high_value_threshold ?? ""} onChange={(e) => setForm({ ...form, high_value_threshold: Number(e.target.value) })} className="field mt-1" /></label>
          <label>Random audit rate (0–1)<input type="number" step="0.05" value={form.audit_rate ?? ""} onChange={(e) => setForm({ ...form, audit_rate: Number(e.target.value) })} className="field mt-1" /></label>
          <label>Kiosk PIN<input value={form.kiosk_pin ?? ""} onChange={(e) => setForm({ ...form, kiosk_pin: e.target.value })} className="field mt-1" /></label>
        </div>
        <button onClick={async () => { await owner.settings(store, form); load(); }} className="btn btn-primary">Save</button>
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
        <h2 className="text-base font-semibold">Import products from any file</h2>
        <p className="text-xs text-muted">Export from your POS, Excel, Google Sheets or Shopify as CSV. The assistant reads the header and a few rows, proposes how the columns map to ours, and you confirm. Your data is converted by the connector, not by the model.</p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setAnalysis(null); }} className="text-sm" />
          <button onClick={analyse} disabled={!file || busy} className="btn btn-primary">{busy ? "Analysing" : "Analyse with AI"}</button>
        </div>
        {analysis && (
          <div className="card border-accent p-3 text-sm space-y-1">
            <div className="flex items-center gap-2"><b>Proposed mapping</b><span className="chip chip-accent">{analysis.source === "model" ? `AI · ${Math.round(analysis.confidence * 100)}% confident` : "heuristic"}</span></div>
            {analysis.notes.map((n) => <div key={n} className="text-muted">· {n}</div>)}
            {analysis.questions.map((q) => <div key={q} className="text-warn">? {q}</div>)}
            <div className="text-xs text-muted">Columns in your file: {analysis.header.join(", ")}</div>
          </div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
          {fields.map((k) => <label key={k} className="text-xs">{k}{["sku", "name", "price", "on_hand"].includes(k) && <span className="text-bad">*</span>}
            {analysis ? (
              <select value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="field py-1.5 text-sm">
                <option value="">not in file</option>{analysis.header.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
            ) : <input value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="field py-1.5 text-sm" />}
          </label>)}
        </div>
        <button onClick={run} disabled={!file} className="btn btn-ink">Import with this mapping</button>
        {result && <p className="text-sm">{result}</p>}
      </section>
      <section className="space-y-2">
        <h2 className="text-base font-semibold">Printable QR codes</h2>
        <button onClick={() => owner.qr(store).then(setQr)} className="btn btn-ghost">Show entrance and aisle links</button>
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
  if (err) return <p className="p-4 chip chip-bad">{err}</p>;
  if (session?.mode !== "owner") return <p className="p-4 text-muted">Starting the owner assistant</p>;
  return <div className="h-full"><Chat /></div>;
}
