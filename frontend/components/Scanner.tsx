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
  const [found, setFound] = useState<Product | null>(null);          // the last product added, shown with its line quantity
  const [added, setAdded] = useState<{ name: string; qty: number; count: number } | null>(null);
  const [error, setError] = useState("");
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState(false);
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

  /** Scan → identify → add one to the cart → show it. The same barcode within 2.5 s is one scan; after that it adds another unit. */
  async function onCode(code: string) {
    const now = Date.now();
    if (busy || (code === lastCode.current.code && now - lastCode.current.at < 2500)) return;
    lastCode.current = { code, at: now };
    if (!session) return;
    const aisle = /[?&]aisle=([A-Za-z0-9]+)/.exec(code)?.[1];
    if (aisle) { updateSession(await api.setAisle(session, aisle)); setError(`You are at aisle ${aisle}`); return; }
    if (!/^\d{8,14}$/.test(code)) return;
    setBusy(true); setError("");
    try {
      const p = await api.byBarcode(session.store_id, code);
      const cart = await api.addItem(session, p.product_id, 1, "scan");
      setCart(cart);
      const line = cart.items.find((i) => i.product_id === p.product_id);
      setFound(p); setAdded({ name: p.name, qty: line?.qty ?? 1, count: cart.count });
      navigator.vibrate?.([40, 40, 40]);
    } catch (e) {
      const m = (e as Error).message;
      if (m === "product not found" || m === "Not Found") setError(`Barcode ${code} is not in this store's catalog. Ask staff, or photograph the product below.`);
      else if (m === "out_of_stock") setError("That item shows no stock in the system. Ask staff to check.");
      else if (m === "item_limit") setError("Self-checkout item limit reached. Please use a counter for more items.");
      else setError(`Could not add it: ${m}`);
      setFound(null); setAdded(null);
    }
    setBusy(false);
  }

  async function changeQty(delta: number) {
    if (!session || !found) return;
    try {
      const cart = delta > 0 ? await api.addItem(session, found.product_id, 1, "scan") : await api.removeItem(session, found.product_id);
      setCart(cart);
      const line = cart.items.find((i) => i.product_id === found.product_id);
      if (!line) { setFound(null); setAdded(null); } else setAdded({ name: found.name, qty: line.qty, count: cart.count });
    } catch (e) { setError(`Could not change it: ${(e as Error).message}`); }
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
      {found && added && (
        <div className="card p-3 flex flex-col gap-3 border-accent reveal" aria-live="polite">
          <div className="chip chip-good self-start">Added to your cart · {added.count} item{added.count === 1 ? "" : "s"} in total</div>
          <ProductCard p={found} />
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted flex-1">{added.name} × {added.qty}. Scan it again for one more.</span>
            <button onClick={() => changeQty(-1)} className="btn btn-ghost w-10 h-10 p-0 rounded-full" aria-label="Remove this line"><IconMinus className="w-4 h-4" /></button>
            <button onClick={() => changeQty(1)} className="btn btn-ghost w-10 h-10 p-0 rounded-full" aria-label="One more"><IconPlus className="w-4 h-4" /></button>
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
