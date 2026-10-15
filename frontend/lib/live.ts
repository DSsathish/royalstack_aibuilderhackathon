/** Live voice client: mic -> PCM16 16 kHz over a websocket; PCM16 24 kHz back into a playback queue. */

import { API } from "./api";

export type LiveFrame =
  | { type: "ready" } | { type: "interrupted" } | { type: "turn_complete" } | { type: "status"; tool: string }
  | { type: "transcript"; role: "user" | "assistant"; text: string }
  | { type: "action"; name: string; data: Record<string, unknown> } | { type: "error"; text: string };

export type LiveState = "connecting" | "listening" | "speaking" | "closed";
export type LiveHandlers = { onFrame: (f: LiveFrame) => void; onState: (s: LiveState) => void };

export function liveSupported(): boolean {
  return typeof window !== "undefined" && "AudioWorkletNode" in window && "WebSocket" in window;
}

export async function startLive(sessionId: string, h: LiveHandlers): Promise<() => void> {
  h.onState("connecting");
  // Create both contexts synchronously, inside the user's tap, so iOS Safari does not leave them suspended.
  const capture = new AudioContext();
  const playback = new AudioContext({ sampleRate: 24000 });
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
  await capture.audioWorklet.addModule("/pcm-worklet.js");
  await Promise.all([capture.resume(), playback.resume()]);
  const source = capture.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(capture, "pcm-worklet");
  source.connect(node);

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
    src.buffer = audio; src.connect(playback.destination);
    const at = Math.max(playback.currentTime, playHead);
    src.start(at); playHead = at + audio.duration;
    scheduled.push(src); src.onended = () => { scheduled = scheduled.filter((x) => x !== src); };
    h.onState("speaking");
    clearTimeout(speakingTimer);
    speakingTimer = setTimeout(() => h.onState("listening"), (playHead - playback.currentTime) * 1000 + 150);
  }
  function flush() {
    scheduled.forEach((s) => { try { s.stop(); } catch {} });
    scheduled = []; playHead = 0; clearTimeout(speakingTimer); h.onState("listening");
  }

  let ready = false;
  node.port.onmessage = (e) => { if (ready && ws.readyState === WebSocket.OPEN) ws.send(e.data as ArrayBuffer); };   // drop audio captured before the model is ready
  ws.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) { playChunk(e.data); return; }
    const f = JSON.parse(e.data) as LiveFrame;
    if (f.type === "ready") { ready = true; h.onState("listening"); }
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
    node.port.onmessage = null; source.disconnect(); node.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    capture.close(); flush(); playback.close();
    h.onState("closed");
  }
  return stop;
}
