"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api";
import { useApp } from "@/lib/store";
import Chat from "@/components/Chat";
import Scanner from "@/components/Scanner";
import Cart from "@/components/Cart";
import StoreMap from "@/components/StoreMap";
import TotalBar from "@/components/TotalBar";
import { IconCart, IconChat, IconMap, IconScan } from "@/components/Icons";

type Tab = "chat" | "scan" | "cart" | "map";

export default function Shop() {
  const router = useRouter();
  const { session, store, setStore, setCart, highlight, setSession } = useApp();
  const [tab, setTab] = useState<Tab>("chat");
  const [photo, setPhoto] = useState<File | null>(null);

  useEffect(() => {
    if (!session) { router.replace("/"); return; }
    const expired = (e: unknown) => { if (e instanceof ApiError && (e.status === 401 || e.status === 404)) setSession(null); };
    api.store(session.store_id).then(setStore).catch(expired);
    api.cart(session).then(setCart).catch(expired);
  }, [session, router, setStore, setCart, setSession]);

  if (!session) return null;
  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "chat", label: "Assistant", icon: <IconChat /> }, { id: "scan", label: "Scan", icon: <IconScan /> },
    { id: "cart", label: "Cart", icon: <IconCart /> }, ...(session.mode === "instore" ? [{ id: "map" as Tab, label: "Map", icon: <IconMap /> }] : []),
  ];
  return (
    <div className="flex flex-col h-dvh">
      <div className="flex-1 overflow-hidden">
        {tab === "chat" && <ChatWithPhoto photo={photo} clear={() => setPhoto(null)} />}
        {tab === "scan" && <Scanner onPhoto={(f) => { setPhoto(f); setTab("chat"); }} />}
        {tab === "cart" && <div className="overflow-y-auto h-full"><Cart /></div>}
        {tab === "map" && store && (
          <div className="p-3 space-y-2">
            <div className="eyebrow px-1">Store map</div>
            <StoreMap aisles={store.floor_map} target={highlight} youAreHere={session.aisle_hint} />
            <p className="text-xs text-muted text-center">{highlight ? `Highlighted: aisle ${highlight.aisle}, bay ${highlight.bay}, ${highlight.side} side` : "Ask the assistant where a product is, or scan an aisle QR to update your position."}</p>
          </div>
        )}
      </div>
      {session.mode !== "owner" && <TotalBar />}
      <nav className="sticky bottom-0 grid grid-flow-col auto-cols-fr border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={`py-2 text-[11px] font-semibold flex flex-col items-center gap-0.5 ${tab === t.id ? "text-ink" : "text-muted"}`}>
            <span className={`rounded-full px-3 py-0.5 ${tab === t.id ? "bg-accent-soft text-accent-ink" : ""}`}>{t.icon}</span>{t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

/** Chat, plus a one-shot photo handed over from the Scan tab. */
function ChatWithPhoto({ photo, clear }: { photo: File | null; clear: () => void }) {
  const { session, push, patch, setCart } = useApp();
  useEffect(() => {
    if (!photo || !session) return;
    clear();
    (async () => {
      push({ role: "user", text: "📷 What is this product?" });
      const id = push({ role: "assistant", text: "", status: "Looking at your photo…" });
      let buffer = "";
      try {
        for await (const e of api.chat(session, "What is this product? Find it in the catalog.", photo)) {
          if (e.type === "token") { buffer += e.text; patch(id, { text: buffer, status: undefined }); }
          else if (e.type === "done") patch(id, { text: e.text || buffer, status: undefined });
          else if (e.type === "action" && e.name === "show_products") patch(id, { products: e.data.products as never });
          else if (e.type === "action" && e.name === "cart_updated") setCart(await api.cart(session));
        }
      } catch { patch(id, { text: "Could not analyse the photo. Please try again.", status: undefined }); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photo]);
  return <Chat />;
}
