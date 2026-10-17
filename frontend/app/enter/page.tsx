"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Session, api, entranceParams } from "@/lib/api";
import { firstAuthState } from "@/lib/firebase";
import { linkShopper } from "@/lib/me";
import { useApp } from "@/lib/store";
import PhoneSignIn from "@/components/PhoneSignIn";

/** Entrance and aisle QR codes open /enter?store=<id>&t=<token>[&aisle=A3]. */
function Enter() {
  const search = useSearchParams();
  const router = useRouter();
  const { session, setSession, updateSession } = useApp();
  const [error, setError] = useState("");
  const [offer, setOffer] = useState<Session | null>(null);     // a new visit opened; offer sign-in before the shop
  const p = useMemo(() => entranceParams("?" + search.toString()), [search]);

  useEffect(() => {
    if (!p) return;
    (async () => {
      try {
        if (session && session.store_id === p.store && session.mode === "instore" && p.aisle) {
          updateSession(await api.setAisle(session, p.aisle));       // aisle QR inside an existing visit
          router.replace("/shop"); return;
        }
        const s = await api.enterStore(p.store, p.token, p.aisle);
        setSession(s);
        const u = await firstAuthState();
        if (u?.phoneNumber) { await linkShopper(s).catch(() => {}); router.replace("/shop"); }   // returning shopper on this phone
        else setOffer(s);
      } catch (e) { setError(`This QR code is not valid for this store. (${(e as Error).message})`); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p?.store, p?.token, p?.aisle]);

  if (offer) return (
    <main className="reveal flex-1 flex flex-col items-center justify-center p-6">
      <div className="card p-5 w-full max-w-sm space-y-3">
        <div className="eyebrow">Welcome</div>
        <h1 className="text-xl font-semibold">Sign in for offers and your history?</h1>
        <p className="text-sm text-muted">Optional. Only the last four digits of your number are ever shown, and you can download or delete everything from your profile.</p>
        <PhoneSignIn onDone={async () => { await linkShopper(offer); router.replace("/shop"); }} onSkip={() => router.replace("/shop")} />
      </div>
    </main>
  );
  const msg = !p ? "Scan the QR code at the store entrance to start." : error || "Opening your store session…";
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
      <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" aria-hidden />
      <p className="text-muted">{msg}</p>
    </main>
  );
}

export default function Page() { return <Suspense><Enter /></Suspense>; }
