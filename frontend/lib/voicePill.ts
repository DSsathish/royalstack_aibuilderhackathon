/** The floating voice pill's rules, kept free of React so they can be unit-tested. The pill is the only voice control:
 *  a tap starts, a tap while the assistant speaks interrupts, a tap while it listens ends, and a long press always ends.
 *  A tap just after the assistant stops speaking is ignored, because the shopper meant to interrupt. */

export type PillMode = "idle" | "connecting" | "reconnecting" | "listening" | "thinking" | "speaking";
export type TapAction = "start" | "interrupt" | "end" | "ignore";
export type Guard = "unknown" | "duplex" | "speaker";

export const INTERRUPT_GRACE_MS = 800;

export function tapAction(mode: PillMode, msSinceSpeechEnded: number): TapAction {
  if (mode === "idle") return "start";
  if (mode === "speaking") return "interrupt";
  if ((mode === "listening" || mode === "thinking") && msSinceSpeechEnded < INTERRUPT_GRACE_MS) return "ignore";
  return "end";
}

/** What the pill says: the state on the first line, where the sound goes (and how to interrupt) on the second. */
export function pillText(mode: PillMode, guard: Guard, activity: string | null): { label: string; sub: string } {
  const where = guard === "speaker" ? "Loudspeaker" : guard === "duplex" ? "Headphones" : "";
  switch (mode) {
    case "idle": return { label: "Talk", sub: "" };
    case "connecting": return { label: "Connecting", sub: "" };
    case "reconnecting": return { label: "Reconnecting", sub: "Keep talking" };
    case "listening": return { label: "Listening", sub: guard === "duplex" ? "Headphones · talk over any time" : where };
    case "thinking": return { label: activity || "Checking", sub: where };
    case "speaking": return { label: "Speaking", sub: guard === "duplex" ? "Talk over or tap to interrupt" : "Tap to interrupt" };
  }
}
