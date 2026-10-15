// Captures mono microphone audio, downsamples to 16 kHz, and posts PCM16 chunks (~100 ms) to the main thread.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.acc = 0;
    this.out = [];
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += 1;
      if (this.acc >= this.ratio) {           // simple decimation; fine for speech
        this.acc -= this.ratio;
        const s = Math.max(-1, Math.min(1, ch[i]));
        this.out.push(s < 0 ? s * 0x8000 : s * 0x7fff);
      }
    }
    if (this.out.length >= 1600) {            // 100 ms at 16 kHz
      const buf = new Int16Array(this.out.splice(0, 1600));
      this.port.postMessage(buf.buffer, [buf.buffer]);
    }
    return true;
  }
}
registerProcessor("pcm-worklet", PcmWorklet);
