"use client";
import { useRef, useState } from "react";
import type { PillMode } from "@/lib/voicePill";
import { IconMic } from "./Icons";

const HOLD_MS = 600;
const R = 10, C = 2 * Math.PI * R;          // the level ring
const HR = 13, HC = 2 * Math.PI * HR;       // the hold ring, drawn while the finger stays down

/**
 * The one voice control, floating above the composer. Idle it is a round mic button; while talking it grows into a
 * pill whose ring shows the microphone level (listening) or the assistant's voice (speaking), turns into a spinning
 * dashed ring while a tool runs, and fills red while a long press is ending the conversation. Tap and hold are
 * decided by the parent through `onTap` and `onHold`.
 */
export default function VoicePill({ mode, level, label, sub, onTap, onHold }: {
  mode: PillMode; level: number; label: string; sub: string; onTap: () => void; onHold: () => void;
}) {
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const held = useRef(false);
  const [holding, setHolding] = useState(false);
  const idle = mode === "idle";
  const busy = mode === "thinking" || mode === "connecting" || mode === "reconnecting";

  const down = () => {
    held.current = false;
    if (idle) return;
    setHolding(true);
    timer.current = setTimeout(() => { held.current = true; setHolding(false); navigator.vibrate?.(20); onHold(); }, HOLD_MS);
  };
  const up = () => { clearTimeout(timer.current); setHolding(false); };
  const click = () => { if (held.current) { held.current = false; return; } onTap(); };
  const hint = idle ? "Start voice conversation" : `${label}. Tap to ${mode === "speaking" ? "interrupt" : "end"}, hold to end`;

  return (
    <button type="button" onClick={click} onPointerDown={down} onPointerUp={up} onPointerLeave={up} onPointerCancel={up}
      onContextMenu={(e) => e.preventDefault()} aria-label={hint} title={hint}
      className={`pill ${idle ? "pill-idle" : "pill-live"} pill-${mode}`}>
      <span className="pill-ring" aria-hidden>
        {idle ? <IconMic /> : (
          <svg viewBox="0 0 28 28" width="28" height="28">
            <circle cx="14" cy="14" r={R} className="pill-track" />
            {busy
              ? <circle cx="14" cy="14" r={R} className="pill-busy" />
              : <circle cx="14" cy="14" r={R} className="pill-level" style={{ strokeDasharray: C, strokeDashoffset: C * (1 - Math.min(1, Math.max(0, level))) }} />}
            {holding && <circle cx="14" cy="14" r={HR} className="pill-hold" style={{ strokeDasharray: HC }} />}
          </svg>
        )}
      </span>
      {!idle && (
        <span className="pill-text" aria-live="polite">
          <span className="pill-label">{label}</span>
          {sub && <span className="pill-sub">{sub}</span>}
        </span>
      )}
    </button>
  );
}
