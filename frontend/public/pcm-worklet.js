// Captures mono microphone audio, downsamples to 16 kHz with a box filter (averages the source samples that fall
// into each output sample, which suppresses aliasing noise), and posts PCM16 chunks of ~100 ms to the main thread.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;        // fractional position in source samples
    this.acc = 0;        // running sum for the current output sample
    this.n = 0;          // samples in the running sum
    this.out = [];
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i]; this.n += 1; this.pos += 1;
      if (this.pos >= this.ratio) {
        this.pos -= this.ratio;
        const s = Math.max(-1, Math.min(1, this.acc / this.n));
        this.out.push(s < 0 ? s * 0x8000 : s * 0x7fff);
        this.acc = 0; this.n = 0;
      }
    }
    if (this.out.length >= 1600) {
      const buf = new Int16Array(this.out.splice(0, 1600));
      this.port.postMessage(buf.buffer, [buf.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm-worklet", PcmWorklet);
