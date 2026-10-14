"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Order, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import { Receipt } from "../../checkout/page";

function Load() {
  const { orderId } = useParams<{ orderId: string }>();
  const session = useApp((s) => s.session);
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { if (session) api.order(session, orderId).then(setOrder).catch((e) => setError(e.message)); }, [session, orderId]);
  if (error) return <main className="p-6 text-center text-zinc-500">{error}</main>;
  return order ? <Receipt order={order} /> : <main className="p-6 text-center text-zinc-500">Loading receipt…</main>;
}

export default function ReceiptPage() { return <Suspense><Load /></Suspense>; }
