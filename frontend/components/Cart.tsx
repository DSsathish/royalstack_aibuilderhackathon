"use client";
import { api, money } from "@/lib/api";
import { useApp } from "@/lib/store";
import { IconClose, IconMinus, IconPlus } from "./Icons";

export default function Cart() {
  const { session, cart, setCart } = useApp();
  if (!session) return null;
  const remove = async (id: string) => setCart(await api.removeItem(session, id));
  const plus = async (id: string) => { try { setCart(await api.addItem(session, id, 1, "scan")); } catch {} };
  const minus = async (id: string, qty: number) => { try { setCart(await api.setQty(session, id, qty - 1)); } catch {} };
  if (!cart || cart.items.length === 0) return (
    <div className="p-8 text-center space-y-2">
      <div className="display text-xl font-semibold">Your cart is empty</div>
      <p className="text-muted text-sm">{session.mode === "online" ? "Browse the shop or ask the assistant to add something." : "Scan an item or ask the assistant to add one."}</p>
    </div>
  );
  return (
    <div className="p-3 space-y-2">
      <div className="eyebrow px-1">Receipt</div>
      <div className="card divide-y divide-line">
        {cart.items.map((i) => (
          <div key={i.product_id} className="p-3 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate">{i.name}</div>
              <div className="text-xs text-muted mono">{money(i.unit_price)} each{session.mode === "instore" ? ` · ${i.via}` : ""}</div>
            </div>
            <div className="mono text-sm">{money(i.unit_price * i.qty)}</div>
            <div className="flex items-center gap-1">
              <button onClick={() => minus(i.product_id, i.qty)} className="btn btn-ghost w-8 h-8 p-0 rounded-full" aria-label="One less"><IconMinus className="w-4 h-4" /></button>
              <span className="mono text-sm w-5 text-center" aria-live="polite">{i.qty}</span>
              <button onClick={() => plus(i.product_id)} className="btn btn-ghost w-8 h-8 p-0 rounded-full" aria-label="One more"><IconPlus className="w-4 h-4" /></button>
            </div>
            <button onClick={() => remove(i.product_id)} className="btn btn-ghost w-9 h-9 p-0 rounded-full text-bad" aria-label="Remove"><IconClose className="w-4 h-4" /></button>
          </div>
        ))}
        <div className="p-3 receipt-edge space-y-1 text-sm">
          <div className="flex justify-between"><span className="text-muted">Subtotal</span><span className="mono">{money(cart.subtotal)}</span></div>
          {cart.savings > 0 && <div className="flex justify-between text-good"><span>Savings vs MRP</span><span className="mono">{money(cart.savings)}</span></div>}
          {cart.discounts?.map((d) => <div key={d.offer_id} className="flex justify-between text-good"><span>{d.name}</span><span className="mono">−{money(d.amount)}</span></div>)}
          <div className="flex justify-between text-lg font-semibold"><span>Total</span><span className="mono">{money(cart.total)}</span></div>
          {cart.points_balance != null && cart.points_balance >= 50 && <div className="text-xs text-muted">You have {cart.points_balance} points worth {money(cart.points_balance)}. Use them at checkout.</div>}
        </div>
      </div>
    </div>
  );
}
