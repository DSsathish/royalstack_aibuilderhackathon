"use client";
import { useEffect, useRef, useState } from "react";
import { Product, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import ProductCard from "./ProductCard";
import { IconCamera, IconMinus, IconPlus } from "./Icons";

type Detector = { detect(src: ImageBitmapSource): Promise<{ rawValue: string }[]> };
declare global { interface Window { BarcodeDetector?: new (o?: { formats: string[] }) => Detector } }

/** Rear-camera scanner: native BarcodeDetector when present, ZXing otherwise. Aisle QR codes update position. */
export default function Scanner({ onPhoto }: { onPhoto: (f: File) => void }) {
  const { session, updateSession, setCart } = useApp();
  const video = useRef<HTMLVideoElement>(null);
  const [found, setFound] = useState<Product | null>(null);
  const [qty, setQty] = useState(1);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const lastCode = useRef<{ code: string; at: number }>({ code: "", at: 0 });

  useEffect(() => {
    let stop = () => {};
    (async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (video.current) { video.current.srcObject = stream; await video.current.play(); }
        if (window.BarcodeDetector) {
          const det = new window.BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "qr_code", "code_128"] });
          const timer = setInterval(async () => {
            if (!video.current || video.current.readyState < 2) return;
            try { const codes = await det.detect(video.current); if (codes[0]) onCode(codes[0].rawValue); } catch {}
          }, 350);
          stop = () => { clearInterval(timer); stream.getTracks().forEach((t) => t.stop()); };
        } else {
          const { BrowserMultiFormatReader } = await import("@zxing/browser");
          const reader = new BrowserMultiFormatReader();
          const controls = await reader.decodeFromVideoElement(video.current!, (r) => { if (r) onCode(r.getText()); });
          stop = () => { controls.stop(); stream.getTracks().forEach((t) => t.stop()); };
        }
      } catch { setError("Camera not available. Type the barcode below."); }
    })();
    return () => stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.session_id]);

  async function onCode(code: string) {
    const now = Date.now();
    if (code === lastCode.current.code && now - lastCode.current.at < 2500) return;
    lastCode.current = { code, at: now };
    if (!session) return;
    const aisle = /[?&]aisle=([A-Za-z0-9]+)/.exec(code)?.[1];
    if (aisle) { updateSession(await api.setAisle(session, aisle)); setError(`You are at aisle ${aisle}`); return; }
    if (!/^\d{8,14}$/.test(code)) return;
    try { setFound(await api.byBarcode(session.store_id, code)); setQty(1); setError(""); navigator.vibrate?.(60); }
    catch { setError(`Barcode ${code} is not in this store's catalog.`); }
  }

  async function add() {
    if (!session || !found) return;
    try { setCart(await api.addItem(session, found.product_id, qty, "scan")); setFound(null); navigator.vibrate?.([40, 40, 40]); }
    catch (e) { setError((e as Error).message === "item_limit" ? "Self-checkout item limit reached. Please use a counter for more items." : `Could not add: ${(e as Error).message}`); }
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="eyebrow px-1">Scan a barcode</div>
      <div className="relative rounded-[18px] overflow-hidden bg-ink aspect-[3/4] max-h-[48vh]">
        <video ref={video} className="w-full h-full object-cover" muted playsInline />
        <div className="absolute inset-x-10 top-1/2 h-0.5 bg-accent animate-pulse" />
        <div className="absolute inset-8 border-2 border-surface/60 rounded-[14px] pointer-events-none" />
      </div>
      {error && <div className="text-sm text-warn">{error}</div>}
      {found && (
        <div className="card p-3 flex flex-col gap-3 border-accent">
          <ProductCard p={found} />
          <div className="flex items-center gap-3">
            <button onClick={() => setQty(Math.max(1, qty - 1))} className="btn btn-ghost w-10 h-10 p-0 rounded-full" aria-label="Less"><IconMinus className="w-4 h-4" /></button>
            <span className="mono text-lg w-6 text-center">{qty}</span>
            <button onClick={() => setQty(qty + 1)} className="btn btn-ghost w-10 h-10 p-0 rounded-full" aria-label="More"><IconPlus className="w-4 h-4" /></button>
            <button onClick={add} className="btn btn-primary flex-1">Add to cart</button>
          </div>
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); onCode(manual.trim()); setManual(""); }} className="flex gap-2">
        <input value={manual} onChange={(e) => setManual(e.target.value)} inputMode="numeric" placeholder="Type the barcode number" className="field flex-1" />
        <button className="btn btn-ghost">Look up</button>
      </form>
      <label className="btn btn-ghost w-full cursor-pointer"><IconCamera className="w-4 h-4" />No barcode? Photograph the product
        <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onPhoto(f); e.target.value = ""; }} />
      </label>
    </div>
  );
}
