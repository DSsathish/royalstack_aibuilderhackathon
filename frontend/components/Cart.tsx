"use client";
import { api, money } from "@/lib/api";
import { useApp } from "@/lib/store";
import { IconClose, IconPlus } from "./Icons";

export default function Cart() {
  const { session, cart, setCart } = useApp();
  if (!session) return null;
  const remove = async (id: string) => setCart(await api.removeItem(session, id));
  const plus = async (id: string) => { try { setCart(await api.addItem(session, id, 1, "scan")); } catch {} };
  if (!cart || cart.items.length === 0) return (
    <div className="p-8 text-center space-y-2">
      <div className="display text-xl font-semibold">Your cart is empty</div>
      <p className="text-muted text-sm">Scan an item or ask the assistant to add one.</p>
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
              <div className="text-xs text-muted mono">{money(i.unit_price)} × {i.qty} · {i.via}</div>
            </div>
            <div className="mono text-sm">{money(i.unit_price * i.qty)}</div>
            <button onClick={() => plus(i.product_id)} className="btn btn-ghost w-9 h-9 p-0 rounded-full" aria-label="Add one"><IconPlus className="w-4 h-4" /></button>
            <button onClick={() => remove(i.product_id)} className="btn btn-ghost w-9 h-9 p-0 rounded-full text-bad" aria-label="Remove"><IconClose className="w-4 h-4" /></button>
          </div>
        ))}
        <div className="p-3 receipt-edge space-y-1 text-sm">
          <div className="flex justify-between"><span className="text-muted">Subtotal</span><span className="mono">{money(cart.subtotal)}</span></div>
          {cart.savings > 0 && <div className="flex justify-between text-good"><span>Savings</span><span className="mono">{money(cart.savings)}</span></div>}
          <div className="flex justify-between text-lg font-semibold"><span>Total</span><span className="mono">{money(cart.total)}</span></div>
        </div>
      </div>
    </div>
  );
}
