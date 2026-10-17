"use client";
import { useEffect, useRef, useState } from "react";

type Detector = { detect(src: ImageBitmapSource): Promise<{ rawValue: string }[]> };

/** Camera barcode reader used by the owner's add-by-scan. Native BarcodeDetector when present, ZXing otherwise. */
export default function BarcodeScan({ onCode, onClose }: { onCode: (code: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const last = useRef("");
  useEffect(() => {
    let stop = () => {};
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (video.current) { video.current.srcObject = stream; await video.current.play(); }
        const Det = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
        const seen = (code: string) => { if (/^\d{8,14}$/.test(code) && code !== last.current) { last.current = code; onCode(code); } };
        if (Det) {
          const det = new Det({ formats: ["ean_13", "ean_8", "upc_a", "code_128"] });
          const t = setInterval(async () => { try { const c = await det.detect(video.current!); if (c[0]) seen(c[0].rawValue); } catch {} }, 350);
          stop = () => { clearInterval(t); stream.getTracks().forEach((x) => x.stop()); };
        } else {
          const { BrowserMultiFormatReader } = await import("@zxing/browser");
          const controls = await new BrowserMultiFormatReader().decodeFromVideoElement(video.current!, (r) => { if (r) seen(r.getText()); });
          stop = () => { controls.stop(); stream.getTracks().forEach((x) => x.stop()); };
        }
      } catch { setError("Camera not available. Type the barcode instead."); }
    })();
    return () => stop();
  }, [onCode]);
  return (
    <div className="card p-3 space-y-2">
      <div className="relative rounded-[14px] overflow-hidden bg-ink aspect-[4/3]"><video ref={video} className="w-full h-full object-cover" muted playsInline /><div className="absolute inset-x-10 top-1/2 h-0.5 bg-accent animate-pulse" /></div>
      {error && <p className="text-sm text-warn">{error}</p>}
      <form onSubmit={(e) => { e.preventDefault(); if (/^\d{8,14}$/.test(manual.trim())) onCode(manual.trim()); }} className="flex gap-2">
        <input value={manual} onChange={(e) => setManual(e.target.value)} inputMode="numeric" placeholder="Type barcode" className="field flex-1 py-1.5 text-sm" />
        <button className="btn btn-ghost py-1.5 text-sm">Use</button>
        <button type="button" onClick={onClose} className="btn btn-ghost py-1.5 text-sm">Cancel</button>
      </form>
    </div>
  );
}
