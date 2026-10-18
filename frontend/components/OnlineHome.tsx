"use client";
import { useEffect, useState } from "react";
import { HomeData, Product, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { toast } from "@/lib/toast";
import { IconCamera, IconSearch } from "./Icons";
import Lottie from "./Lottie";
import ProductCard from "./ProductCard";
import ProductSheet from "./ProductSheet";

/** The online shop's first screen (docs/lld/online-shop.md): search, categories, deals, trending, recommended. */
export default function OnlineHome({ onPhoto, onAsk }: { onPhoto: (f: File) => void; onAsk: (q: string) => void }) {
  const { session, store, setCart } = useApp();
  const [home, setHome] = useState<HomeData | null>(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState<{ title: string; products: Product[]; total: number; loading: boolean } | null>(null);
  const [open, setOpen] = useState<Product | null>(null);
  useEffect(() => {
    if (!session) return;
    api.home(session.store_id, session).then(setHome).catch((e) => setErr(`The shop did not load: ${(e as Error).message}`));
  }, [session]);

  async function show(title: string, opts: { q?: string; category?: string }) {
    if (!session) return;
    setPage({ title, products: [], total: 0, loading: true });
    try { const r = await api.products(session.store_id, { ...opts, limit: 40 }); setPage({ title: r.section ?? title, products: r.products, total: r.total, loading: false }); }
    catch (e) { toast.error((e as Error).message); setPage(null); }
  }
  async function add(p: Product, qty = 1) {
    if (!session) return;
    try { setCart(await api.addItem(session, p.product_id, qty, "chat")); toast.ok(`${p.name} added to the cart.`); }
    catch (e) { toast.error(`Could not add: ${(e as Error).message}`); }
  }
  const grid = (items: Product[]) => (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3 px-4">
      {items.map((p) => <ProductCard key={p.product_id} p={p} layout="grid" onAdd={(x) => add(x)} onOpen={setOpen} />)}
    </div>
  );
  return (
    <div className="h-full overflow-y-auto pb-28">
      <header className="px-4 pt-3 pb-2 sticky top-0 bg-bg z-10">
        <div className="eyebrow">{store?.brand?.tagline || "Shop online"}</div>
        <h1 className="text-lg font-semibold leading-tight truncate">{store?.name ?? "Shop"}</h1>
        <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) show(`Results for "${q.trim()}"`, { q: q.trim() }); }} className="mt-2 flex items-center gap-2">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products" aria-label="Search products" className="field flex-1 rounded-full py-2.5" />
          <label className="btn btn-ghost btn-icon rounded-full cursor-pointer" title="Search with a photo">
            <IconCamera />
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onPhoto(f); e.target.value = ""; }} />
          </label>
          <button type="submit" className="btn btn-primary btn-icon rounded-full" aria-label="Search"><IconSearch /></button>
        </form>
      </header>

      {page ? (
        <Section title={page.title} note={page.loading ? "Searching" : `${page.total} product${page.total === 1 ? "" : "s"}`} action={<button type="button" onClick={() => setPage(null)} className="text-sm text-accent font-semibold">Back</button>}>
          {page.loading ? <Placeholder /> : page.products.length === 0
            ? <div className="px-4 py-6 text-center space-y-2"><Lottie slot="noResults" fallback={<div className="w-14 h-14 rounded-full bg-surface-2 text-muted flex items-center justify-center"><IconSearch /></div>} className="mx-auto" /><p className="text-sm text-muted">Nothing matched. Try other words, or ask the assistant.</p></div>
            : grid(page.products)}
        </Section>
      ) : err ? (
        <p className="px-4 py-6 text-sm text-bad">{err}</p>
      ) : !home ? (
        <Placeholder />
      ) : (
        <>
          {home.categories.length > 0 && (
            <Section title="Shop by category">
              <div className="flex gap-2 overflow-x-auto px-4 pb-1">
                {home.categories.map((c) => <button key={c.name} type="button" onClick={() => show(c.name, { category: c.name })} className="chip chip-muted whitespace-nowrap">{c.name} <span className="text-muted">{c.count}</span></button>)}
              </div>
            </Section>
          )}
          {home.deals.length > 0 && (
            <Section title="Deals right now">
              <div className="space-y-3">
                {home.deals.map((d) => (
                  <div key={d.offer_id} className="px-4">
                    <div className="card px-3 py-2 flex items-center gap-3"><span className="chip chip-accent">{d.name}</span><span className="text-xs text-muted">{d.detail}</span></div>
                    {d.products.length > 0 && <div className="flex gap-2 overflow-x-auto py-2 -mx-4 px-4">{d.products.map((p) => <ProductCard key={p.product_id} p={p} onAdd={(x) => add(x)} onOpen={setOpen} />)}</div>}
                  </div>
                ))}
              </div>
            </Section>
          )}
          {home.trending.length > 0 && <Section title="Trending now" note="Most bought in the last 30 days">{grid(home.trending)}</Section>}
          {home.recommended.length > 0 && <Section title={home.segment === "guest" ? "You may also like" : "Picked for you"} note={home.segment === "guest" ? undefined : "From what you usually buy"}>{grid(home.recommended)}</Section>}
          <p className="px-4 pt-2 text-xs text-muted">Looking for something specific? Use the search, send a photo, or tap the microphone.</p>
        </>
      )}
      {open && <ProductSheet key={open.product_id} p={open} onClose={() => setOpen(null)} onAdd={(p, qty) => { add(p, qty); setOpen(null); }} onAsk={(text) => { setOpen(null); onAsk(text); }} />}
    </div>
  );
}

function Section({ title, note, action, children }: { title: string; note?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="pt-4">
      <div className="px-4 pb-2 flex items-end gap-3">
        <div className="flex-1 min-w-0"><h2 className="text-base font-semibold leading-tight">{title}</h2>{note && <div className="text-xs text-muted">{note}</div>}</div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Placeholder() {
  return (
    <div className="pt-4">
      <div className="flex justify-center pb-2"><Lottie slot="loading" fallback={null} /></div>
      <div className="grid grid-cols-2 gap-3 px-4">{[0, 1, 2, 3].map((i) => <div key={i} className="card h-44 animate-pulse bg-surface-2" />)}</div>
    </div>
  );
}
