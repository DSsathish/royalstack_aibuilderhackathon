"use client";
import { Product, money } from "@/lib/api";
import { IconPin, IconPlus } from "./Icons";

const TINT: Record<string, string> = { Dairy: "#dbe9f3", Staples: "#efe3c8", "Oils & Ghee": "#f6e3b8", Beverages: "#e3e0f2", Snacks: "#f6dcd3", Sweets: "#f8d9e2", "Personal Care": "#dcefe4", Household: "#e2e6ea", Baby: "#f3e2ec", Pharmacy: "#dfeef0", "Fruits & Vegetables": "#dfeccf", Frozen: "#d9eef5", Pet: "#ece3d6" };

export default function ProductCard({ p, onAdd, onWhere }: { p: Product; onAdd?: (p: Product) => void; onWhere?: (p: Product) => void }) {
  const aisle = p.aisle ?? p.location?.aisle;
  const bay = p.bay ?? p.location?.bay;
  const out = p.available <= 0;
  const initials = p.name.split(" ").slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (
    <div className="card min-w-[11.5rem] max-w-[12.5rem] shrink-0 overflow-hidden flex flex-col">
      <div className="h-16 flex items-center justify-between px-3" style={{ background: TINT[p.category ?? ""] ?? "var(--surface-2)" }}>
        <span className="display text-2xl font-semibold text-ink/70">{initials}</span>
        {aisle && <span className="chip bg-surface text-ink"><IconPin className="w-3.5 h-3.5" />{aisle}{bay ? `·${bay}` : ""}</span>}
      </div>
      <div className="p-3 flex flex-col gap-1.5 flex-1">
        <div className="text-sm font-semibold leading-snug line-clamp-2">{p.name}</div>
        <div className="flex items-baseline gap-2">
          <span className="mono text-base">{money(p.price)}</span>
          {p.mrp > p.price && <span className="mono text-xs line-through text-muted">{money(p.mrp)}</span>}
        </div>
        <span className={`chip ${out ? "chip-bad" : "chip-good"}`}><span className="dot" />{out ? "Out of stock" : `${p.available} in stock`}</span>
        <div className="flex gap-2 mt-auto pt-1">
          {onAdd && <button disabled={out} onClick={() => onAdd(p)} className="btn btn-primary flex-1 py-2 text-xs"><IconPlus className="w-4 h-4" />Add</button>}
          {onWhere && aisle && <button onClick={() => onWhere(p)} className="btn btn-ghost flex-1 py-2 text-xs">Where?</button>}
        </div>
      </div>
    </div>
  );
}
