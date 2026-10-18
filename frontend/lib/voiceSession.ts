"use client";
/** The live voice conversation, independent of any screen (docs/lld/voice-widget.md). The chat thread, the orb in the
 *  bar and the status strip all read `useVoice`; starting, ending, interrupting and typing into it go through `voice`. */
import { create } from "zustand";
import type { Session } from "./api";
import { applyAction } from "./actions";
import { GuardMode, LiveControl, LiveFrame, LiveState, liveSupported, startLive } from "./live";
import { useApp } from "./store";
import type { OrbState } from "./voiceText";

export type { OrbState };
type VoiceState = {
  live: LiveState;          // "closed" when no conversation runs
  orb: OrbState;            // what the orb shows; also driven by text replies being read aloud
  level: number;            // 0..1, the mic while listening, the assistant's voice while speaking
  guard: GuardMode;         // loudspeaker or headphones, as measured by the echo guard
  expanded: boolean;        // the status strip is shown
  fallback: boolean;        // the push-to-talk loop runs (browsers without live audio)
  supported: boolean;       // live audio works here; set after mount
};
export const useVoice = create<VoiceState>(() => ({ live: "closed", orb: "idle", level: 0, guard: "unknown", expanded: false, fallback: false, supported: false }));

const set = useVoice.setState;
const app = () => useApp.getState();
let ctl: LiveControl | null = null;
let connecting = false;
let onSession: Session | null = null;                                   // the session the conversation runs on
let liveMsg: { user: number | null; assistant: number | null } = { user: null, assistant: null };
let pendingVoice: number | null = null;                                 // the spoken user bubble waiting for its clip
let fallbackStop: (() => void) | null = null;

function onFrame(f: LiveFrame) {
  const { push, patch } = app();
  if (f.type === "transcript") {
    const slot = f.role, cur = liveMsg[slot];
    if (cur === null) {
      const id = push({ role: slot, text: f.text, ...(slot === "user" ? { voice: {} } : {}) });
      liveMsg[slot] = id;
      if (slot === "user") pendingVoice = id;
    } else patch(cur, { text: (app().messages.find((m) => m.id === cur)?.text ?? "") + f.text });
    if (slot === "user") liveMsg.assistant = null;
  } else if (f.type === "turn_complete") {
    if (pendingVoice !== null) { patch(pendingVoice, { voice: undefined }); pendingVoice = null; }   // nothing loud enough to clip: show the text
    liveMsg = { user: null, assistant: null };
  } else if (f.type === "echo") {
    const cur = liveMsg.user;
    if (cur !== null) patch(cur, { text: "(echo from the speaker)", voice: undefined });
    liveMsg.user = null; pendingVoice = null;
  } else if (f.type === "status") set({ orb: "thinking" });                 // a tool is running; the voice resumes when audio arrives
  else if (f.type === "action") { const id = liveMsg.assistant ?? (liveMsg.assistant = push({ role: "assistant", text: "" })); applyAction(f.name, f.data, id); }
  else if (f.type === "error") push({ role: "assistant", text: f.text });
}

export const voice = {
  /** Call once after mount: the bar shows the Talk slot only where live audio works. */
  detect() { set({ supported: liveSupported() }); },
  active() { return ctl !== null; },
  async start(session: Session, language: string) {
    if (ctl || connecting) return;
    connecting = true; onSession = session;
    let closedEarly = false;
    set({ expanded: true });
    try {
      const c = await startLive(session.session_id, language, {
        onLevel: (level) => set({ level }),
        onGuard: (guard) => set({ guard }),
        onUserAudio: (clip) => {
          const id = pendingVoice; pendingVoice = null;
          if (id !== null) app().patch(id, { voice: { url: URL.createObjectURL(clip.blob), seconds: clip.seconds, peaks: clip.peaks } });
        },
        onState: (st) => {
          set({ live: st, orb: st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "connecting" || st === "reconnecting" ? "connecting" : "idle" });
          app().setAvatar(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "closed" ? "idle" : "thinking");
          if (st === "closed") { closedEarly = true; ctl = null; liveMsg = { user: null, assistant: null }; pendingVoice = null; set({ level: 0, guard: "unknown", expanded: false }); }
        },
        onFrame,
      });
      if (closedEarly) c.stop(); else ctl = c;
    } catch (e) {
      app().push({ role: "assistant", text: `Live voice could not start: ${(e as Error).message}` });
      ctl = null; set({ live: "closed", orb: "idle", expanded: false });
    }
    connecting = false;
  },
  end() { ctl?.stop(); fallbackStop?.(); },
  interrupt() { ctl?.interrupt(); },
  /** A typed line becomes the next turn of the running conversation; false when none runs. */
  sendText(text: string): boolean {
    if (!ctl?.sendText(text)) return false;
    app().push({ role: "user", text });
    liveMsg = { user: null, assistant: null }; pendingVoice = null;
    return true;
  },
  setExpanded(expanded: boolean) { set({ expanded }); },
  toggleExpanded() { set((s) => ({ expanded: !s.expanded })); },
  /** The push-to-talk loop tells the controller how to stop it, so End on the strip works there too. */
  registerFallback(stop: (() => void) | null) { fallbackStop = stop; },
  /** A text reply read aloud: the orb follows a simulated cadence (browser TTS exposes no signal). Returns the stop. */
  pulse(): () => void {
    if (ctl) return () => {};
    set({ orb: "speaking" });
    const t = setInterval(() => set({ level: 0.35 + Math.random() * 0.4 }), 90);
    return () => { clearInterval(t); set({ level: 0, orb: "idle" }); };
  },
};

// The conversation follows the app: a language change restarts it; a new or ended session ends it.
useApp.subscribe((s, prev) => {
  if (!ctl) return;
  if (s.session?.session_id !== prev.session?.session_id) { voice.end(); return; }
  if (s.language !== prev.language && onSession) { const sess = s.session ?? onSession; voice.end(); setTimeout(() => { void voice.start(sess, s.language); }, 400); }
});
