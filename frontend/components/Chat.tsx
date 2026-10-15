"use client";
import { useEffect, useRef, useState } from "react";
import { listenOnce } from "@/lib/voice";
import { LiveFrame, LiveState, liveSupported, startLive } from "@/lib/live";
import { Product, api } from "@/lib/api";
import { Msg, sayAloud, useApp } from "@/lib/store";
import { UiEvent } from "@/lib/sse";
import Avatar from "./Avatar";
import ProductCard from "./ProductCard";
import StoreMap from "./StoreMap";
import Link from "next/link";

const STATUS: Record<string, string> = {
  search_products: "Checking the shelves…", navigate_to: "Finding the aisle…", add_to_cart: "Adding to your cart…",
  suggest_substitutes: "Looking for alternatives…", view_cart: "Opening your cart…", start_checkout: "Preparing checkout…",
};

export default function Chat() {
  const { session, store, messages, push, patch, setCart, setHighlight, language, setLanguage, speak, setSpeak, setAvatar } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [voiceOn, setVoiceOn] = useState(false);
  const [voiceState, setVoiceState] = useState<"listening" | "thinking" | "speaking" | "">("");
  const voiceRef = useRef(false);
  const media = useRef<{ stream: MediaStream; ctx: AudioContext } | null>(null);
  const [live, setLive] = useState<LiveState>("closed");
  const [canLive, setCanLive] = useState(false);
  useEffect(() => { setTimeout(() => setCanLive(liveSupported()), 0); }, []);
  const liveStop = useRef<(() => void) | null>(null);
  const liveConnecting = useRef(false);
  const liveMsg = useRef<{ user: number | null; assistant: number | null }>({ user: null, assistant: null });
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function consume(stream: AsyncGenerator<UiEvent>, userMsgId?: number) {
    const id = push({ role: "assistant", text: "" });
    let buffer = "";
    setAvatar("thinking");
    try {
      for await (const e of stream) {
        if (e.type === "transcript" && userMsgId) patch(userMsgId, { text: e.text });
        else if (e.type === "status") patch(id, { status: STATUS[e.tool] ?? "Working…" });
        else if (e.type === "token") { buffer += e.text; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "done") { buffer = e.text || buffer; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "action") handleAction(e.name, e.data, id);
        else if (e.type === "error") { buffer = ""; patch(id, { text: e.text, status: undefined }); }
      }
      if ((speak || voiceRef.current) && buffer) { setAvatar("speaking"); sayAloud(buffer, language); setTimeout(() => setAvatar("idle"), 2500); }
      else setAvatar("idle");
    } catch (err) {
      patch(id, { text: `Assistant unavailable: ${(err as Error).message}`, status: undefined });
      setAvatar("idle");
    }
  }

  function handleAction(name: string, data: Record<string, unknown>, id: number) {
    if (name === "show_products") patch(id, { products: (data.products as Product[]) ?? [] });
    else if (name === "show_product") patch(id, { products: [data as unknown as Product] });
    else if (name === "highlight_map" && data.aisle) { const loc = data as Msg["map"]; setHighlight(loc!); patch(id, { map: loc }); }
    else if (name === "cart_updated" && data.cart) refreshCart();
    else if (name === "checkout_ready" && data.ok) patch(id, { checkout: true });
  }

  async function refreshCart() { if (session) setCart(await api.cart(session)); }

  async function send(message: string, image?: Blob) {
    if (!session || (!message.trim() && !image)) return;
    setBusy(true); setText("");
    push({ role: "user", text: message || "📷 (photo)" });
    await consume(api.chat(session, message || "What is this product?", image));
    setBusy(false);
  }

  async function addFromCard(p: Product) {
    if (!session) return;
    try { setCart(await api.addItem(session, p.product_id, 1, "chat")); } catch (e) { push({ role: "assistant", text: `Could not add ${p.name}: ${(e as Error).message}` }); }
  }
  function whereIs(p: Product) { send(`Where is ${p.name}?`); }

  /** Hands-free conversation: listen -> transcribe and answer -> speak -> listen again, until stopped. */
  async function toggleVoice() {
    if (voiceRef.current) { stopVoice(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      media.current = { stream, ctx };
    } catch { push({ role: "assistant", text: "Microphone not available. Please type instead." }); return; }
    voiceRef.current = true; setVoiceOn(true);
    if (messages.length === 0) push({ role: "assistant", text: "I'm listening. Ask me anything about the store, in English, Tamil or Hindi." });
    while (voiceRef.current && media.current) {
      setVoiceState("listening"); setAvatar("listening");
      const heard = await listenOnce(media.current.stream, media.current.ctx, () => !voiceRef.current);
      if (!voiceRef.current) break;
      if (!heard) continue;                       // nothing said: keep listening
      setVoiceState("thinking"); setBusy(true);
      const userId = push({ role: "user", text: "🎤 …" });
      if (session) await consume(api.audio(session, heard.blob), userId);   // speaks the reply before returning
      setBusy(false);
    }
    setVoiceState("");
  }

  /** Real-time speech-to-speech on the Gemini Live API. Transcripts and tool actions flow into the same chat. */
  async function toggleLive() {
    if (liveStop.current) { liveStop.current(); return; }
    if (liveConnecting.current || !session) return;
    if (voiceRef.current) stopVoice();
    liveConnecting.current = true;
    let closedEarly = false;
    try {
      const stop = await startLive(session.session_id, {
        onState: (st) => { setLive(st); setAvatar(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "connecting" ? "thinking" : "idle"); if (st === "closed") { closedEarly = true; liveStop.current = null; liveMsg.current = { user: null, assistant: null }; } },
        onFrame: (f: LiveFrame) => {
          if (f.type === "transcript") {
            const slot = f.role;
            const cur = liveMsg.current[slot];
            if (cur === null) liveMsg.current[slot] = push({ role: slot, text: f.text });
            else patch(cur, { text: (useApp.getState().messages.find((m) => m.id === cur)?.text ?? "") + f.text });
            if (slot === "user") liveMsg.current.assistant = null;   // a new user utterance starts a new assistant bubble
          } else if (f.type === "turn_complete") {
            liveMsg.current = { user: null, assistant: null };
          } else if (f.type === "action") {
            const id = liveMsg.current.assistant ?? (liveMsg.current.assistant = push({ role: "assistant", text: "" }));
            handleAction(f.name, f.data, id);
          } else if (f.type === "error") {
            push({ role: "assistant", text: f.text });
          }
        },
      });
      if (closedEarly) stop(); else liveStop.current = stop;   // socket refused during connect: do not keep a dead stop
    } catch (e) { push({ role: "assistant", text: `Live voice could not start: ${(e as Error).message}` }); liveStop.current = null; setLive("closed"); }
    liveConnecting.current = false;
  }

  function stopVoice() {
    voiceRef.current = false; setVoiceOn(false); setVoiceState("");
    window.speechSynthesis?.cancel();
    media.current?.stream.getTracks().forEach((t) => t.stop());
    media.current?.ctx.close();
    media.current = null;
    setAvatar("idle");
  }

  useEffect(() => () => { if (voiceRef.current) stopVoice(); liveStop.current?.(); }, []);   // leaving the tab ends the conversation

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 px-4 py-2 border-b border-zinc-200 dark:border-zinc-800">
        <Avatar />
        <div className="flex-1">
          <div className="font-semibold text-sm">{store?.name ?? "Store assistant"}</div>
          <div className="text-xs text-zinc-500">{session?.mode === "instore" ? "In-store assistant" : "Shopping assistant"}</div>
        </div>
        <select value={language} onChange={(e) => setLanguage(e.target.value as never)} className="text-xs rounded-md border border-zinc-300 dark:border-zinc-700 bg-transparent px-1 py-1">
          <option value="auto">Auto</option><option value="en">English</option><option value="ta">தமிழ்</option><option value="hi">हिन्दी</option>
        </select>
        <button onClick={() => setSpeak(!speak)} title="Read aloud" className="text-lg">{speak ? "🔊" : "🔇"}</button>
        {canLive && (
          <button onClick={toggleLive} className={`text-xs rounded-full px-3 py-1.5 font-semibold ${live !== "closed" ? "bg-red-500 text-white" : "bg-emerald-600 text-white"}`}>
            {live === "closed" ? "Talk live" : live === "connecting" ? "Connecting…" : "End"}
          </button>
        )}
      </header>
      {live !== "closed" && (
        <div className="flex items-center justify-between px-4 py-1.5 text-xs bg-emerald-50 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-200">
          <span>{live === "listening" ? "Live · listening, just talk. You can interrupt." : live === "speaking" ? "Live · speaking" : "Live · connecting"}</span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-sm text-zinc-500 space-y-2">
            <p>Ask me anything about the store. Try:</p>
            {["Where is atta?", "பால் எங்கே இருக்கு?", "Do you have oat milk?", "Something for a headache"].map((q) => (
              <button key={q} onClick={() => send(q)} className="block rounded-full border border-zinc-300 dark:border-zinc-700 px-3 py-1 text-left">{q}</button>
            ))}
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
            <div className={`rounded-2xl px-3 py-2 text-sm max-w-[85%] whitespace-pre-wrap ${m.role === "user" ? "bg-emerald-600 text-white" : "bg-zinc-100 dark:bg-zinc-800"}`}>
              {m.text || (m.status ? <span className="text-zinc-500 italic">{m.status}</span> : <span className="text-zinc-400">…</span>)}
            </div>
            {m.products && m.products.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {m.products.map((p) => <ProductCard key={p.product_id} p={p} onAdd={session?.mode !== "owner" ? addFromCard : undefined} onWhere={session?.mode === "instore" ? whereIs : undefined} />)}
              </div>
            )}
            {m.map && store && <div className="max-w-[85%]"><StoreMap aisles={store.floor_map} target={m.map} youAreHere={session?.aisle_hint} compact /></div>}
            {m.checkout && <Link href="/checkout" className="inline-block rounded-lg bg-emerald-600 text-white text-sm px-4 py-2">Go to checkout</Link>}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      {voiceOn && (
        <div className="flex items-center justify-between px-4 py-1.5 text-xs bg-emerald-50 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-200">
          <span>{voiceState === "listening" ? "Listening… speak now, pause when done" : voiceState === "thinking" ? "Thinking…" : voiceState === "speaking" ? "Speaking…" : "Voice conversation on"}</span>
          <button onClick={stopVoice} className="underline">End</button>
        </div>
      )}
      <form onSubmit={(e) => { e.preventDefault(); send(text); }} className="flex items-center gap-2 px-3 py-2 border-t border-zinc-200 dark:border-zinc-800">
        <label className="text-xl cursor-pointer" title="Send a photo of a product">📷
          <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) send(text, f); e.target.value = ""; }} />
        </label>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about products, prices, aisles…" className="flex-1 rounded-full border border-zinc-300 dark:border-zinc-700 bg-transparent px-4 py-2 text-sm" disabled={busy} />
        <button type="button" onClick={toggleVoice} className={`text-xl rounded-full w-10 h-10 ${voiceOn ? "bg-red-500 text-white animate-pulse" : "bg-zinc-200 dark:bg-zinc-700"}`} title={voiceOn ? "End voice conversation" : "Start voice conversation"}>{voiceOn ? "■" : "🎤"}</button>
        <button type="submit" disabled={busy || !text.trim()} className="rounded-full bg-emerald-600 disabled:bg-zinc-300 text-white w-10 h-10">➤</button>
      </form>
    </div>
  );
}
