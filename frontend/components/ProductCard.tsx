"use client";
import { Product, money } from "@/lib/api";
import { IconPin, IconPlus } from "./Icons";

const TINT: Record<string, string> = { Dairy: "#e3f0fa", Staples: "#f4ead3", "Oils & Ghee": "#fbefc9", Beverages: "#e7e5f7", Snacks: "#fde4d6", Sweets: "#fbe0e8", "Personal Care": "#dff3e8", Household: "#e6ecef", Baby: "#f7e6f0", Pharmacy: "#e0f1f3", "Fruits & Vegetables": "#e3f3d2", Frozen: "#dcf0f8", Pet: "#efe6d8" };

export default function ProductCard({ p, onAdd, onWhere, onOpen, layout = "row" }: { p: Product; onAdd?: (p: Product) => void; onWhere?: (p: Product) => void; onOpen?: (p: Product) => void; layout?: "row" | "grid" }) {
  const aisle = p.aisle ?? p.location?.aisle;
  const bay = p.bay ?? p.location?.bay;
  const out = p.available <= 0;
  const initials = p.name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (
    <div className={`reveal card overflow-hidden flex flex-col ${layout === "grid" ? "w-full" : "min-w-[11.5rem] max-w-[12.5rem] shrink-0"}`}>
      <button type="button" onClick={onOpen ? () => onOpen(p) : undefined} disabled={!onOpen} className={`${layout === "grid" ? "h-24" : "h-16"} flex items-center justify-between px-3 w-full text-left`} style={{ background: TINT[p.category ?? ""] ?? "var(--surface-2)" }} aria-label={onOpen ? `Open ${p.name}` : undefined}>
        {p.image_url
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={p.image_url} alt="" className="h-full max-w-[60%] object-contain" onError={(e) => { e.currentTarget.style.display = "none"; }} />
          : <span className="display text-2xl font-semibold text-ink/70">{initials}</span>}
        {aisle && <span className="chip bg-surface text-ink"><IconPin className="w-3.5 h-3.5" />{aisle}{bay ? `·${bay}` : ""}</span>}
      </button>
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <button type="button" onClick={onOpen ? () => onOpen(p) : undefined} disabled={!onOpen} className="text-sm font-semibold leading-snug line-clamp-2 text-left">{p.name}</button>
        {(p.pack_size || p.brand) && <div className="text-xs text-muted truncate">{[p.brand, p.pack_size].filter(Boolean).join(" · ")}</div>}
        <div className="flex items-baseline gap-2">
          <span className="mono text-base">{money(p.price)}</span>
          {p.mrp > p.price && <span className="mono text-xs line-through text-muted">{money(p.mrp)}</span>}
        </div>
        <span className={`chip ${out ? "chip-bad" : "chip-good"}`}><span className="dot" />{out ? "Out of stock" : `${p.available} in stock`}</span>
        {p.bought_30d ? <span className="text-[11px] text-muted">Bought {p.bought_30d}× this month</span> : null}
        <div className="flex gap-2 mt-auto pt-1">
          {onAdd && <button disabled={out} onClick={() => onAdd(p)} className="btn btn-primary flex-1 py-2 text-xs"><IconPlus className="w-4 h-4" />Add</button>}
          {onWhere && aisle && <button onClick={() => onWhere(p)} className="btn btn-ghost flex-1 py-2 text-xs">Where?</button>}
        </div>
      </div>
    </div>
  );
}
