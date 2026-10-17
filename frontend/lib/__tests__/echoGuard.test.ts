import { describe, expect, it } from "vitest";
import { CAL_END_MS, EchoGuard, pcmRms } from "../echoGuard";

/** Plays one assistant burst: returns the guard's decisions for mic chunks every 100 ms. */
function burst(g: EchoGuard, mic: number[], out = 0.3, start = 1000): boolean[] {
  return mic.map((m, i) => g.allow(m, out, true, start + i * 100));
}

describe("EchoGuard", () => {
  it("lets everything through while nothing is playing", () => {
    const g = new EchoGuard();
    expect(g.allow(0.5, 0, false, 0)).toBe(true);
    expect(g.allow(0.001, 0, false, 100)).toBe(true);
    expect(g.mode).toBe("unknown");
  });

  it("holds the mic while measuring the first reply, then recognises headphones and allows talking over", () => {
    const g = new EchoGuard();
    const quiet = Array(12).fill(0.004);                    // mic hears nothing of the playback
    const hold = Math.ceil(CAL_END_MS / 100);              // chunks that fall inside the measuring window
    const decisions = burst(g, quiet);
    expect(decisions.slice(0, hold)).toEqual(Array(hold).fill(false));
    expect(g.mode).toBe("duplex");
    expect(decisions.slice(hold)).toEqual(Array(12 - hold).fill(true));
    g.allow(0, 0, false, 4000);                             // the reply ends
    expect(burst(g, [0.003, 0.4, 0.003], 0.3, 5000)).toEqual([true, true, true]);   // next reply: no hold at all
  });

  it("recognises a loudspeaker and passes only chunks clearly louder than the echo", () => {
    const g = new EchoGuard();
    burst(g, Array(8).fill(0.09));                          // echo at 0.09 while the speaker plays at 0.3
    expect(g.mode).toBe("speaker");
    expect(g.gain).toBeCloseTo(0.3, 5);
    const later = burst(g, [0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.09, 0.1, 0.4, 0.09], 0.3, 9000);
    expect(later.slice(0, 7)).toEqual(Array(7).fill(false));   // measuring again, speaker mode holds
    expect(later.slice(7)).toEqual([false, true, false]);      // 0.1 is echo-level, 0.4 is a shopper
    expect(g.allow(0.05, 0, false, 12000)).toBe(true);         // playback over: open again
  });

  it("tracks the playback level, so a quiet passage does not let echo through later", () => {
    const g = new EchoGuard();
    burst(g, Array(8).fill(0.09), 0.3);
    expect(g.allow(0.2, 0.6, true, 2000)).toBe(false);         // louder playback: expected echo 0.18, margin makes 0.45
    expect(g.allow(0.2, 0.1, true, 2100)).toBe(true);          // quiet playback: 0.2 is well above the expected echo
  });

  it("stays in speaker mode once echo is confirmed, re-measuring only the gain", () => {
    const g = new EchoGuard();
    g.force("speaker");
    expect(g.allow(0.2, 0.3, true, 0)).toBe(false);            // calibration hold
    g.allow(0, 0, false, 1000);                                // that reply ends
    const d = burst(g, Array(8).fill(0.004), 0.3, 2000);       // this reply measures almost no echo ...
    expect(g.mode).toBe("speaker");                            // ... but a confirmed loudspeaker does not become headphones
    expect(d[7]).toBe(false);                                  // 0.004 is below the speech floor
    expect(g.allow(0.05, 0.3, true, 2800)).toBe(true);         // a shopper's voice still passes
  });

  it("switches from headphones to speaker when a later reply does echo, never back", () => {
    const g = new EchoGuard();
    burst(g, Array(8).fill(0.004)); g.allow(0, 0, false, 3000);
    expect(g.mode).toBe("duplex");
    burst(g, Array(8).fill(0.06), 0.3, 4000); g.allow(0, 0, false, 6000);
    expect(g.mode).toBe("speaker");
    burst(g, Array(8).fill(0.004), 0.3, 7000);
    expect(g.mode).toBe("speaker");
  });

  it("measures PCM levels", () => {
    expect(pcmRms(new Int16Array(1600))).toBe(0);
    expect(pcmRms(Int16Array.from({ length: 1600 }, (_, i) => (i % 2 ? 0x7fff : -0x8000)))).toBeCloseTo(1, 3);
  });
});
