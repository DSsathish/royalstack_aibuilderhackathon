/** Live voice client: mic -> PCM16 16 kHz over a websocket; PCM16 24 kHz back into a playback queue.
 *  One AudioContext carries both directions. Playback leaves through a media element, the path the browser's echo
 *  canceller tracks, and an EchoGuard keeps whatever echo survives from reaching the model. */

import { API } from "./api";
import { EchoGuard, GuardMode, pcmRms } from "./echoGuard";

export type LiveFrame =
  | { type: "ready" } | { type: "interrupted" } | { type: "turn_complete" } | { type: "reconnect" } | { type: "echo" } | { type: "status"; tool: string }
  | { type: "transcript"; role: "user" | "assistant"; text: string }
  | { type: "action"; name: string; data: Record<string, unknown> } | { type: "error"; text: string };

export type LiveState = "connecting" | "reconnecting" | "listening" | "speaking" | "closed";
export type { GuardMode };
export type LiveHandlers = {
  onFrame: (f: LiveFrame) => void; onState: (s: LiveState) => void;
  onLevel?: (level: number, who: "mic" | "ai") => void; onGuard?: (mode: GuardMode) => void;
};
export type LiveControl = { stop: () => void; interrupt: () => void };

const PREBUFFER_S = 0.15;    // a reply starts playing this far ahead, so late chunks do not open gaps
const ECHO_TAIL_S = 0.3;     // the room keeps echoing this long after playback stops
const CHUNK_BYTES = 3200;    // 100 ms of PCM16 at 16 kHz, what the worklet posts
const SILENCE = new ArrayBuffer(CHUNK_BYTES);

/** RMS of an analyser's time-domain signal, 0..1 with a speech-friendly curve. */
export function rmsLevel(analyser: AnalyserNode, buf: Float32Array<ArrayBuffer>): number {
  analyser.getFloatTimeDomainData(buf);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.min(1, Math.sqrt(sum / buf.length) * 6);
}

export function liveSupported(): boolean {
  return typeof window !== "undefined" && "AudioWorkletNode" in window && "WebSocket" in window;
}

