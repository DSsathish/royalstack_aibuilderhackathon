"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Product, api } from "@/lib/api";
import { LiveFrame, LiveState, liveSupported, startLive } from "@/lib/live";
import { UiEvent } from "@/lib/sse";
import { Msg, sayAloud, useApp } from "@/lib/store";
import { listenOnce } from "@/lib/voice";
import { IconCamera, IconMic, IconSend, IconSpeaker, IconStop } from "./Icons";
import ProductCard from "./ProductCard";
import StoreMap from "./StoreMap";
import VoiceOrb, { OrbState } from "./VoiceOrb";

const STATUS: Record<string, string> = {
  search_products: "Checking the shelves", navigate_to: "Finding the aisle", add_to_cart: "Adding to your cart",
  suggest_substitutes: "Looking for alternatives", view_cart: "Opening your cart", start_checkout: "Preparing checkout",
  get_low_stock: "Checking stock levels", forecast_demand: "Reading the forecast", draft_purchase_order: "Drafting orders",
  get_anomalies: "Checking exits and counts", record_demand_signal: "Noting your request",
};
const SUGGESTIONS = ["Where is atta?", "பால் எங்கே இருக்கு?", "Do you have oat milk?", "Something for a headache"];
const OWNER_SUGGESTIONS = ["What is running low?", "How much milk will we sell this week?", "Prepare purchase orders", "Anything suspicious at the exits?"];

