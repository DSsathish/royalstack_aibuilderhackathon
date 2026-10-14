"use client";
import { useApp } from "@/lib/store";

/** Small animated 2D face: idle, listening, thinking, speaking. */
export default function Avatar({ size = 40 }: { size?: number }) {
  const state = useApp((s) => s.avatar);
  const mouth = { idle: "M20 27 q6 3 12 0", listening: "M22 27 q4 1 8 0", thinking: "M21 28 q5 -2 10 0", speaking: "M20 26 q6 7 12 0" }[state];
  return (
    <svg width={size} height={size} viewBox="0 0 52 52" aria-label={`assistant ${state}`} className={state === "thinking" ? "animate-pulse" : ""}>
      <circle cx="26" cy="26" r="24" className="fill-emerald-500" />
      <circle cx="18" cy="21" r="3" className="fill-white" />
      <circle cx="34" cy="21" r="3" className="fill-white" />
      <path d={mouth} className={`stroke-white fill-none ${state === "speaking" ? "animate-bounce" : ""}`} strokeWidth="2.5" strokeLinecap="round" />
      {state === "listening" && <circle cx="26" cy="26" r="24" className="fill-none stroke-emerald-300 animate-ping" strokeWidth="2" />}
    </svg>
  );
}
