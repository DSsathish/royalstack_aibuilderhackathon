/** Pure wording and tap rules for the compact voice control (docs/lld/voice-widget.md). No browser, no store. */
import type { GuardMode, LiveState } from "./live";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "connecting";

/** What a tap on the orb does: start a conversation, interrupt a reply, or show/hide the strip. */
export function dockAction(live: LiveState, orb: OrbState): "start" | "interrupt" | "toggle" {
  if (live === "closed") return "start";
  if (orb === "speaking") return "interrupt";
  return "toggle";
}

/** The strip's two lines. */
export function stripText(live: LiveState, orb: OrbState, guard: GuardMode, fallback = false): { label: string; sub: string } {
  if (fallback) return { label: orb === "listening" ? "Listening. Speak, then pause" : orb === "speaking" ? "Speaking" : "Working on it", sub: "Push-to-talk mode" };
  if (live === "reconnecting") return { label: "Reconnecting, keep talking", sub: "" };
  if (live === "connecting") return { label: "Connecting", sub: "" };
  const onSpeaker = guard === "speaker";
  const label = orb === "listening" ? (onSpeaker ? "Listening. Just talk" : "Listening. Just talk, interrupt any time")
    : orb === "speaking" ? (onSpeaker ? "Speaking. Tap the orb to interrupt" : "Speaking")
    : orb === "thinking" ? "Checking" : "Ready";
  const sub = onSpeaker ? "Loudspeaker: tap the orb to interrupt" : guard === "duplex" ? "Headphones: talk over any time" : "Checking for speaker echo";
  return { label, sub };
}
