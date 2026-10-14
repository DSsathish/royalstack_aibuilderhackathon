"use client";
import Link from "next/link";
import { money } from "@/lib/api";
import { useApp } from "@/lib/store";

export default function TotalBar() {
  const { cart, store } = useApp();
  const count = cart?.count ?? 0;
  const limit = store?.self_checkout_item_limit ?? 15;
  const lines = cart?.items.length ?? 0;
  return (
    <div className="sticky bottom-14 z-10 mx-3 rounded-xl bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 px-4 py-2 flex items-center justify-between shadow-lg">
      <div className="text-sm">
        <div><b>{count}</b> item{count === 1 ? "" : "s"} · <b>{money(cart?.total ?? 0)}</b></div>
        {(cart?.savings ?? 0) > 0 && <div className="text-xs opacity-70">You save {money(cart!.savings)}</div>}
        {lines >= limit && <div className="text-xs text-amber-400 dark:text-amber-600">Self-checkout limit reached ({limit} lines)</div>}
      </div>
      <Link href="/checkout" aria-disabled={count === 0} className={`rounded-lg px-4 py-2 text-sm font-semibold ${count ? "bg-emerald-500 text-white" : "bg-zinc-600 text-zinc-300 pointer-events-none"}`}>Checkout</Link>
    </div>
  );
}
