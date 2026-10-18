"use client";
import { useEffect, useRef, useState } from "react";
import { claimPlayback } from "@/lib/voiceClip";

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** The shopper's own spoken turn: play it back, see its shape, open the transcript if wanted. */
export default function VoiceNote({ url, seconds, peaks, text }: { url?: string; seconds?: number; peaks?: number[]; text: string }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [pos, setPos] = useState(0);
  const [dur, setDur] = useState(seconds ?? 0);
  const [showText, setShowText] = useState(false);
  const bars = peaks ?? Array(28).fill(0.3);
  const hasText = !!text && text !== "…";
  useEffect(() => () => audio.current?.pause(), []);

  function toggle() {
    const el = audio.current;
    if (!el) return;
    if (el.paused) { claimPlayback(el); el.play().catch(() => setPlaying(false)); } else el.pause();
  }
  return (
    <div className="voice-note">
      <div className="flex items-center gap-2.5">
        <button type="button" onClick={toggle} disabled={!url} aria-label={playing ? "Pause your voice message" : "Play your voice message"} className="voice-play">
          {playing
            ? <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></svg>
            : <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden><path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" /></svg>}
        </button>
        <div className={`voice-wave ${url ? "" : "voice-wave-pending"}`} aria-hidden>
          {bars.map((h, i) => <span key={i} style={{ height: `${Math.round(h * 100)}%` }} className={i / bars.length < pos ? "on" : ""} />)}
        </div>
        <span className="mono text-xs opacity-80 tabular-nums">{url ? fmt(playing ? pos * dur : dur) : "…"}</span>
      </div>
      {hasText && (
        <>
          <button type="button" onClick={() => setShowText(!showText)} className="voice-text-toggle">{showText ? "Hide text" : "Show text"}</button>
          {showText && <div className="text-sm mt-1 opacity-90 whitespace-pre-wrap">{text}</div>}
        </>
      )}
      {url && (
        <audio ref={audio} src={url} preload="metadata"
          onLoadedMetadata={(e) => { const d = e.currentTarget.duration; if (Number.isFinite(d) && d > 0) setDur(d); }}
          onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
          onTimeUpdate={(e) => { const d = Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : dur; if (d) setPos(e.currentTarget.currentTime / d); }}
          onEnded={() => { setPlaying(false); setPos(0); }} />
      )}
    </div>
  );
}
