"use client";
import { useState } from "react";
import { money } from "@/lib/api";

/** Single-series daily revenue: thin bars, one hue, hover tooltip, table view. */
export default function RevenueChart({ series }: { series: { day: string; revenue: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const W = 600, H = 160, pad = 24;
  const max = Math.max(1, ...series.map((d) => d.revenue));
  const bw = (W - pad * 2) / Math.max(1, series.length);
  const label = (d: string) => new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return (
    <div className="card p-3">
      <div className="flex justify-between items-baseline mb-1">
        <div className="eyebrow">Daily revenue, last 14 days</div>
        <button onClick={() => setTable(!table)} className="text-xs text-muted underline">{table ? "Chart" : "Table"}</button>
      </div>
      {table ? (
        <table className="w-full text-sm"><tbody>{series.map((d) => <tr key={d.day} className="border-t border-line"><td className="py-1">{label(d.day)}</td><td className="text-right mono">{money(d.revenue)}</td></tr>)}</tbody></table>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Daily revenue bar chart">
            <line x1={pad} x2={W - pad} y1={H - pad} y2={H - pad} className="stroke-line" />
            {series.map((d, i) => {
              const h = Math.round(((H - pad * 2) * d.revenue) / max);
              const x = pad + i * bw + 2, y = H - pad - h;
              return <rect key={d.day} x={x} y={y} width={Math.max(2, bw - 4)} height={h} rx="3"
                className={hover === i ? "fill-ink" : "fill-accent"} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />;
            })}
            {series.length > 0 && <text x={W - pad} y={H - pad - Math.round(((H - pad * 2) * series[series.length - 1].revenue) / max) - 6} textAnchor="end" className="fill-ink text-[11px] mono">{money(series[series.length - 1].revenue)}</text>}
            <text x={pad} y={H - 6} className="fill-muted text-[10px]">{series[0] ? label(series[0].day) : ""}</text>
            <text x={W - pad} y={H - 6} textAnchor="end" className="fill-muted text-[10px]">today</text>
          </svg>
          {hover !== null && series[hover] && (
            <div className="absolute top-2 left-1/2 -translate-x-1/2 rounded-md bg-ink text-bg text-xs px-2 py-1 mono">{label(series[hover].day)} · {money(series[hover].revenue)}</div>
          )}
        </div>
      )}
    </div>
  );
}
