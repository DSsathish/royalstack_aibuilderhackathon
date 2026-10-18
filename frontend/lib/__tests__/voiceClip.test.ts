import { describe, expect, it } from "vitest";
import { ClipBuffer, pcmToWav, peaksOf } from "../voiceClip";

const chunk = (amp: number) => Int16Array.from({ length: 1600 }, (_, i) => (i % 2 ? amp : -amp));

describe("voice clips", () => {
  it("writes a valid 16 kHz mono WAV", async () => {
    const wav = pcmToWav(new Int16Array(1600));
    const bytes = new Uint8Array(await wav.arrayBuffer());
    expect(wav.type).toBe("audio/wav");
    expect(bytes.length).toBe(44 + 3200);
    expect(String.fromCharCode(...bytes.slice(0, 4))).toBe("RIFF");
    expect(new DataView(bytes.buffer).getUint32(24, true)).toBe(16000);
  });
  it("keeps the speech with a little padding and drops the silence around it", () => {
    const b = new ClipBuffer();
    for (let i = 0; i < 10; i++) b.add(chunk(0), 0);           // 1 s of silence
    for (let i = 0; i < 8; i++) b.add(chunk(8000), 0.24);      // 0.8 s of speech
    for (let i = 0; i < 10; i++) b.add(chunk(0), 0);
    const clip = b.cut()!;
    expect(clip.seconds).toBeCloseTo(1.2, 5);                    // 8 chunks + 2 padding each side
    expect(clip.peaks).toHaveLength(28);
    expect(Math.max(...clip.peaks)).toBeGreaterThan(0.3);
    expect(b.cut()).toBeNull();                                  // cut empties the buffer
  });
  it("returns nothing for a cough or for silence", () => {
    const b = new ClipBuffer();
    b.add(chunk(9000), 0.3); b.add(chunk(9000), 0.3);
    for (let i = 0; i < 20; i++) b.add(chunk(0), 0);
    expect(b.cut()).toBeNull();
  });
  it("draws flat bars for empty audio", () => {
    expect(peaksOf([], 5)).toEqual([0.08, 0.08, 0.08, 0.08, 0.08]);
  });
});
