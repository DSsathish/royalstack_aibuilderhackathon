"use client";
import { useState } from "react";
import { Aisle, Location } from "@/lib/api";

const ENTRANCE = { x: 500, y: 585 };
const CORRIDOR_Y = 540;
const FLOOR_LABEL = ["", "Ground", "First", "Second", "Third", "Fourth", "Fifth"];
const KIND_FILL: Record<string, string> = { aisle: "fill-surface", chiller: "fill-[#dbeefe]", freezer: "fill-[#e4f1fb]", counter: "fill-[#f3e9d9]" };
const KIND_WORD: Record<string, string> = { chiller: "chiller", freezer: "freezer", counter: "counter" };

/** SVG floor plan (1000x600 per floor). Shows the floor of the target or of the shopper, with a floor switcher when there
 *  are several; chillers, freezers and counters are drawn in their own tints. Draws a corridor route to the target bay. */
export default function StoreMap({ aisles, target, youAreHere, compact = false }:
  { aisles: Aisle[]; target?: Location | null; youAreHere?: string | null; compact?: boolean }) {
  const floorOf = (name?: string | null) => aisles.find((a) => a.aisle === name)?.floor ?? 1;
  const floors = Array.from(new Set(aisles.map((a) => a.floor ?? 1))).sort((a, b) => a - b);
  const wanted = target ? floorOf(target.aisle) : floorOf(youAreHere);
  const [picked, setPicked] = useState<{ when: number; floor: number } | null>(null);   // a manual choice holds until the target changes
  const floor = picked && picked.when === wanted ? picked.floor : wanted;
  const setFloor = (f: number) => setPicked({ when: wanted, floor: f });
  const blocks = aisles.filter((a) => (a.floor ?? 1) === floor);
  const here = blocks.find((a) => a.aisle === youAreHere);
  const start = here ? { x: here.x + here.w / 2, y: here.y + here.h + 20 } : ENTRANCE;
  const targetBlock = target ? blocks.find((a) => a.aisle === target.aisle) : undefined;
  const bays = 4;
  const end = targetBlock && target
    ? { x: targetBlock.x + (target.side === "left" ? -12 : targetBlock.w + 12), y: targetBlock.y + ((target.bay - 0.5) / bays) * targetBlock.h }
    : null;
  const route = end ? `M${start.x},${start.y} L${start.x},${CORRIDOR_Y} L${end.x},${CORRIDOR_Y} L${end.x},${end.y}` : "";
  return (
    <div className="space-y-1.5">
      {floors.length > 1 && (
        <div className="flex gap-1.5">{floors.map((f) => <button key={f} onClick={() => setFloor(f)} className={`chip ${floor === f ? "bg-ink text-bg" : "chip-muted"}`}>{FLOOR_LABEL[f] ?? `Floor ${f}`} floor{target && floorOf(target.aisle) === f ? " · item here" : ""}</button>)}</div>
      )}
      <svg viewBox="0 0 1000 600" className={`w-full ${compact ? "max-h-40" : "max-h-[70vh]"} rounded-[14px] bg-surface-2`}>
        {blocks.map((a) => (
          <g key={a.aisle}>
            <rect x={a.x} y={a.y} width={a.w} height={a.h} rx="8" className={`${targetBlock?.aisle === a.aisle ? "fill-accent-soft" : KIND_FILL[a.kind ?? "aisle"]} stroke-line`} strokeWidth="2" />
            <text x={a.x + a.w / 2} y={a.y + a.h / 2} textAnchor="middle" className="fill-ink text-[28px] font-semibold">{a.aisle}</text>
            {a.label && a.label !== a.aisle
              ? <text x={a.x + a.w / 2} y={a.y + a.h / 2 + 24} textAnchor="middle" className="fill-muted text-[13px]">{a.label.length > 14 ? a.label.slice(0, 13) + "…" : a.label}</text>
              : a.kind && a.kind !== "aisle" && <text x={a.x + a.w / 2} y={a.y + a.h / 2 + 26} textAnchor="middle" className="fill-muted text-[16px]">{KIND_WORD[a.kind]}</text>}
          </g>
        ))}
        <rect x="430" y="560" width="140" height="30" rx="6" className="fill-line" />
        <text x="500" y="582" textAnchor="middle" className="fill-ink text-[18px]">{floor === 1 ? "Entrance / Exit" : "Stairs / Lift"}</text>
        {route && <path d={route} className="stroke-accent fill-none" strokeWidth="6" strokeDasharray="14 10" strokeLinecap="round" />}
        {end && <circle cx={end.x} cy={end.y} r="14" className="fill-accent animate-pulse" />}
        <circle cx={start.x} cy={start.y} r="11" className="fill-ink" />
        <text x={start.x + 16} y={start.y + 6} className="fill-ink text-[18px]">You</text>
      </svg>
      {target && !targetBlock && floors.length > 1 && <p className="text-xs text-muted">The item is on the {FLOOR_LABEL[floorOf(target.aisle)]?.toLowerCase() ?? ""} floor.</p>}
    </div>
  );
}
