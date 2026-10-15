/** Hands-free voice loop: record until the shopper stops talking, hand the audio over, speak the reply, repeat. */

export type ListenResult = { blob: Blob; mime: string } | null;

const SPEECH_RMS = 0.015;      // above this the shopper is talking
const SILENCE_MS = 1300;       // this much quiet after speech ends the utterance
const NO_SPEECH_MS = 7000;     // give up if nobody talks
const MAX_MS = 15000;

/** Records one utterance. Resolves null when no speech was detected or the loop was cancelled. */
export function listenOnce(stream: MediaStream, ctx: AudioContext, cancelled: () => boolean, onLevel?: (level: number) => void): Promise<ListenResult> {
  return new Promise((resolve) => {
    const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
    const rec = new MediaRecorder(stream, { mimeType: mime });
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 1024;
    const source = ctx.createMediaStreamSource(stream);
    source.connect(analyser);
    const buf = new Float32Array(analyser.fftSize);

    const started = Date.now();
    let spokeAt = 0, lastLoud = 0;
    const timer = setInterval(() => {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      onLevel?.(Math.min(1, rms * 6));
      const now = Date.now();
      if (rms > SPEECH_RMS) { lastLoud = now; if (!spokeAt) spokeAt = now; }
      const silentFor = now - lastLoud;
      const done = cancelled()
        || (spokeAt && silentFor > SILENCE_MS)
        || (!spokeAt && now - started > NO_SPEECH_MS)
        || now - started > MAX_MS;
      if (done && rec.state === "recording") rec.stop();
    }, 100);

    rec.onstop = () => {
      clearInterval(timer);
      source.disconnect();
      resolve(spokeAt && !cancelled() ? { blob: new Blob(chunks, { type: mime }), mime } : null);
    };
    rec.start(250);
  });
}

/** Speaks text and resolves when the browser finishes (or immediately when speech is unavailable). */
export function speak(text: string, langCode: string): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window) || !text) return resolve();
    const voice = speechSynthesis.getVoices().find((v) => v.lang.toLowerCase().startsWith(langCode));
    if (!voice && langCode !== "en") return resolve();
    const u = new SpeechSynthesisUtterance(text.replace(/[*_#`]/g, ""));
    if (voice) u.voice = voice;
    u.lang = voice?.lang ?? "en-IN";
    u.onend = () => resolve();
    u.onerror = () => resolve();
    speechSynthesis.cancel();
    speechSynthesis.speak(u);
  });
}

export function languageOf(text: string, preferred: string): string {
  if (preferred !== "auto") return preferred;
  return /[஀-௿]/.test(text) ? "ta" : /[ऀ-ॿ]/.test(text) ? "hi" : "en";
}
