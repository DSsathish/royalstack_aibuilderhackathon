"use client";
import type { Session } from "@/lib/api";
import { useApp } from "@/lib/store";
import { useVoice, voice } from "@/lib/voiceSession";
import { dockAction } from "@/lib/voiceText";
import { IconMic } from "./Icons";
import VoiceOrb from "./VoiceOrb";

/** The one voice control: a mic button when idle, the live orb during a conversation. It lives in the shopper's bottom
 *  bar or the owner's header, never over content (docs/lld/voice-widget.md). */
export default function VoiceDock({ variant, resolveSession }: { variant: "nav" | "header"; resolveSession?: () => Promise<Session | null> }) {
  const live = useVoice((s) => s.live), orb = useVoice((s) => s.orb), level = useVoice((s) => s.level), expanded = useVoice((s) => s.expanded);
  const session = useApp((s) => s.session), language = useApp((s) => s.language);
  const action = dockAction(live, orb);
  const hint = action === "start" ? "Start voice conversation" : action === "interrupt" ? "Interrupt the assistant" : expanded ? "Hide voice controls" : "Show voice controls";
  async function tap() {
    if (action === "start") { const s = resolveSession ? await resolveSession().catch(() => null) : session; if (s) void voice.start(s, language); }
    else if (action === "interrupt") voice.interrupt();
    else voice.toggleExpanded();
  }
  const size = variant === "nav" ? 44 : 40;
  const idle = live === "closed" && orb === "idle";
  return (
    <button type="button" onClick={tap} aria-label={hint} title={hint} aria-pressed={live !== "closed"}
      className={variant === "nav" ? "py-1 text-[11px] font-semibold flex flex-col items-center gap-0.5 text-muted" : "rounded-full shrink-0"}>
      {idle
        ? <span className="rounded-full flex items-center justify-center shadow-sm" style={{ width: size, height: size, background: "var(--accent)", color: "var(--bg)" }}><IconMic /></span>
        : <VoiceOrb state={orb} level={level} size={size} showLabel={false} />}
      {variant === "nav" && <span className={live !== "closed" ? "text-ink" : ""}>{live !== "closed" ? "Voice" : "Talk"}</span>}
    </button>
  );
}
