"use client";
import { api, money } from "@/lib/api";
import { useApp } from "@/lib/store";

export default function Cart() {
  const { session, cart, setCart } = useApp();
  if (!session) return null;
  const remove = async (id: string) => setCart(await api.removeItem(session, id));
  const plus = async (id: string) => { try { setCart(await api.addItem(session, id, 1, "scan")); } catch {} };
  if (!cart || cart.items.length === 0) return <div className="p-6 text-center text-zinc-500 text-sm">Your cart is empty. Scan an item or ask the assistant.</div>;
  return (
    <div className="p-3 space-y-2">
      {cart.items.map((i) => (
        <div key={i.product_id} className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-3 flex items-center gap-3">
          <div className="flex-1">
            <div className="text-sm font-semibold">{i.name}</div>
            <div className="text-xs text-zinc-500">{money(i.unit_price)} × {i.qty} · added by {i.via}</div>
          </div>
          <div className="font-semibold text-sm">{money(i.unit_price * i.qty)}</div>
          <button onClick={() => plus(i.product_id)} className="w-8 h-8 rounded-full border text-lg leading-none">+</button>
          <button onClick={() => remove(i.product_id)} className="w-8 h-8 rounded-full border text-red-600 text-lg leading-none">×</button>
        </div>
      ))}
      <div className="text-sm text-right space-y-1 pt-2">
        <div>Subtotal <b>{money(cart.subtotal)}</b></div>
        {cart.savings > 0 && <div className="text-emerald-600">Savings {money(cart.savings)}</div>}
        <div className="text-lg">Total <b>{money(cart.total)}</b></div>
      </div>
    </div>
  );
}
