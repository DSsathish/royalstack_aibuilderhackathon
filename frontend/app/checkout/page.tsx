"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { QRCodeSVG } from "qrcode.react";
import { ApiError, Order, api, money } from "@/lib/api";
import { freshIdToken } from "@/lib/firebase";
import { useApp } from "@/lib/store";
import { IconCheck } from "@/components/Icons";
import PhoneSignIn from "@/components/PhoneSignIn";

declare global { interface Window { Razorpay?: new (o: Record<string, unknown>) => { open(): void } } }

export default function Checkout() {
  const router = useRouter();
  const { session, cart, setCart } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [order, setOrder] = useState<Order | null>(null);
  const [verifying, setVerifying] = useState(false);          // code step before points can be spent
  const [token, setToken] = useState<string | null>(null);     // fresh token after that step
  const [usePoints, setUsePoints] = useState(0);

  useEffect(() => { if (!session) router.replace("/"); else api.cart(session).then(setCart).catch(() => {}); }, [session, router, setCart]);

  const balance = cart?.points_balance ?? 0;
  const maxPoints = Math.min(balance, Math.floor(cart?.total ?? 0));
  const canUsePoints = balance >= 50 && maxPoints >= 50;
  const pointsApplied = token && usePoints >= 50 ? Math.min(usePoints, maxPoints) : 0;   // under 50 applies nothing, and shows nothing
  const due = Math.max(0, (cart?.total ?? 0) - pointsApplied);

  async function pay() {
    if (!session) return;
    setBusy(true); setError("");
    try {
      const intent = await api.checkoutIntent(session, pointsApplied >= 50 ? pointsApplied : 0, token ?? undefined);
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
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 403 && token) { setToken(null); setUsePoints(0); setError("Your verification expired. Tap Use points to verify again."); }
      else setError(err.message);
    }
    setBusy(false);
  }

  if (!session) return null;
  if (order) return <Receipt order={order} />;
  return (
    <main className="flex-1 p-4 space-y-4 max-w-md mx-auto w-full">
      <div><div className="eyebrow">Self-checkout</div><h1 className="text-2xl font-semibold">Review and pay</h1></div>
      <div className="card divide-y divide-line">
        {cart?.items.map((i) => (
          <div key={i.product_id} className="flex justify-between p-3 text-sm"><span>{i.name} <span className="text-muted">× {i.qty}</span></span><span className="mono">{money(i.unit_price * i.qty)}</span></div>
        ))}
        <div className="p-3 receipt-edge space-y-1 text-sm">
          {cart && cart.savings > 0 && <div className="flex justify-between text-good"><span>Savings vs MRP</span><span className="mono">{money(cart.savings)}</span></div>}
          {cart?.discounts?.map((d) => <div key={d.offer_id} className="flex justify-between text-good"><span>{d.name}</span><span className="mono">−{money(d.amount)}</span></div>)}
          {pointsApplied >= 50 && <div className="flex justify-between text-good"><span>Points used ({pointsApplied})</span><span className="mono">−{money(pointsApplied)}</span></div>}
          <div className="flex justify-between text-lg font-semibold"><span>Total</span><span className="mono">{money(due)}</span></div>
        </div>
      </div>
      {canUsePoints && !verifying && !token && (
        <div className="card p-3 text-sm flex items-center gap-3">
          <div className="flex-1">You have <b>{balance} points</b> worth {money(balance)}. Use up to {maxPoints} on this bill.</div>
          <button onClick={() => setVerifying(true)} className="btn btn-ghost py-2">Use points</button>
        </div>
      )}
      {verifying && (
        <div className="card p-4 space-y-2">
          <div className="eyebrow">Confirm it is you</div>
          <PhoneSignIn reverify onDone={async () => { setToken(await freshIdToken()); setUsePoints(maxPoints); setVerifying(false); }} onSkip={() => setVerifying(false)} />
        </div>
      )}
      {token && canUsePoints && (
        <label className="card p-3 text-sm flex items-center gap-3">
          <span className="flex-1">Points to use (50 to {maxPoints})</span>
          <input type="number" min={50} max={maxPoints} value={usePoints} onChange={(e) => setUsePoints(Number(e.target.value))} className="field w-28 py-1.5 mono" />
          {usePoints > 0 && usePoints < 50 && <span className="text-xs text-warn">Minimum 50</span>}
          <button onClick={() => { setToken(null); setUsePoints(0); }} className="btn btn-ghost py-1.5 text-xs">Remove</button>
        </label>
      )}
      {error && <div className="chip chip-bad">{error}</div>}
      <button onClick={pay} disabled={busy || !cart?.count} className="btn btn-primary w-full py-3.5 text-base">{busy ? "Processing" : "Pay now"}</button>
      <p className="text-xs text-muted text-center">Sandbox payment. No real money is charged.</p>
      <button onClick={() => router.back()} className="btn btn-ghost w-full">Back</button>
    </main>
  );
}

export function Receipt({ order }: { order: Order }) {
  const exitUrl = `${typeof window !== "undefined" ? window.location.origin : ""}/exit/?r=${order.receipt_token}`;
  return (
    <main className="flex-1 p-4 space-y-4 max-w-md mx-auto w-full text-center">
      <div className="w-14 h-14 mx-auto rounded-full bg-good-soft text-good flex items-center justify-center"><IconCheck /></div>
      <div><div className="eyebrow">Paid</div><h1 className="text-3xl font-semibold mono">{money(order.total)}</h1></div>
      <p className="text-sm text-muted">Show this code at the exit.</p>
      <div className="flex justify-center"><div className="bg-white p-3 rounded-[14px]"><QRCodeSVG value={exitUrl} size={220} /></div></div>
      <div className="card text-left text-sm divide-y divide-line">
        {order.items.map((i) => <div key={i.product_id} className="flex justify-between p-3"><span>{i.name} <span className="text-muted">× {i.qty}</span></span><span className="mono">{money(i.unit_price * i.qty)}</span></div>)}
        {(order.discounts?.length > 0 || order.points_redeemed > 0) && (
          <div className="p-3 space-y-1 text-good">
            {order.discounts?.map((d) => <div key={d.offer_id} className="flex justify-between"><span>{d.name}</span><span className="mono">−{money(d.amount)}</span></div>)}
            {order.points_redeemed > 0 && <div className="flex justify-between"><span>Points used ({order.points_redeemed})</span><span className="mono">−{money(order.points_value)}</span></div>}
          </div>
        )}
        <div className="flex justify-between p-3 font-semibold receipt-edge"><span>Total</span><span className="mono">{money(order.total)}</span></div>
        {order.points_earned > 0 && <div className="p-3 text-xs text-muted">You earned {order.points_earned} reward point{order.points_earned === 1 ? "" : "s"} on this bill.</div>}
      </div>
      <p className="text-xs text-muted mono">Order {order.order_id.slice(0, 8)} · {order.paid_at ? new Date(order.paid_at).toLocaleString() : ""}</p>
      <a href="/shop" className="btn btn-ghost">Continue shopping</a>
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