export async function startLive(sessionId: string, language: string, h: LiveHandlers): Promise<LiveControl> {
  // Everything that needs the user's tap happens before the first await: the context and the media element.
  const ctx = new AudioContext();
  const sink = ctx.createMediaStreamDestination();
  const speaker = new Audio();
  speaker.srcObject = sink.stream;
  speaker.setAttribute("playsinline", "");
  const outAnalyser = ctx.createAnalyser(); outAnalyser.fftSize = 1024; outAnalyser.connect(sink);
  speaker.play().catch(() => outAnalyser.connect(ctx.destination));   // media playback refused: fall back to the plain output
  h.onState("connecting");
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 } });
  // iOS suspends the audio graph when another app takes the output or the screen locks; resume it instead of dropping the session
  const keepAlive = () => { if (document.visibilityState === "visible" && ctx.state !== "running") ctx.resume().catch(() => {}); };
  ctx.addEventListener("statechange", keepAlive);
  document.addEventListener("visibilitychange", keepAlive);
  await ctx.audioWorklet.addModule("/pcm-worklet.js");
  await ctx.resume();
  const source = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, "pcm-worklet");
  source.connect(node);
  const micAnalyser = ctx.createAnalyser(); micAnalyser.fftSize = 1024; source.connect(micAnalyser);
  const micBuf = new Float32Array(micAnalyser.fftSize), outBuf = new Float32Array(outAnalyser.fftSize);
  let state: LiveState = "connecting";
  const setState = (st: LiveState) => { state = st; h.onState(st); };
  let levelRaf = 0;
  const tick = () => {
    if (h.onLevel) h.onLevel(state === "speaking" ? rmsLevel(outAnalyser, outBuf) : rmsLevel(micAnalyser, micBuf), state === "speaking" ? "ai" : "mic");
    levelRaf = requestAnimationFrame(tick);
  };
  levelRaf = requestAnimationFrame(tick);

  // Playback queue. `played` remembers what the speaker produced lately, so the echo guard knows what to expect at the mic.
  let playHead = 0;
  let scheduled: AudioBufferSourceNode[] = [];
  const played: { t0: number; t1: number; rms: number }[] = [];
  let speakingTimer: ReturnType<typeof setTimeout> | undefined;
  let discard = false;                                                // the shopper tapped to interrupt: drop the rest of this reply

  function playChunk(buf: ArrayBuffer) {
    const pcm = new Int16Array(buf);
    const audio = ctx.createBuffer(1, pcm.length, 24000);             // the context resamples 24 kHz buffers on playback
    const ch = audio.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
    const src = ctx.createBufferSource();
    src.buffer = audio; src.connect(outAnalyser);
    const at = playHead > ctx.currentTime ? playHead : ctx.currentTime + PREBUFFER_S;
    src.start(at); playHead = at + audio.duration;
    played.push({ t0: at, t1: playHead, rms: pcmRms(pcm) });
    while (played.length && played[0].t1 < ctx.currentTime - 2) played.shift();
    scheduled.push(src); src.onended = () => { scheduled = scheduled.filter((x) => x !== src); };
    setState("speaking");
    clearTimeout(speakingTimer);
    speakingTimer = setTimeout(() => setState("listening"), (playHead - ctx.currentTime) * 1000 + 150);
  }
  function flush() {
    scheduled.forEach((s) => { try { s.stop(); } catch {} });
    scheduled = []; playHead = 0; played.length = 0; clearTimeout(speakingTimer); setState("listening");
  }
  const playing = () => playHead > 0 && ctx.currentTime < playHead + ECHO_TAIL_S;
  /** The loudest playback that could be reaching the mic right now. */
  const outLevel = () => {
    const t = ctx.currentTime; let m = 0;
    for (const p of played) if (p.t1 > t - 0.35 && p.t0 < t + 0.05) m = Math.max(m, p.rms);
    return m;
  };

  // Uplink: every mic chunk passes the echo guard; held-back chunks go out as silence so the model's timing stays continuous.
  const guard = new EchoGuard();
  let mode: GuardMode = guard.mode;
  const reportMode = () => { if (guard.mode !== mode) { mode = guard.mode; h.onGuard?.(mode); } };
  let held: { buf: ArrayBuffer; ok: boolean } | null = null;
  const url = `${API.replace(/^http/, "ws")}/agent/live?session_id=${sessionId}&language=${encodeURIComponent(language)}`;
  let ws: WebSocket;
  let ready = false;
  let attempts = 0;
  let fatal = false;
  node.port.onmessage = (e) => {
    if (!ready || !ws || ws.readyState !== WebSocket.OPEN) return;
    const buf = e.data as ArrayBuffer;
    const ok = guard.allow(pcmRms(new Int16Array(buf)), outLevel(), playing(), performance.now());
    reportMode();
    if (held) ws.send(held.ok || ok ? held.buf : SILENCE);           // one chunk of look-ahead: the first syllable of an interruption survives
    held = { buf, ok };
  };

  function connect(reconnect = false) {
    ready = false; held = null;
    setState(reconnect ? "reconnecting" : "connecting");
    ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    ws.onmessage = (e) => {
      if (e.data instanceof ArrayBuffer) { if (!discard) playChunk(e.data); return; }
      const f = JSON.parse(e.data) as LiveFrame;
      if (f.type === "ready") { ready = true; attempts = 0; setState("listening"); }
      if (f.type === "interrupted") { discard = false; flush(); }
      if (f.type === "turn_complete") discard = false;
      if (f.type === "echo") { guard.force("speaker"); reportMode(); }
      if (f.type === "error") fatal = true;
      if (f.type === "reconnect") { try { ws.close(); } catch {} }     // server is rotating the session: reconnect with resumption
      if (f.type === "transcript" && f.role === "assistant" && discard) return;   // cut off by the shopper: they did not hear this
      h.onFrame(f);
    };
    ws.onclose = () => {
      if (stopped || fatal) { stop(); return; }
      if (attempts < 3) { attempts += 1; setTimeout(() => connect(true), 400 * attempts); }   // keep mic and playback alive across the gap
      else { h.onFrame({ type: "error", text: "Live voice lost the connection. Tap Talk to start again." }); stop(); }
    };
    ws.onerror = () => { /* onclose follows and decides */ };
  }
  connect();

  let stopped = false;
  function stop() {
    if (stopped) return; stopped = true;
    try { ws?.send(JSON.stringify({ type: "end" })); } catch {}
    try { ws?.close(); } catch {}
    cancelAnimationFrame(levelRaf);
    document.removeEventListener("visibilitychange", keepAlive);
    node.port.onmessage = null; source.disconnect(); node.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    flush(); speaker.pause(); speaker.srcObject = null; ctx.close();
    setState("closed");
  }
  /** The shopper tapped while the assistant was speaking: stop the sound and listen. */
  function interrupt() {
    if (!playing()) return;
    flush(); discard = true;
  }
  return { stop, interrupt };
}
