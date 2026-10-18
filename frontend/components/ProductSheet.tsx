"use client";
import { useEffect, useState } from "react";
import { CompareRow, Facts, Product, api, money } from "@/lib/api";
import { useApp } from "@/lib/store";
import { IconMinus, IconPlus } from "./Icons";
import Modal from "./Modal";

/** One product: details, stock, a quantity stepper, add to cart, and the label facts the assistant can look up. */
export default function ProductSheet({ p, onClose, onAdd, onAsk }: { p: Product; onClose: () => void; onAdd: (p: Product, qty: number) => void; onAsk: (text: string) => void }) {
  const { session, language } = useApp();
  const [qty, setQty] = useState(1);
  const [facts, setFacts] = useState<Facts | "loading">("loading");     // the sheet is keyed by product, so it starts fresh each time
  const [cmp, setCmp] = useState<CompareRow[] | "loading" | null>(null);
  async function compareNow() {
    if (!session) return;
    setCmp("loading");
    try { setCmp(await api.compare(session, p.product_id)); } catch (e) { setCmp([{ provider: "", label: "Comparison", demo: false, status: "unavailable", note: (e as Error).message }]); }
  }
  const out = p.available <= 0;
  useEffect(() => {
    if (!session) return;
    api.facts(session, p.product_id, language).then(setFacts).catch((e) => setFacts({ ok: false, note: (e as Error).message }));
  }, [session, p.product_id, language]);
  const label = facts !== "loading" ? facts.label : null;
  return (
    <Modal title={p.name} onClose={onClose}>
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="mono text-xl font-semibold">{money(p.price)}</span>
          {p.mrp > p.price && <span className="mono text-sm line-through text-muted">{money(p.mrp)}</span>}
          {p.mrp > p.price && <span className="chip chip-good">Save {money(p.mrp - p.price)}</span>}
          <span className={`chip ${out ? "chip-bad" : "chip-good"}`}><span className="dot" />{out ? "Out of stock" : `${p.available} in stock`}</span>
        </div>
        <div className="text-xs text-muted">{[p.brand, p.category, p.subcategory, p.pack_size, p.unit !== "pc" ? `per ${p.unit}` : ""].filter(Boolean).join(" · ")}</div>
        {p.description && <p>{p.description}</p>}
        {(p.location?.aisle || p.aisle) && <div className="text-xs text-muted">In the shop: {p.location?.aisle ?? p.aisle}{p.aisle_label ? ` · ${p.aisle_label}` : ""}{p.location?.bay ? `, bay ${p.location.bay}` : ""}</div>}
        {p.bought_30d ? <div className="text-xs text-muted">Bought {p.bought_30d} times by shoppers this month.</div> : null}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 border border-line rounded-full px-1">
            <button type="button" onClick={() => setQty((n) => Math.max(1, n - 1))} className="btn btn-ghost w-9 h-9 p-0 rounded-full" aria-label="One less"><IconMinus className="w-4 h-4" /></button>
            <span className="mono w-6 text-center" aria-live="polite">{qty}</span>
            <button type="button" onClick={() => setQty((n) => Math.min(20, n + 1))} className="btn btn-ghost w-9 h-9 p-0 rounded-full" aria-label="One more"><IconPlus className="w-4 h-4" /></button>
          </div>
          <button type="button" disabled={out} onClick={() => onAdd(p, qty)} className="btn btn-primary flex-1 py-2.5">{out ? "Not available" : `Add ${qty} to cart`}</button>
        </div>
        <button type="button" onClick={() => onAsk(`Tell me about ${p.name}: is it good value, and what else goes with it?`)} className="btn btn-ghost w-full py-2">Ask the assistant about this</button>
        <section className="border border-line rounded-xl p-3 space-y-1.5">
          <div className="flex items-center gap-2"><div className="eyebrow flex-1">Other providers</div>{cmp === null && <button type="button" onClick={compareNow} className="text-xs text-accent font-semibold">Compare prices</button>}</div>
          {cmp === "loading" && <div className="text-muted inline-flex items-center gap-2"><span className="dot animate-pulse" />Asking connected providers</div>}
          {Array.isArray(cmp) && (
            <div className="space-y-1">
              <div className="flex justify-between"><span>This shop</span><span className="mono">{money(p.price)}</span></div>
              {cmp.map((r) => (
                <div key={r.provider || r.label} className="flex justify-between gap-2">
                  <span className="min-w-0 truncate">{r.label}{r.demo && <span className="chip chip-muted ml-1">demo data</span>}</span>
                  <span className="mono whitespace-nowrap">{r.status === "ok" ? `${money(r.price ?? 0)}${r.available === 0 ? " · out of stock" : ""}` : r.status === "no_match" ? "not listed" : "unavailable"}</span>
                </div>
              ))}
              <div className="text-xs text-muted">Live prices come only from providers the shop has connected; demo rows are samples.</div>
            </div>
          )}
        </section>
        <section className="border border-line rounded-xl p-3 space-y-1.5">
          <div className="eyebrow">Label and nutrition</div>
          {facts === "loading" && <div className="text-muted inline-flex items-center gap-2"><span className="dot animate-pulse" />Looking up public label data</div>}
          {facts !== "loading" && (
            <>
              {label?.ingredients && <div><span className="text-muted">Ingredients: </span>{label.ingredients}</div>}
              {label?.allergens && label.allergens.length > 0 && <div><span className="text-muted">Allergens: </span>{label.allergens.join(", ")}</div>}
              {label?.nutrition_per_100g && <div className="text-muted">Per 100 g: {Object.entries(label.nutrition_per_100g).map(([k, v]) => `${k.replace(/-/g, " ")} ${v}`).join(" · ")}{label.nutriscore ? ` · Nutri-Score ${label.nutriscore}` : ""}</div>}
              {facts.summary && <p>{facts.summary}</p>}
              {facts.sources && facts.sources.length > 0 && <div className="flex flex-wrap gap-x-3 gap-y-1">{facts.sources.map((s) => <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="underline text-muted text-xs">{s.title}</a>)}</div>}
              {!facts.ok && <div className="text-muted">{facts.note || "No label data is available for this product."}</div>}
              {facts.note && facts.ok && <div className="text-xs text-muted">{facts.note}</div>}
            </>
          )}
        </section>
      </div>
    </Modal>
  );
}
