/** Keeps the assistant's own voice out of the microphone stream.
 *
 *  While the assistant's audio plays, the mic hears some of it through the loudspeaker (or almost none through
 *  headphones). The browser's echo canceller removes most of it; what survives still sounds like speech to the model's
 *  turn detector, which then interrupts the assistant with its own words. The guard measures, early in each reply, how
 *  loud the mic is compared with the playback. If the mic stays quiet, the shopper is on headphones and may talk over
 *  the assistant freely ("duplex"). If it follows the playback, the shopper is on the loudspeaker ("speaker") and a mic
 *  chunk goes through only when it is clearly louder than the expected echo. Everything else is replaced by silence. */

export type GuardMode = "unknown" | "duplex" | "speaker";

export const CAL_START_MS = 150;   // the output path and the room delay the echo by about this much
export const CAL_END_MS = 650;     // the window in which the echo level is measured
export const QUIET = 0.008;        // mic level below this while the speaker plays: no echo path
export const MARGIN = 2.5;         // a chunk must be this many times the expected echo to count as the shopper
export const MIN_SPEECH = 0.02;    // and at least this loud in absolute terms
const FORCED_GAIN = 1;             // when the server reports echo before a measurement: assume a loud loudspeaker

export class EchoGuard {
  mode: GuardMode = "unknown";
  gain = 0;                        // mic level per unit of playback level on the loudspeaker
  private burstAt = -1;
  private calMic = 0;
  private calOut = 0;
  private measured = false;

  /** Whether a 100 ms mic chunk may be sent. micRms and outRms are 0..1; now is in milliseconds. */
  allow(micRms: number, outRms: number, playing: boolean, now: number): boolean {
    if (!playing) { this.burstAt = -1; return true; }
    if (this.burstAt < 0) { this.burstAt = now; this.calMic = 0; this.calOut = 0; this.measured = false; }
    const t = now - this.burstAt;
    if (t < CAL_END_MS) {
      if (t >= CAL_START_MS) { this.calMic = Math.max(this.calMic, micRms); this.calOut = Math.max(this.calOut, outRms); }
      return this.mode === "duplex";                                   // unknown or speaker: hold the mic while measuring
    }
    if (!this.measured) {
      this.measured = true;
      if (this.calOut > 0) {                                           // a silent window measures nothing: keep the last verdict
        this.gain = this.calMic / this.calOut;
        if (this.mode !== "speaker") this.mode = this.calMic < QUIET ? "duplex" : "speaker";   // speaker is sticky for the session
      }
    }
    if (this.mode !== "speaker") return true;
    return micRms > Math.max(this.gain * outRms * MARGIN, MIN_SPEECH);
  }

  /** The server heard the assistant's own words come back: treat the output as a loudspeaker from now on. */
  force(mode: GuardMode): void {
    this.mode = mode;
    if (mode === "speaker" && this.gain === 0) this.gain = FORCED_GAIN;
  }
}

/** RMS level of a PCM16 chunk, 0..1. */
export function pcmRms(pcm: Int16Array): number {
  if (pcm.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < pcm.length; i++) { const v = pcm[i] / 0x8000; sum += v * v; }
  return Math.sqrt(sum / pcm.length);
}