export default function Chat() {
  const { session, store, messages, push, patch, setCart, setHighlight, language, setLanguage, speak, setSpeak, setAvatar } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [orb, setOrb] = useState<OrbState>("idle");
  const [voiceOn, setVoiceOn] = useState(false);               // record-and-answer loop (fallback)
  const voiceRef = useRef(false);
  const media = useRef<{ stream: MediaStream; ctx: AudioContext } | null>(null);
  const [live, setLive] = useState<LiveState>("closed");       // speech-to-speech
  const [canLive, setCanLive] = useState(false);
  useEffect(() => { setTimeout(() => setCanLive(liveSupported()), 0); }, []);
  const liveStop = useRef<(() => void) | null>(null);
  const liveConnecting = useRef(false);
  const liveMsg = useRef<{ user: number | null; assistant: number | null }>({ user: null, assistant: null });
  const bottom = useRef<HTMLDivElement>(null);
  const talking = live !== "closed" || voiceOn;
  const owner = session?.mode === "owner";

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function consume(stream: AsyncGenerator<UiEvent>, userMsgId?: number) {
    const id = push({ role: "assistant", text: "" });
    let buffer = "";
    setAvatar("thinking"); setOrb("thinking");
    try {
      for await (const e of stream) {
        if (e.type === "transcript" && userMsgId) patch(userMsgId, { text: e.text });
        else if (e.type === "status") patch(id, { status: STATUS[e.tool] ?? "Working" });
        else if (e.type === "token") { buffer += e.text; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "done") { buffer = e.text || buffer; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "action") handleAction(e.name, e.data, id);
        else if (e.type === "error") { buffer = ""; patch(id, { text: e.text, status: undefined }); }
      }
      if ((speak || voiceRef.current) && buffer) {
        setAvatar("speaking"); setOrb("speaking");
        const pulse = setInterval(() => setLevel(0.35 + Math.random() * 0.4), 90);   // browser TTS exposes no signal; simulate cadence
        await sayAloud(buffer, language);
        clearInterval(pulse); setLevel(0);
      }
      setAvatar("idle"); setOrb(voiceRef.current ? "listening" : "idle");
    } catch (err) {
      patch(id, { text: `Assistant unavailable: ${(err as Error).message}`, status: undefined });
      setAvatar("idle"); setOrb("idle");
    }
  }

  function handleAction(name: string, data: Record<string, unknown>, id: number) {
    if (name === "show_products") patch(id, { products: (data.products as Product[]) ?? [], fromPhoto: photoTurn.current });
    else if (name === "show_product") patch(id, { products: [data as unknown as Product] });
    else if (name === "highlight_map" && data.aisle) { const loc = data as Msg["map"]; setHighlight(loc!); patch(id, { map: loc }); }
    else if (name === "cart_updated" && data.cart) refreshCart();
    else if (name === "checkout_ready" && data.ok) patch(id, { checkout: true });
    else if (name === "show_low_stock") patch(id, { lowStock: (data.items as Msg["lowStock"]) ?? [] });
    else if (name === "drafts_created") patch(id, { drafts: (data.drafts as Msg["drafts"]) ?? [] });
  }
  async function refreshCart() { if (session) setCart(await api.cart(session)); }

  const photoTurn = useRef(false);
  async function send(message: string, image?: Blob) {
    if (!session || (!message.trim() && !image)) return;
    setBusy(true); setText("");
    photoTurn.current = !!image;
    push({ role: "user", text: message || "Photo of a product" });
    await consume(api.chat(session, message || "What is this product?", image));
    setBusy(false);
  }
  async function addFromCard(p: Product, fromPhoto: boolean) {
    if (!session) return;
    const via = session.mode === "instore" ? "vision" : "chat";      // in store, only a confirmed photo may add
    if (session.mode === "instore" && !fromPhoto) return;
    try { setCart(await api.addItem(session, p.product_id, 1, via)); } catch (e) { push({ role: "assistant", text: `Could not add ${p.name}: ${(e as Error).message}` }); }
  }
  const whereIs = (p: Product) => send(`Where is ${p.name}?`);

  /** Speech-to-speech on the Gemini Live API. Transcripts and tool actions flow into the same thread. */
  async function toggleLive() {
    if (liveStop.current) { liveStop.current(); return; }
    if (liveConnecting.current || !session) return;
    if (voiceRef.current) stopVoice();
    liveConnecting.current = true;
    let closedEarly = false;
    try {
      const stop = await startLive(session.session_id, {
        onLevel: (l) => setLevel(l),
        onState: (st) => {
          setLive(st);
          setOrb(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "connecting" || st === "reconnecting" ? "connecting" : "idle");
          setAvatar(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "closed" ? "idle" : "thinking");
          if (st === "closed") { closedEarly = true; liveStop.current = null; liveMsg.current = { user: null, assistant: null }; setLevel(0); }
        },
        onFrame: (f: LiveFrame) => {
          if (f.type === "transcript") {
            const slot = f.role, cur = liveMsg.current[slot];
            if (cur === null) liveMsg.current[slot] = push({ role: slot, text: f.text });
            else patch(cur, { text: (useApp.getState().messages.find((m) => m.id === cur)?.text ?? "") + f.text });
            if (slot === "user") liveMsg.current.assistant = null;
          } else if (f.type === "turn_complete") liveMsg.current = { user: null, assistant: null };
          else if (f.type === "status") setOrb("thinking");      // a tool is running; the voice resumes when audio arrives
          else if (f.type === "action") { const id = liveMsg.current.assistant ?? (liveMsg.current.assistant = push({ role: "assistant", text: "" })); handleAction(f.name, f.data, id); }
          else if (f.type === "error") push({ role: "assistant", text: f.text });
        },
      });
      if (closedEarly) stop(); else liveStop.current = stop;
    } catch (e) { push({ role: "assistant", text: `Live voice could not start: ${(e as Error).message}` }); liveStop.current = null; setLive("closed"); setOrb("idle"); }
    liveConnecting.current = false;
  }

  /** Fallback: record until silence, answer, speak, listen again. Used where live audio is unsupported. */
  async function toggleVoice() {
    if (voiceRef.current) { stopVoice(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      media.current = { stream, ctx: new AudioContext() };
    } catch { push({ role: "assistant", text: "Microphone not available. Please type instead." }); return; }
    voiceRef.current = true; setVoiceOn(true);
    while (voiceRef.current && media.current) {
      setOrb("listening"); setAvatar("listening");
      const heard = await listenOnce(media.current.stream, media.current.ctx, () => !voiceRef.current, setLevel);
      if (!voiceRef.current) break;
      if (!heard) continue;
      setBusy(true);
      const userId = push({ role: "user", text: "…" });
      if (session) await consume(api.audio(session, heard.blob), userId);
      setBusy(false);
    }
  }
  function stopVoice() {
    voiceRef.current = false; setVoiceOn(false); setOrb("idle"); setLevel(0);
    window.speechSynthesis?.cancel();
    media.current?.stream.getTracks().forEach((t) => t.stop());
    media.current?.ctx.close(); media.current = null;
    setAvatar("idle");
  }
  function toggleTalk() { if (canLive) toggleLive(); else toggleVoice(); }
  function endTalk() { if (liveStop.current) liveStop.current(); if (voiceRef.current) stopVoice(); }
  useEffect(() => () => { if (voiceRef.current) stopVoice(); liveStop.current?.(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const orbCaption = live === "reconnecting" ? "Reconnecting, keep talking" : live === "connecting" ? "Connecting" : orb === "listening" ? "Listening. Just talk, interrupt any time" : orb === "speaking" ? "Speaking" : orb === "thinking" ? "Checking" : "Tap to talk";

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 px-4 pt-3 pb-2">
        <div className="flex-1 min-w-0">
          <div className="eyebrow">{owner ? "Owner assistant" : store?.brand?.tagline || (session?.mode === "instore" ? "In-store assistant" : "Shopping assistant")}</div>
          <h1 className="text-lg font-semibold leading-tight truncate">{store?.name ?? "Store"}</h1>
        </div>
        <select id="lang" value={language} onChange={(e) => setLanguage(e.target.value as never)} className="chip chip-muted bg-surface border border-line" aria-label="Language">
          <option value="auto">Auto</option><option value="en">English</option><option value="ta">தமிழ்</option><option value="hi">हिन्दी</option>
        </select>
        <button onClick={() => setSpeak(!speak)} title={speak ? "Mute read-aloud" : "Read replies aloud"} className="text-muted"><IconSpeaker muted={!speak} /></button>
      </header>

      {/* voice stage: the orb is the centrepiece while talking, a compact tap target otherwise */}
      <div className={`flex flex-col items-center transition-all ${talking ? "py-2" : "py-0.5"}`}>
        <button onClick={talking ? undefined : toggleTalk} className="rounded-full" aria-label="Start voice conversation" disabled={talking}>
          <VoiceOrb state={orb} level={level} size={talking ? 150 : 72} label={talking ? orbCaption : "Tap to talk"} />
        </button>
        {talking && <button onClick={endTalk} className="btn btn-ink mt-3"><IconStop className="w-4 h-4" /> End conversation</button>}
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-3">
        {messages.length === 0 && !talking && (
          <div className="px-1 space-y-2">
            <div className="eyebrow">Try asking</div>
            <div className="flex flex-wrap gap-2">
              {(owner ? OWNER_SUGGESTIONS : SUGGESTIONS).map((q) => <button key={q} onClick={() => send(q)} className="btn btn-ghost text-sm py-2">{q}</button>)}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
            <div className={`px-3.5 py-2.5 text-[15px] max-w-[85%] whitespace-pre-wrap ${m.role === "user" ? "bubble-user" : "bubble-ai"}`}>
              {m.text || (m.status ? <span className="text-muted inline-flex items-center gap-2"><span className="dot animate-pulse" />{m.status}</span> : <span className="text-muted">…</span>)}
            </div>
            {m.products && m.products.length > 0 && (
              <div className="flex gap-2 overflow-x-auto pb-1 -mx-3 px-3">
                {m.products.map((p) => <ProductCard key={p.product_id} p={p} onAdd={!owner && (session?.mode !== "instore" || m.fromPhoto) ? (x) => addFromCard(x, !!m.fromPhoto) : undefined} onWhere={session?.mode === "instore" ? whereIs : undefined} />)}
              </div>
            )}
            {m.map && store && <div className="max-w-[85%]"><StoreMap aisles={store.floor_map} target={m.map} youAreHere={session?.aisle_hint} compact /></div>}
            {m.lowStock && m.lowStock.length > 0 && (
              <div className="card p-3 text-sm max-w-[85%]">
                <div className="eyebrow mb-1">Running low</div>
                {m.lowStock.slice(0, 8).map((i) => <div key={i.product_id} className="flex justify-between py-0.5"><span>{i.name}</span><span className="mono text-muted">{i.available} / {i.reorder_point}</span></div>)}
              </div>
            )}
            {m.drafts && m.drafts.length > 0 && (
              <div className="card p-3 text-sm max-w-[85%]">
                <div className="eyebrow mb-1">Drafts waiting for approval</div>
                {m.drafts.map((d) => <div key={d.po_id} className="py-0.5"><b>{d.supplier}</b> <span className="text-muted">· {d.lines} lines</span></div>)}
                <Link href="/owner/" className="text-accent text-sm font-semibold">Review in Reorders</Link>
              </div>
            )}
            {m.checkout && <Link href="/checkout" className="btn btn-primary">Go to checkout</Link>}
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(text); }} className="flex items-center gap-2 px-3 py-2 border-t border-line bg-bg">
        {!owner && (
          <label className="text-muted cursor-pointer p-2" title="Send a photo of a product">
            <IconCamera />
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) send(text, f); e.target.value = ""; }} />
          </label>
        )}
        <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={owner ? "Ask about stock, sales, orders" : "Ask about products, prices, aisles"} className="field flex-1 rounded-full py-2.5" disabled={busy} />
        {!talking && <button type="button" onClick={toggleTalk} className="btn btn-ghost w-11 h-11 p-0 rounded-full" title="Talk"><IconMic /></button>}
        <button type="submit" disabled={busy || !text.trim()} className="btn btn-primary w-11 h-11 p-0 rounded-full" title="Send"><IconSend /></button>
      </form>
    </div>
  );
}
