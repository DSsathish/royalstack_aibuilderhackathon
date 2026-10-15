/** Live voice client: mic -> PCM16 16 kHz over a websocket; PCM16 24 kHz back into a playback queue. */

import { API } from "./api";

export type LiveFrame =
  | { type: "ready" } | { type: "interrupted" } | { type: "turn_complete" } | { type: "status"; tool: string }
  | { type: "transcript"; role: "user" | "assistant"; text: string }
  | { type: "action"; name: string; data: Record<string, unknown> } | { type: "error"; text: string };

export type LiveState = "connecting" | "listening" | "speaking" | "closed";
export type LiveHandlers = { onFrame: (f: LiveFrame) => void; onState: (s: LiveState) => void; onLevel?: (level: number, who: "mic" | "ai") => void };

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

export async function startLive(sessionId: string, h: LiveHandlers): Promise<() => void> {
  // Create both contexts synchronously, inside the user's tap, so iOS Safari does not leave them suspended.
  const capture = new AudioContext();
  const playback = new AudioContext({ sampleRate: 24000 });
  h.onState("connecting");
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  await capture.audioWorklet.addModule("/pcm-worklet.js");
  await Promise.all([capture.resume(), playback.resume()]);
  const source = capture.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(capture, "pcm-worklet");
  source.connect(node);
  const micAnalyser = capture.createAnalyser(); micAnalyser.fftSize = 1024; source.connect(micAnalyser);
  const outAnalyser = playback.createAnalyser(); outAnalyser.fftSize = 1024; outAnalyser.connect(playback.destination);
  const micBuf = new Float32Array(micAnalyser.fftSize), outBuf = new Float32Array(outAnalyser.fftSize);
  let state: LiveState = "connecting";
  const setState = (st: LiveState) => { state = st; h.onState(st); };
  let levelRaf = 0;
  const tick = () => {
    if (h.onLevel) h.onLevel(state === "speaking" ? rmsLevel(outAnalyser, outBuf) : rmsLevel(micAnalyser, micBuf), state === "speaking" ? "ai" : "mic");
    levelRaf = requestAnimationFrame(tick);
  };
  levelRaf = requestAnimationFrame(tick);

  let playHead = 0;
  let scheduled: AudioBufferSourceNode[] = [];
  let speakingTimer: ReturnType<typeof setTimeout> | undefined;

  const ws = new WebSocket(`${API.replace(/^http/, "ws")}/agent/live?session_id=${sessionId}`);
  ws.binaryType = "arraybuffer";

  function playChunk(buf: ArrayBuffer) {
    const pcm = new Int16Array(buf);
    const audio = playback.createBuffer(1, pcm.length, 24000);
    const ch = audio.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
    const src = playback.createBufferSource();
    src.buffer = audio; src.connect(outAnalyser);
    const at = Math.max(playback.currentTime, playHead);
    src.start(at); playHead = at + audio.duration;
    scheduled.push(src); src.onended = () => { scheduled = scheduled.filter((x) => x !== src); };
    setState("speaking");
    clearTimeout(speakingTimer);
    speakingTimer = setTimeout(() => setState("listening"), (playHead - playback.currentTime) * 1000 + 150);
  }
  function flush() {
    scheduled.forEach((s) => { try { s.stop(); } catch {} });
    scheduled = []; playHead = 0; clearTimeout(speakingTimer); setState("listening");
  }

  let ready = false;
  node.port.onmessage = (e) => { if (ready && ws.readyState === WebSocket.OPEN) ws.send(e.data as ArrayBuffer); };   // drop audio captured before the model is ready
  ws.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) { playChunk(e.data); return; }
    const f = JSON.parse(e.data) as LiveFrame;
    if (f.type === "ready") { ready = true; setState("listening"); }
    if (f.type === "interrupted") flush();
    h.onFrame(f);
  };
  ws.onclose = () => stop();
  ws.onerror = () => { h.onFrame({ type: "error", text: "Live voice connection failed." }); stop(); };

  let stopped = false;
  function stop() {
    if (stopped) return; stopped = true;
    try { ws.send(JSON.stringify({ type: "end" })); } catch {}
    try { ws.close(); } catch {}
    cancelAnimationFrame(levelRaf);
    node.port.onmessage = null; source.disconnect(); node.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    capture.close(); flush(); playback.close();
    setState("closed");
  }
  return stop;
}
