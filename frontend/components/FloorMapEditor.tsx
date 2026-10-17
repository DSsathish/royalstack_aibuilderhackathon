"use client";
import React, { useRef, useState } from "react";
import type { Aisle } from "@/lib/api";

const W = 1000, H = 600, FLOOR = 540, GRID = 10;      // same 1000 x 600 space the shopper map draws; corridor and entrance below 540
const snap = (v: number) => Math.round(v / GRID) * GRID;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function nextName(aisles: Aisle[]): string {
  for (let i = 1; i < 99; i++) if (!aisles.some((a) => a.aisle.toLowerCase() === `a${i}`)) return `A${i}`;
  return `A${aisles.length + 1}`;
}

/** Owners draw their own floor: add aisles, drag them into place, resize from the corner, name them after what they hold.
 *  Shoppers see exactly this map, and the assistant uses the names when it gives directions. */
export default function FloorMapEditor({ aisles: initial, counts = {}, saving, onSave }:
  { aisles: Aisle[]; counts?: Record<string, number>; saving?: boolean; onSave: (aisles: Aisle[]) => void }) {
  const [aisles, setAisles] = useState<Aisle[]>(initial);
  const [sel, setSel] = useState<string | null>(initial[0]?.aisle ?? null);
  const [nameErr, setNameErr] = useState("");
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ kind: "move" | "resize"; name: string; dx: number; dy: number } | null>(null);
  const dirty = JSON.stringify(aisles) !== JSON.stringify(initial);
  const current = aisles.find((a) => a.aisle === sel) ?? null;

  function point(e: React.PointerEvent): { x: number; y: number } {
    const el = svg.current!; const pt = el.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(el.getScreenCTM()!.inverse()); return { x: p.x, y: p.y };
  }
  const update = (name: string, patch: Partial<Aisle>) => setAisles((as) => as.map((a) => (a.aisle === name ? { ...a, ...patch } : a)));

  function startMove(e: React.PointerEvent, a: Aisle) {
    const p = point(e); drag.current = { kind: "move", name: a.aisle, dx: p.x - a.x, dy: p.y - a.y }; setSel(a.aisle);
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  }
  function startResize(e: React.PointerEvent, a: Aisle) {
    e.stopPropagation(); const p = point(e); drag.current = { kind: "resize", name: a.aisle, dx: p.x - (a.x + a.w), dy: p.y - (a.y + a.h) }; setSel(a.aisle);
    (e.currentTarget as Element).setPointerCapture?.(e.pointerId);
  }
  function onMove(e: React.PointerEvent) {
    const d = drag.current; if (!d) return;
    const a = aisles.find((x) => x.aisle === d.name); if (!a) return;
    const p = point(e);
    if (d.kind === "move") update(d.name, { x: clamp(snap(p.x - d.dx), 0, W - a.w), y: clamp(snap(p.y - d.dy), 0, FLOOR - a.h) });
    else update(d.name, { w: clamp(snap(p.x - d.dx - a.x), 40, W - a.x), h: clamp(snap(p.y - d.dy - a.y), 40, FLOOR - a.y) });
  }
  const endDrag = () => { drag.current = null; };

  function add() {
    const name = nextName(aisles);
    const x = clamp(snap(60 + (aisles.length % 7) * 130), 0, W - 90);
    setAisles([...aisles, { aisle: name, x, y: 80, w: 90, h: 320 }]); setSel(name);
  }
  function rename(a: Aisle, raw: string) {
    const name = raw.replace(/[^A-Za-z0-9 ]+/g, "").slice(0, 16);
    if (!name.trim()) { setNameErr("Give the aisle a name."); return; }
    if (aisles.some((x) => x.aisle !== a.aisle && x.aisle.toLowerCase() === name.trim().toLowerCase())) { setNameErr("Another aisle already has that name."); return; }
    setNameErr(""); update(a.aisle, { aisle: name }); setSel(name);
  }
  function remove(a: Aisle) { if (aisles.length <= 1) return; setAisles(aisles.filter((x) => x.aisle !== a.aisle)); setSel(null); }
  function rotate(a: Aisle) { update(a.aisle, { w: clamp(a.h, 40, W - a.x), h: clamp(a.w, 40, FLOOR - a.y) }); }
  function lineUp() {
    const n = aisles.length, w = Math.min(90, Math.floor(820 / n) - 20);
    setAisles(aisles.map((a, i) => ({ ...a, x: 80 + i * (w + 20), y: 80, w, h: 420 })));
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <button type="button" onClick={add} disabled={aisles.length >= 16} className="btn btn-ghost py-2">Add aisle</button>
        <button type="button" onClick={lineUp} className="btn btn-ghost py-2">Line them up</button>
        <span className="flex-1" />
        {dirty && <span className="text-xs text-warn">Unsaved changes</span>}
        <button type="button" onClick={() => onSave(aisles)} disabled={!dirty || saving} className="btn btn-primary py-2">{saving ? "Saving" : "Save floor map"}</button>
      </div>
      <div className="grid lg:grid-cols-[minmax(0,1fr)_260px] gap-3">
        <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="w-full rounded-[10px] bg-surface border border-line select-none touch-none"
          onPointerMove={onMove} onPointerUp={endDrag} onPointerCancel={endDrag} onPointerDown={() => setSel(null)} role="application" aria-label="Floor map editor">
          <defs><pattern id="floor-grid" width="50" height="50" patternUnits="userSpaceOnUse"><path d="M50 0H0V50" fill="none" className="stroke-line" strokeWidth="1" /></pattern></defs>
          <rect width={W} height={H} fill="url(#floor-grid)" />
          <line x1="0" x2={W} y1={FLOOR} y2={FLOOR} className="stroke-line" strokeDasharray="8 8" strokeWidth="2" />
          <rect x="430" y="560" width="140" height="30" rx="6" className="fill-line" />
          <text x="500" y="582" textAnchor="middle" className="fill-ink text-[18px]">Entrance / Exit</text>
          {aisles.map((a) => (
            <g key={a.aisle} onPointerDown={(e) => { e.stopPropagation(); startMove(e, a); }} className="cursor-move">
              <rect x={a.x} y={a.y} width={a.w} height={a.h} rx="8" strokeWidth="2" className={sel === a.aisle ? "fill-accent-soft stroke-accent" : "fill-surface-2 stroke-line"} />
              <text x={a.x + a.w / 2} y={a.y + a.h / 2 + (counts[a.aisle] ? -6 : 8)} textAnchor="middle" className="fill-ink text-[24px] font-semibold" style={{ pointerEvents: "none" }}>{a.aisle}</text>
              {counts[a.aisle] ? <text x={a.x + a.w / 2} y={a.y + a.h / 2 + 20} textAnchor="middle" className="fill-muted text-[15px]" style={{ pointerEvents: "none" }}>{counts[a.aisle]} items</text> : null}
              {sel === a.aisle && <rect x={a.x + a.w - 16} y={a.y + a.h - 16} width="16" height="16" rx="3" className="fill-accent cursor-nwse-resize" onPointerDown={(e) => startResize(e, a)} />}
            </g>
          ))}
        </svg>
        <aside className="card p-3 space-y-3 text-sm">
          {current ? (
            <>
              <label className="block font-medium">Aisle name
                <input key={current.aisle} defaultValue={current.aisle} onBlur={(e) => rename(current, e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} maxLength={16} className="field mt-1" />
              </label>
              {nameErr && <p className="chip chip-bad whitespace-normal">{nameErr}</p>}
              <p className="label">Name it after what it holds: “Dairy”, “Rice and atta”, “Kids”. The assistant says this name when it gives directions.</p>
              <div className="grid grid-cols-2 gap-2 text-xs text-muted"><span>Position {Math.round(current.x)}, {Math.round(current.y)}</span><span>Size {Math.round(current.w)} × {Math.round(current.h)}</span></div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => rotate(current)} className="btn btn-ghost py-1.5 text-xs">Rotate</button>
                <button type="button" onClick={() => remove(current)} disabled={aisles.length <= 1} className="btn btn-ghost py-1.5 text-xs text-bad">Remove</button>
              </div>
            </>
          ) : <p className="text-muted">Select an aisle to name, move or resize it, or add a new one.</p>}
          <p className="label">Drag an aisle to move it; drag the green corner to resize. Shoppers enter at the bottom. Products are placed on aisles from the Inventory page.</p>
        </aside>
      </div>
    </div>
  );
}
