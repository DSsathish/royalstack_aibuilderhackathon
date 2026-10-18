/** The shopper's spoken turns as playable clips, kept in the browser only (object URLs, gone when the page closes).
 *  The text transcript still goes to the assistant's memory; nothing here is uploaded. */

const RATE = 16000;
const MAX_CHUNKS = 300;          // 30 s of 100 ms chunks: a turn longer than that keeps its last 30 s
const QUIET = 0.012;             // chunk RMS under this is silence
const PAD = 2;                   // chunks of silence kept before and after the speech
const MIN_SPEECH = 3;            // fewer loud chunks than this is not a turn worth keeping

export type Clip = { blob: Blob; seconds: number; peaks: number[] };

/** Bar heights 0..1 for a small waveform. */
export function peaksOf(samples: ArrayLike<number>, bars = 28, scale = 1): number[] {
  if (!samples.length) return Array(bars).fill(0.08);
  const step = Math.max(1, Math.floor(samples.length / bars));
  const out: number[] = [];
  for (let b = 0; b < bars; b++) {
    let peak = 0;
    for (let i = b * step; i < Math.min(samples.length, (b + 1) * step); i++) peak = Math.max(peak, Math.abs(samples[i]) / scale);
    out.push(Math.max(0.08, Math.min(1, peak * 1.6)));
  }
  return out;
}

/** 16-bit mono PCM into a WAV file. */
export function pcmToWav(pcm: Int16Array, rate = RATE): Blob {
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const v = new DataView(buf);
  const text = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  text(0, "RIFF"); v.setUint32(4, 36 + pcm.length * 2, true); text(8, "WAVE");
  text(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  text(36, "data"); v.setUint32(40, pcm.length * 2, true);
  new Int16Array(buf, 44).set(pcm);
  return new Blob([buf], { type: "audio/wav" });
}

/** Collects the mic chunks actually sent to the model during one user turn; `cut` turns them into a clip. */
export class ClipBuffer {
  private chunks: { pcm: Int16Array; rms: number }[] = [];

  add(pcm: Int16Array, rms: number): void {
    this.chunks.push({ pcm: pcm.slice(), rms });
    if (this.chunks.length > MAX_CHUNKS) this.chunks.shift();
  }

  clear(): void { this.chunks = []; }

  /** The speech in the buffer, trimmed of silence at both ends; null when nobody really spoke. Empties the buffer. */
  cut(): Clip | null {
    const loud = this.chunks.map((c, i) => (c.rms >= QUIET ? i : -1)).filter((i) => i >= 0);
    const chunks = this.chunks;
    this.chunks = [];
    if (loud.length < MIN_SPEECH) return null;
    const keep = chunks.slice(Math.max(0, loud[0] - PAD), Math.min(chunks.length, loud[loud.length - 1] + PAD + 1));
    const pcm = new Int16Array(keep.reduce((n, c) => n + c.pcm.length, 0));
    let o = 0;
    for (const c of keep) { pcm.set(c.pcm, o); o += c.pcm.length; }
    return { blob: pcmToWav(pcm), seconds: pcm.length / RATE, peaks: peaksOf(pcm, 28, 0x8000) };
  }
}

/** One voice note plays at a time, and while it plays the live mic sends silence so the model never hears it. */
let current: HTMLAudioElement | null = null;
export function notePlaying(): boolean { return !!current && !current.paused && !current.ended; }
export function claimPlayback(el: HTMLAudioElement): void { if (current && current !== el) current.pause(); current = el; }
