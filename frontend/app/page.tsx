"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session, StoreLite, api, loadSession } from "@/lib/api";
import { useApp } from "@/lib/store";
import { IconBag, IconStore } from "@/components/Icons";
import Lottie from "@/components/Lottie";

/** Two front doors (docs/lld/online-shop.md): the store visit, started by the entrance code, and the online shop. */
export default function Home() {
  const router = useRouter();
  const setSession = useApp((s) => s.setSession);
  const [saved, setSaved] = useState<Session | null>(null);
  const [stores, setStores] = useState<StoreLite[] | null>(null);
  const [picking, setPicking] = useState(false);
  const [hint, setHint] = useState(false);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setSaved(loadSession()), 0);            // after hydration: the saved visit lives in this browser only
    api.stores().then(setStores).catch(() => setStores([]));
    return () => clearTimeout(t);
  }, []);

  async function shopOnline(store_id?: string) {
    const list = stores ?? [];
    const id = store_id ?? (list.length === 1 ? list[0].store_id : undefined);
    if (!id) { setPicking(true); return; }
    setBusy(id); setErr("");
    try { setSession(await api.onlineSession(id)); router.push("/shop"); }
    catch (e) { setErr(`Could not open the shop: ${(e as Error).message}`); }
    setBusy("");
  }
  const storeVisit = () => { if (saved?.mode === "instore") router.push("/shop"); else setHint(true); };

  return (
    <main className="reveal-stagger flex-1 flex flex-col items-center justify-center gap-6 px-6 py-10 text-center">
      <Lottie slot="hero" fallback={<div className="w-16 h-16 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><IconStore /></div>} />
      <div className="space-y-2 max-w-sm">
        <div className="eyebrow">Royal Stack</div>
        <h1 className="text-3xl font-semibold">Shop with an assistant that knows every shelf</h1>
        <p className="text-muted">Ask by voice or text in your language, see where things are, pay without the queue.</p>
      </div>
      <div className="grid gap-3 w-full max-w-sm">
        <button type="button" onClick={storeVisit} className="btn btn-primary py-3 text-base"><IconStore className="w-5 h-5" /> {saved?.mode === "instore" ? "Continue the store visit" : "Start the store visit"}</button>
        <button type="button" onClick={() => shopOnline()} disabled={busy !== "" || stores === null} className="btn btn-ink py-3 text-base"><IconBag className="w-5 h-5" /> {busy ? "Opening" : "Shop online"}</button>
      </div>
      {hint && (
        <div className="card p-4 text-sm max-w-sm text-left space-y-1">
          <div className="font-semibold">In the shop? Scan the code at the entrance.</div>
          <p className="text-muted">Your phone camera opens the visit here, with the map and scan-as-you-go. No app to install.</p>
        </div>
      )}
      {picking && stores && stores.length > 0 && (
        <div className="card p-3 w-full max-w-sm text-left space-y-1">
          <div className="eyebrow px-1">Choose a shop</div>
          {stores.map((s) => (
            <button key={s.store_id} type="button" onClick={() => shopOnline(s.store_id)} disabled={busy !== ""} className="w-full text-left px-3 py-2 rounded-xl hover:bg-surface-2">
              <div className="font-semibold">{s.name}</div>
              <div className="text-xs text-muted">{[s.city, s.tagline].filter(Boolean).join(" · ")}</div>
            </button>
          ))}
        </div>
      )}
      {stores && stores.length === 0 && <p className="text-sm text-bad">No shop is open online right now.</p>}
      {err && <p className="text-sm text-bad">{err}</p>}
      <p className="text-sm text-muted">Shop owner? <Link href="/owner/" className="text-accent font-semibold">Register your shop or sign in</Link></p>
    </main>
  );
}
