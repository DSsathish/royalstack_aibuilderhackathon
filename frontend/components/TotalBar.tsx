"use client";
import Link from "next/link";
import { money } from "@/lib/api";
import { useApp } from "@/lib/store";

/** Running receipt, always visible: the lesson from cashierless stores is that shoppers want to see the bill as it grows. */
export default function TotalBar() {
  const { cart, store } = useApp();
  const count = cart?.count ?? 0;
  const limit = store?.self_checkout_item_limit ?? 15;
  const lines = cart?.items.length ?? 0;
  return (
    <div className="sticky bottom-14 z-10 mx-3 card receipt-edge px-4 py-2.5 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="eyebrow">Your receipt</div>
        <div className="mono text-base leading-tight">{count} item{count === 1 ? "" : "s"} · {money(cart?.total ?? 0)}</div>
        {((cart?.savings ?? 0) > 0 || (cart?.discount_total ?? 0) > 0) && <div className="text-xs text-good">You save {money((cart?.savings ?? 0) + (cart?.discount_total ?? 0))}{(cart?.discount_total ?? 0) > 0 ? " with offers" : ""}</div>}
        {lines >= limit && <div className="text-xs text-warn">Self-checkout limit reached ({limit} lines)</div>}
      </div>
      <Link href="/checkout" aria-disabled={count === 0} className={`btn ${count ? "btn-primary" : "btn-ghost pointer-events-none text-muted"}`}>Checkout</Link>
    </div>
  );
}
