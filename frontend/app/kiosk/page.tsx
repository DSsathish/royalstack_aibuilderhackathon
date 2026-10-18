"use client";
import FieldError, { Req } from "@/components/FieldError";
import { Errors, guard, rules } from "@/lib/validate";
import { useEffect, useRef, useState } from "react";
import { Verification, api, money } from "@/lib/api";

type Step = "setup" | "scan" | "bag" | "checking" | "result";
type Detector = { detect(src: ImageBitmapSource): Promise<{ rawValue: string }[]> };

/** Exit kiosk for a tablet: PIN -> scan receipt QR -> bag photo -> verdict. Staff clear amber/red results. */
export default function Kiosk() {
  const [store, setStore] = useState(""); const [pin, setPin] = useState(""); const [kioskId, setKioskId] = useState("exit-1");
  const [ke, setKe] = useState<Errors>({});
  const [step, setStep] = useState<Step>("setup");
  useEffect(() => {
    const t = setTimeout(() => {   // after hydration: restore the tablet's saved settings
      try { const c = JSON.parse(localStorage.getItem("rs.kiosk") ?? "null"); if (c) { setStore(c.store); setPin(c.pin); setKioskId(c.kioskId); setStep("scan"); } } catch {}
    }, 0);
    return () => clearTimeout(t);
  }, []);
  const [token, setToken] = useState(""); const [result, setResult] = useState<Verification | null>(null);
  const [error, setError] = useState("");
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const zxing = useRef<{ stop(): void } | null>(null);
  const lastCode = useRef("");

  // camera runs during scan and bag steps
  useEffect(() => {
    if (step !== "scan" && step !== "bag") { stream.current?.getTracks().forEach((t) => t.stop()); stream.current = null; return; }
    let timer: ReturnType<typeof setInterval> | undefined;
    (async () => {
      try {
        if (!stream.current) stream.current = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (video.current) { video.current.srcObject = stream.current; await video.current.play(); }
        if (step === "scan") {
          const Det = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
          if (Det) {
            const det = new Det({ formats: ["qr_code"] });
            timer = setInterval(async () => { try { const c = await det.detect(video.current!); if (c[0]) onScan(c[0].rawValue); } catch {} }, 400);
          } else {
            const { BrowserQRCodeReader } = await import("@zxing/browser");
            zxing.current = await new BrowserQRCodeReader().decodeFromVideoElement(video.current!, (r) => { if (r) onScan(r.getText()); });
          }
        }
      } catch { setError("Camera not available. Paste the receipt code below."); }
    })();
    return () => { if (timer) clearInterval(timer); zxing.current?.stop(); zxing.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  function onScan(text: string) {
    const t = text.trim();
    const looksLikeReceipt = /[?&]r=/.test(t) || /^[A-Za-z0-9_-]+\.[a-f0-9]{64}$/.test(t);
    if (!looksLikeReceipt) { if (t) setError("That is not an exit code."); return; }
    if (t === lastCode.current) return;
    lastCode.current = t; setError(""); setToken(t); setStep("bag");
  }

  async function capture(skip = false) {
    setStep("checking"); setError("");
    let blob: Blob | undefined;
    if (!skip && video.current) {
      const c = document.createElement("canvas"); c.width = video.current.videoWidth; c.height = video.current.videoHeight;
      c.getContext("2d")!.drawImage(video.current, 0, 0);
      blob = await new Promise<Blob | undefined>((res) => c.toBlob((b) => res(b ?? undefined), "image/jpeg", 0.8));
    }
    try { setResult(await api.exitVerify(store, pin, token, kioskId, blob)); setStep("result"); }
    catch (e) { setError((e as Error).message); lastCode.current = ""; setStep("scan"); }
  }

  async function review(outcome: "cleared" | "issue_confirmed") {
    if (result) { try { await api.exitReview(store, pin, result.verification_id, outcome); } catch {} }
    reset();
  }
  function reset() { setResult(null); setToken(""); lastCode.current = ""; setStep("scan"); }
  useEffect(() => { if (step === "result" && result?.verdict === "clear") { const t = setTimeout(reset, 5000); return () => clearTimeout(t); } }, [step, result]);

  if (step === "setup") return (
    <main className="flex-1 flex flex-col gap-3 p-6 max-w-sm mx-auto w-full justify-center">
      <div><div className="eyebrow">Exit kiosk</div><h1 className="text-2xl font-semibold">Set up this tablet</h1></div>
      <label className="text-sm font-medium">Store id<Req /><input id="k-store" value={store} onChange={(e) => { setStore(e.target.value); setKe({ ...ke, store: "" }); }} placeholder="demo-grocery" aria-invalid={!!ke.store} className="field mt-1" /><FieldError msg={ke.store} /></label>
      <label className="text-sm font-medium">Kiosk PIN<Req /><input id="k-pin" value={pin} onChange={(e) => { setPin(e.target.value); setKe({ ...ke, pin: "" }); }} type="password" aria-invalid={!!ke.pin} className="field mt-1" /><FieldError msg={ke.pin} /></label>
      <label className="text-sm font-medium">Kiosk name <span className="text-muted font-normal">(optional)</span><input id="k-name" value={kioskId} onChange={(e) => setKioskId(e.target.value)} placeholder="Exit 1" className="field mt-1" /></label>
      <button onClick={() => {
        if (!guard({ store: { label: "Store id", value: store }, pin: { label: "Kiosk PIN", value: pin, rule: rules.number("Kiosk PIN", { integer: true }) } }, setKe)) return;
        localStorage.setItem("rs.kiosk", JSON.stringify({ store: store.trim(), pin: pin.trim(), kioskId })); setStep("scan");
      }} className="btn btn-primary py-3">Start</button>
    </main>
  );

  const color = result?.verdict === "clear" ? "bg-good" : result?.verdict === "spot_check" ? "bg-warn" : "bg-bad";
  return (
    <main className="flex-1 flex flex-col h-dvh">
      <header className="flex justify-between items-center px-4 py-2 text-sm text-muted border-b border-line">
        <span>{store} · {kioskId}</span>
        <button onClick={() => { localStorage.removeItem("rs.kiosk"); setStep("setup"); }}>Settings</button>
      </header>
      {(step === "scan" || step === "bag") && (
        <div className="flex-1 flex flex-col items-center gap-3 p-4">
          <h1 className="text-3xl font-semibold text-center">{step === "scan" ? "Scan your exit code" : "Now show your bag to the camera"}</h1>
          <div className="relative w-full max-w-md aspect-[3/4] rounded-[18px] overflow-hidden bg-ink">
            <video ref={video} className="w-full h-full object-cover" muted playsInline />
            {step === "scan" && <div className="absolute inset-12 border-4 border-accent/80 rounded-[16px]" />}
          </div>
          {step === "bag" && (
            <div className="flex gap-3 w-full max-w-md">
              <button onClick={() => capture()} className="btn btn-primary flex-1 py-3.5 text-base">Check my bag</button>
              <button onClick={() => capture(true)} className="btn btn-ghost">Skip photo</button>
            </div>
          )}
          {step === "scan" && (
            <form onSubmit={(e) => { e.preventDefault(); const f = new FormData(e.currentTarget); onScan(String(f.get("code"))); }} className="flex gap-2 w-full max-w-md">
              <input name="code" placeholder="…or paste the receipt code" className="field flex-1" />
              <button className="btn btn-ghost">Go</button>
            </form>
          )}
          {error && <p className="chip chip-bad">{error}</p>}
          <p className="text-xs text-muted">A photo of your bag is checked by AI and not stored.</p>
        </div>
      )}
      {step === "checking" && <div className="flex-1 flex flex-col items-center justify-center gap-3"><div className="w-12 h-12 rounded-full border-2 border-accent border-t-transparent animate-spin" /><div className="eyebrow">Checking</div></div>}
      {step === "result" && result && (
        <div className={`flex-1 flex flex-col items-center justify-center gap-4 p-6 text-white text-center ${color}`}>
          <div className="text-7xl">{result.verdict === "clear" ? "✓" : result.verdict === "spot_check" ? "!" : "✕"}</div>
          <h1 className="text-4xl font-semibold">{result.verdict === "clear" ? "Thank you, have a nice day" : result.verdict === "spot_check" ? "Quick check with staff" : "Please wait for staff"}</h1>
          {result.order_summary && <p className="opacity-90">{result.order_summary.items.reduce((n, i) => n + i.qty, 0)} items · {money(result.order_summary.total)}</p>}
          {result.reasons.length > 0 && <ul className="text-lg space-y-1">{result.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
          {result.vision && !result.vision.skipped && <p className="text-sm opacity-80">Bag match confidence {Math.round(result.vision.confidence * 100)}%</p>}
          {result.verdict !== "clear" && (
            <div className="flex gap-3 mt-4">
              <button onClick={() => review("cleared")} className="btn bg-white text-ink px-6 py-3">Checked, clear</button>
              {result.verdict === "flag" && <button onClick={() => review("issue_confirmed")} className="btn border-2 border-white text-white px-6 py-3">Issue confirmed</button>}
            </div>
          )}
        </div>
      )}
    </main>
  );
}
