"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, entranceParams } from "@/lib/api";
import { useApp } from "@/lib/store";

/** Entrance and aisle QR codes open /enter?store=<id>&t=<token>[&aisle=A3]. */
function Enter() {
  const search = useSearchParams();
  const router = useRouter();
  const { session, setSession, updateSession } = useApp();
  const [error, setError] = useState("");
  const p = useMemo(() => entranceParams("?" + search.toString()), [search]);

  useEffect(() => {
    if (!p) return;
    (async () => {
      try {
        if (session && session.store_id === p.store && session.mode === "instore" && p.aisle) {
          updateSession(await api.setAisle(session, p.aisle));       // aisle QR inside an existing visit
        } else {
          setSession(await api.enterStore(p.store, p.token, p.aisle));
        }
        router.replace("/shop");
      } catch (e) { setError(`This QR code is not valid for this store. (${(e as Error).message})`); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p?.store, p?.token, p?.aisle]);

  const msg = !p ? "Scan the QR code at the store entrance to start." : error || "Opening your store session…";
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
      <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" aria-hidden />
      <p className="text-muted">{msg}</p>
    </main>
  );
}

export default function Page() { return <Suspense><Enter /></Suspense>; }
