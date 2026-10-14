"use client";
import { Aisle, Location } from "@/lib/api";

const ENTRANCE = { x: 500, y: 585 };
const CORRIDOR_Y = 540;

/** SVG floor plan (1000x600 space). Highlights a target bay and draws a corridor route from the shopper's position. */
export default function StoreMap({ aisles, target, youAreHere, compact = false }:
  { aisles: Aisle[]; target?: Location | null; youAreHere?: string | null; compact?: boolean }) {
  const here = aisles.find((a) => a.aisle === youAreHere);
  const start = here ? { x: here.x + here.w / 2, y: here.y + here.h + 20 } : ENTRANCE;
  const targetAisle = target ? aisles.find((a) => a.aisle === target.aisle) : undefined;
  const bays = 4;
  const end = targetAisle && target
    ? { x: targetAisle.x + (target.side === "left" ? -12 : targetAisle.w + 12), y: targetAisle.y + ((target.bay - 0.5) / bays) * targetAisle.h }
    : null;
  const route = end ? `M${start.x},${start.y} L${start.x},${CORRIDOR_Y} L${end.x},${CORRIDOR_Y} L${end.x},${end.y}` : "";
  return (
    <svg viewBox="0 0 1000 600" className={`w-full ${compact ? "max-h-40" : "max-h-[70vh]"} rounded-xl bg-zinc-100 dark:bg-zinc-800`}>
      {aisles.map((a) => (
        <g key={a.aisle}>
          <rect x={a.x} y={a.y} width={a.w} height={a.h} rx="8" className={`${targetAisle?.aisle === a.aisle ? "fill-emerald-200 dark:fill-emerald-900" : "fill-white dark:fill-zinc-700"} stroke-zinc-300 dark:stroke-zinc-600`} strokeWidth="2" />
          <text x={a.x + a.w / 2} y={a.y + a.h / 2} textAnchor="middle" className="fill-zinc-700 dark:fill-zinc-200 text-[28px] font-semibold">{a.aisle}</text>
        </g>
      ))}
      <rect x="430" y="560" width="140" height="30" rx="6" className="fill-zinc-300 dark:fill-zinc-600" />
      <text x="500" y="582" textAnchor="middle" className="fill-zinc-700 dark:fill-zinc-100 text-[18px]">Entrance / Exit</text>
      {route && <path d={route} className="stroke-emerald-600 fill-none" strokeWidth="6" strokeDasharray="14 10" strokeLinecap="round" />}
      {end && <circle cx={end.x} cy={end.y} r="14" className="fill-emerald-600 animate-pulse" />}
      <circle cx={start.x} cy={start.y} r="11" className="fill-blue-600" />
      <text x={start.x + 16} y={start.y + 6} className="fill-blue-700 dark:fill-blue-300 text-[18px]">You</text>
    </svg>
  );
}
