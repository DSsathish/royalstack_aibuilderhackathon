"use client";
import { useEffect, useRef, useState } from "react";
import { Product, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import ProductCard from "./ProductCard";

type Detector = { detect(src: ImageBitmapSource): Promise<{ rawValue: string }[]> };
declare global { interface Window { BarcodeDetector?: new (o?: { formats: string[] }) => Detector } }

/** Rear-camera scanner: native BarcodeDetector when present, ZXing otherwise. Aisle QR codes update position. */
export default function Scanner({ onPhoto }: { onPhoto: (f: File) => void }) {
  const { session, setSession, setCart } = useApp();
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
    if (aisle) { setSession(await api.setAisle(session, aisle)); setError(`You are at aisle ${aisle}`); return; }
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
      <div className="relative rounded-xl overflow-hidden bg-black aspect-[3/4] max-h-[50vh]">
        <video ref={video} className="w-full h-full object-cover" muted playsInline />
        <div className="absolute inset-x-8 top-1/2 h-0.5 bg-emerald-400/80 animate-pulse" />
      </div>
      {error && <div className="text-sm text-amber-600">{error}</div>}
      {found && (
        <div className="rounded-xl border border-emerald-300 p-3 flex flex-col gap-2">
          <ProductCard p={found} />
          <div className="flex items-center gap-3">
            <button onClick={() => setQty(Math.max(1, qty - 1))} className="w-9 h-9 rounded-full border">−</button>
            <span className="font-semibold">{qty}</span>
            <button onClick={() => setQty(qty + 1)} className="w-9 h-9 rounded-full border">+</button>
            <button onClick={add} className="flex-1 rounded-lg bg-emerald-600 text-white py-2 font-semibold">Add to cart</button>
          </div>
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); onCode(manual.trim()); setManual(""); }} className="flex gap-2">
        <input value={manual} onChange={(e) => setManual(e.target.value)} inputMode="numeric" placeholder="Type barcode" className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-transparent px-3 py-2 text-sm" />
        <button className="rounded-lg border px-3 text-sm">Look up</button>
      </form>
      <label className="text-center text-sm text-emerald-700 dark:text-emerald-400 cursor-pointer">Can&apos;t find the barcode? Take a photo instead
        <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onPhoto(f); e.target.value = ""; }} />
      </label>
    </div>
  );
}
