"use client";
import { Product, money } from "@/lib/api";

export default function ProductCard({ p, onAdd, onWhere }: { p: Product; onAdd?: (p: Product) => void; onWhere?: (p: Product) => void }) {
  const aisle = p.aisle ?? p.location?.aisle;
  const bay = p.bay ?? p.location?.bay;
  const out = p.available <= 0;
  return (
    <div className="min-w-44 max-w-48 shrink-0 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3 flex flex-col gap-1">
      <div className="text-sm font-semibold leading-tight line-clamp-2">{p.name}</div>
      <div className="text-xs text-zinc-500">{p.brand}</div>
      <div className="flex items-baseline gap-2">
        <span className="font-bold">{money(p.price)}</span>
        {p.mrp > p.price && <span className="text-xs line-through text-zinc-400">{money(p.mrp)}</span>}
      </div>
      <div className={`text-xs ${out ? "text-red-600" : "text-emerald-600"}`}>{out ? "Out of stock" : `${p.available} in stock`}{aisle ? ` · Aisle ${aisle}${bay ? `, bay ${bay}` : ""}` : ""}</div>
      <div className="flex gap-2 mt-1">
        {onAdd && <button disabled={out} onClick={() => onAdd(p)} className="flex-1 rounded-lg bg-emerald-600 disabled:bg-zinc-300 text-white text-xs py-1.5">Add</button>}
        {onWhere && aisle && <button onClick={() => onWhere(p)} className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-600 text-xs py-1.5">Where?</button>}
      </div>
    </div>
  );
}
