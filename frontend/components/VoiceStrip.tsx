"use client";
import { useVoice, voice } from "@/lib/voiceSession";
import { stripText } from "@/lib/voiceText";
import { IconStop } from "./Icons";

/** Status and controls for the running conversation, in the page flow (never over the thread). Hide it and the orb in
 *  the bar keeps showing the state. */
export default function VoiceStrip() {
  const live = useVoice((s) => s.live), orb = useVoice((s) => s.orb), guard = useVoice((s) => s.guard), expanded = useVoice((s) => s.expanded), fallback = useVoice((s) => s.fallback);
  if ((live === "closed" && !fallback) || !expanded) return null;
  const { label, sub } = stripText(live, orb, guard, fallback);
  return (
    <div className="flex items-center gap-2 px-4 py-2 border-t border-line bg-surface text-sm" role="status" aria-live="polite">
      <div className="min-w-0 flex-1">
        <div className="font-medium truncate">{label}</div>
        {sub && <div className="text-xs text-muted truncate">{sub}</div>}
      </div>
      {orb === "speaking" && live !== "closed" && <button type="button" onClick={() => voice.interrupt()} className="btn btn-ghost py-1.5 text-xs">Interrupt</button>}
      <button type="button" onClick={() => voice.end()} className="btn btn-ink py-1.5 text-xs"><IconStop className="w-4 h-4" /> End</button>
      <button type="button" onClick={() => voice.setExpanded(false)} aria-label="Hide voice controls" className="btn btn-ghost py-1.5 px-2.5 text-xs">Hide</button>
    </div>
  );
}
