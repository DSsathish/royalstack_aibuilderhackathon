"use client";
import { useEffect, useRef } from "react";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "connecting";

/**
 * Circular audio level. `level` is 0..1: the microphone while listening, the assistant's speaker output while speaking.
 * Canvas, 60 fps, honours reduced motion (static ring with opacity only).
 */
export default function VoiceOrb({ state, level, size = 220, label }: { state: OrbState; level: number; size?: number; label?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const levelRef = useRef(0);
  const stateRef = useRef<OrbState>(state);
  useEffect(() => { levelRef.current = level; }, [level]);
  useEffect(() => { stateRef.current = state; }, [state]);

  useEffect(() => {
    const c = canvas.current; if (!c) return;
    const ctx = c.getContext("2d"); if (!ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = size * dpr; c.height = size * dpr;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const rgb = getComputedStyle(document.documentElement).getPropertyValue("--orb").trim() || "39 163 110";
    const glow = getComputedStyle(document.documentElement).getPropertyValue("--orb-glow").trim() || "143 224 184";
    const ink = getComputedStyle(document.documentElement).getPropertyValue("--ink").trim() || "#11261d";
    let raf = 0, t = 0, smooth = 0;
    const draw = () => {
      t += 1 / 60;
      const s = stateRef.current;
      const target = s === "idle" || s === "connecting" ? 0 : levelRef.current;
      smooth += (target - smooth) * (target > smooth ? 0.35 : 0.08);      // fast attack, slow release
      const cx = c.width / 2, cy = c.height / 2, R = (size / 2 - 16) * dpr;
      ctx.clearRect(0, 0, c.width, c.height);
      const breathe = reduced ? 0 : Math.sin(t * (s === "thinking" ? 6 : 1.6)) * 0.02;
      const r = R * (0.62 + breathe + smooth * 0.30);
      // halo
      const halo = ctx.createRadialGradient(cx, cy, r * 0.6, cx, cy, R * 1.05);
      halo.addColorStop(0, `rgba(${glow.replace(/ /g, ",")},${0.45 + smooth * 0.4})`);
      halo.addColorStop(1, `rgba(${glow.replace(/ /g, ",")},0)`);
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, R * 1.05, 0, Math.PI * 2); ctx.fill();
      // level rings: three concentric strokes, outer ones only when loud
      for (let i = 0; i < 3; i++) {
        const rr = r + i * 14 * dpr, a = Math.max(0, (smooth - i * 0.25) / (1 - i * 0.25));
        if (i > 0 && a <= 0) continue;
        ctx.beginPath(); ctx.arc(cx, cy, rr, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(${rgb.replace(/ /g, ",")},${i === 0 ? 0.95 : 0.35 * a})`;
        ctx.lineWidth = (i === 0 ? 3 : 1.5) * dpr; ctx.stroke();
      }
      // core disc
      ctx.beginPath(); ctx.arc(cx, cy, r * 0.82, 0, Math.PI * 2);
      const core = ctx.createRadialGradient(cx - r * 0.25, cy - r * 0.3, r * 0.1, cx, cy, r * 0.82);
      core.addColorStop(0, `rgba(${glow.replace(/ /g, ",")},0.95)`);
      core.addColorStop(1, `rgba(${rgb.replace(/ /g, ",")},${s === "speaking" ? 1 : 0.85})`);
      ctx.fillStyle = core; ctx.fill();
      // thinking / connecting: a rotating arc
      if (s === "thinking" || s === "connecting") {
        const a0 = (reduced ? 0 : t * 3) % (Math.PI * 2);
        ctx.beginPath(); ctx.arc(cx, cy, R * 0.96, a0, a0 + Math.PI * 0.6);
        ctx.strokeStyle = ink; ctx.lineWidth = 2 * dpr; ctx.stroke();
      }
      // listening: a thin mic-level bar set (12 ticks around the ring)
      if (s === "listening") {
        for (let k = 0; k < 24; k++) {
          const ang = (k / 24) * Math.PI * 2, len = (4 + smooth * 14 * (0.5 + 0.5 * Math.sin(k * 1.7 + t * 4))) * dpr;
          const x1 = cx + Math.cos(ang) * (R * 0.98), y1 = cy + Math.sin(ang) * (R * 0.98);
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 + Math.cos(ang) * len, y1 + Math.sin(ang) * len);
          ctx.strokeStyle = ink; ctx.lineWidth = 1.5 * dpr; ctx.globalAlpha = 0.55; ctx.stroke(); ctx.globalAlpha = 1;
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [size]);

  const caption = label ?? { idle: "Tap to talk", listening: "Listening", thinking: "Thinking", speaking: "Speaking", connecting: "Connecting" }[state];
  return (
    <div className="flex flex-col items-center gap-2" aria-live="polite">
      <canvas ref={canvas} style={{ width: size, height: size }} aria-label={`assistant ${state}`} />
      <div className="eyebrow">{caption}</div>
    </div>
  );
}
