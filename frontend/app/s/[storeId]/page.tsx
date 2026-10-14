"use client";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, entranceParams } from "@/lib/api";
import { useApp } from "@/lib/store";

function Enter() {
  const { storeId } = useParams<{ storeId: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const { session, setSession } = useApp();
  const [error, setError] = useState("");
  const p = useMemo(() => entranceParams("?" + search.toString()), [search]);

  useEffect(() => {
    if (!p) return;
    (async () => {
      try {
        if (session && session.store_id === storeId && session.mode === "instore" && p.aisle) {
          setSession(await api.setAisle(session, p.aisle));          // aisle QR inside an existing visit
        } else {
          setSession(await api.enterStore(storeId, p.token, p.aisle));
        }
        router.replace("/shop");
      } catch (e) { setError(`This QR code is not valid for this store. (${(e as Error).message})`); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storeId]);

  const msg = !p ? "Scan the QR code at the store entrance to start." : error || "Opening your store session…";
  return <main className="flex-1 flex items-center justify-center p-6 text-center text-zinc-600">{msg}</main>;
}

export default function Page() { return <Suspense><Enter /></Suspense>; }
