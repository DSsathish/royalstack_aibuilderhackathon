"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { money } from "@/lib/api";
import { useApp } from "@/lib/store";
import Modal from "./Modal";

/** Back gesture or back button on the shop screen: a friendly check before leaving, with a word about what is in the
 *  cart. Closing the tab with items in the cart gets the browser's own prompt (its wording cannot be customised). */
export default function LeaveGuard({ storeName }: { storeName: string }) {
  const router = useRouter();
  const cart = useApp((s) => s.cart);
  const [open, setOpen] = useState(false);
  const leaving = useRef(false);
  useEffect(() => {
    history.pushState({ rsGuard: true }, "");
    const onPop = () => { if (leaving.current) return; setOpen(true); history.pushState({ rsGuard: true }, ""); };
    const onUnload = (e: BeforeUnloadEvent) => { if ((useApp.getState().cart?.count ?? 0) > 0) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("popstate", onPop);
    window.addEventListener("beforeunload", onUnload);
    return () => { window.removeEventListener("popstate", onPop); window.removeEventListener("beforeunload", onUnload); };
  }, []);
  if (!open) return null;
  const count = cart?.count ?? 0;
  const leave = () => { leaving.current = true; setOpen(false); router.push("/"); };
  return (
    <Modal title={count > 0 ? "Leave with items in your cart?" : `Leave ${storeName}?`} onClose={() => setOpen(false)}>
      <div className="space-y-4 text-sm">
        {count > 0
          ? <p>You have {count} item{count === 1 ? "" : "s"} worth {money(cart?.total ?? 0)} waiting. They stay in your cart, so you can pick up where you left off whenever you come back.</p>
          : <p>Your visit ends here. Come back any time, the assistant will be ready for you.</p>}
        <div className="flex flex-col sm:flex-row gap-2 sm:justify-end">
          <button type="button" onClick={leave} className="btn btn-ghost py-2.5">{count > 0 ? "Leave for now" : "Leave"}</button>
          <button type="button" onClick={() => setOpen(false)} className="btn btn-primary py-2.5">{count > 0 ? "Stay and check out" : "Stay"}</button>
        </div>
      </div>
    </Modal>
  );
}
