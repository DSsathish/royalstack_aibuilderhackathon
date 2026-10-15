"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { Order, api, money } from "@/lib/api";
import { useApp } from "@/lib/store";

declare global { interface Window { Razorpay?: new (o: Record<string, unknown>) => { open(): void } } }

export default function Checkout() {
  const router = useRouter();
  const { session, cart, setCart } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [order, setOrder] = useState<Order | null>(null);

  useEffect(() => { if (!session) router.replace("/"); else api.cart(session).then(setCart).catch(() => {}); }, [session, router, setCart]);

  async function pay() {
    if (!session) return;
    setBusy(true); setError("");
    try {
      const intent = await api.checkoutIntent(session);
      if (intent.provider === "mock") {
        setOrder(await api.checkoutConfirm(session, intent.order_id, "mock_" + Date.now(), "mock"));
      } else {
        await loadRazorpay();
        new window.Razorpay!({
          key: intent.razorpay_key_id, amount: Math.round(intent.amount * 100), currency: "INR", order_id: intent.razorpay_order_id,
          name: "Royal Stack", description: "Self-checkout", theme: { color: "#059669" },
          handler: async (r: { razorpay_payment_id: string; razorpay_signature: string }) => {
            try { setOrder(await api.checkoutConfirm(session, intent.order_id, r.razorpay_payment_id, r.razorpay_signature)); }
            catch (e) { setError((e as Error).message); }
            setBusy(false);
          },
          modal: { ondismiss: () => setBusy(false) },
        }).open();
        return;  // busy stays true until the modal's handler or ondismiss runs
      }
      setCart(await api.cart(session));
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  }

  if (!session) return null;
  if (order) return <Receipt order={order} />;
  return (
    <main className="flex-1 p-4 space-y-4 max-w-md mx-auto w-full">
      <h1 className="text-xl font-bold">Self-checkout</h1>
      {cart?.items.map((i) => (
        <div key={i.product_id} className="flex justify-between text-sm"><span>{i.name} × {i.qty}</span><span>{money(i.unit_price * i.qty)}</span></div>
      ))}
      <div className="border-t pt-2 space-y-1 text-sm">
        {cart && cart.savings > 0 && <div className="flex justify-between text-emerald-600"><span>You save</span><span>{money(cart.savings)}</span></div>}
        <div className="flex justify-between text-lg font-bold"><span>Total</span><span>{money(cart?.total ?? 0)}</span></div>
      </div>
      {error && <div className="text-sm text-red-600">{error}</div>}
      <button onClick={pay} disabled={busy || !cart?.count} className="w-full rounded-xl bg-emerald-600 disabled:bg-zinc-300 text-white py-3 font-semibold">{busy ? "Processing…" : "Pay now (sandbox)"}</button>
      <p className="text-xs text-zinc-500 text-center">Test payments only. No real money is charged.</p>
      <button onClick={() => router.back()} className="w-full text-sm text-zinc-500">Back</button>
    </main>
  );
}

export function Receipt({ order }: { order: Order }) {
  const exitUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/exit/?r=${order.receipt_token}`;
  return (
    <main className="flex-1 p-4 space-y-4 max-w-md mx-auto w-full text-center">
      <div className="text-emerald-600 text-5xl">✓</div>
      <h1 className="text-xl font-bold">Paid {money(order.total)}</h1>
      <p className="text-sm text-zinc-500">Show this code at the exit.</p>
      <div className="flex justify-center"><div className="bg-white p-3 rounded-xl"><QRCodeSVG value={exitUrl} size={220} /></div></div>
      <div className="text-left text-sm space-y-1 border rounded-xl p-3">
        {order.items.map((i) => <div key={i.product_id} className="flex justify-between"><span>{i.name} × {i.qty}</span><span>{money(i.unit_price * i.qty)}</span></div>)}
        <div className="flex justify-between font-bold border-t pt-1"><span>Total</span><span>{money(order.total)}</span></div>
      </div>
      <p className="text-xs text-zinc-400">Order {order.order_id.slice(0, 8)} · {order.paid_at ? new Date(order.paid_at).toLocaleString() : ""}</p>
      <a href="/shop" className="inline-block rounded-lg border px-4 py-2 text-sm">Continue shopping</a>
    </main>
  );
}

function loadRazorpay(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js"; s.onload = () => resolve(); s.onerror = () => reject(new Error("payment library failed to load"));
    document.body.appendChild(s);
  });
}
