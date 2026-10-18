"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ApiError, Offer, Product, api } from "@/lib/api";
import { liveSupported } from "@/lib/live";
import { UiEvent } from "@/lib/sse";
import { sayAloud, useApp } from "@/lib/store";
import { LANGUAGES } from "@/lib/languages";
import { listenOnce } from "@/lib/voice";
import { IconCamera, IconMic, IconSend, IconSpeaker } from "./Icons";
import ProductCard from "./ProductCard";
import StoreMap from "./StoreMap";
import VoiceDock from "./VoiceDock";
import VoiceStrip from "./VoiceStrip";
import { applyAction } from "@/lib/actions";
import { useVoice, voice } from "@/lib/voiceSession";
import VoiceNote from "./VoiceNote";
import { peaksOf } from "@/lib/voiceClip";

const SUGGESTIONS = ["Where is atta?", "பால் எங்கே இருக்கு?", "Do you have oat milk?", "Something for a headache"];
const OWNER_SUGGESTIONS = ["How are we doing today?", "What should I reorder?", "Which products are not selling?", "Create 10% off on Dairy for everyone", "Who are my VIP customers?", "What did shoppers ask for that we don't have?"];

export default function Chat() {
  const { session, setSession, store, messages, push, patch, setCart, language, setLanguage, speak, setSpeak, setAvatar, customer } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const liveState = useVoice((s) => s.live);                   // the conversation itself lives in lib/voiceSession
  const [voiceOn, setVoiceOn] = useState(false);               // record-and-answer loop, only where live audio is unsupported
  const voiceRef = useRef(false);
  const media = useRef<{ stream: MediaStream; ctx: AudioContext } | null>(null);
  const [canLive, setCanLive] = useState(true);
  useEffect(() => { setTimeout(() => setCanLive(liveSupported()), 0); }, []);
  const bottom = useRef<HTMLDivElement>(null);
  const talking = liveState !== "closed" || voiceOn;
  const owner = session?.mode === "owner";
  const [offers, setOffers] = useState<Offer[]>([]);
  useEffect(() => {
    if (!session || owner) return;
    api.offers(session.store_id, session).then(setOffers).catch(() => {});
  }, [session, owner]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  const ask = useApp((s) => s.ask), setAsk = useApp((s) => s.setAsk);
  useEffect(() => { if (ask) { setAsk(null); void send(ask); } }, [ask]);   // eslint-disable-line react-hooks/exhaustive-deps

  /** Sessions live four hours. An owner's dead session is replaced silently; a shopper's visit ends and the entrance page returns. */
  const sessionGone = (e: unknown) => e instanceof ApiError && (e.status === 404 || e.status === 401);
  async function freshSession(): Promise<typeof session> {
    if (!session || !owner) return null;
    const { owner: ownerApi } = await import("@/lib/owner");
    const next = await ownerApi.session(session.store_id);
    setSession(next);
    return next;
  }

  async function consume(make: (s: NonNullable<typeof session>) => AsyncGenerator<UiEvent>, userMsgId?: number, retried = false) {
    if (!session) return;
    const id = push({ role: "assistant", text: "" });
    let buffer = "";
    setAvatar("thinking"); if (!voice.active()) useVoice.setState({ orb: "thinking" });
    try {
      for await (const e of make(session)) {
        if (e.type === "transcript" && userMsgId) patch(userMsgId, { text: e.text });
        else if (e.type === "status") patch(id, { status: e.label ?? "Working" });   // the label comes with the event: one wording for every surface
        else if (e.type === "token") { buffer += e.text; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "done") { buffer = e.text || buffer; patch(id, { text: buffer, status: undefined }); }
        else if (e.type === "action") applyAction(e.name, e.data, id, photoTurn.current);
        else if (e.type === "error") { buffer = ""; patch(id, { text: e.text, status: undefined }); }
      }
      if ((speak || voiceRef.current) && buffer) {
        setAvatar("speaking");
        const stopPulse = voice.pulse();
        await sayAloud(buffer, language);
        stopPulse();
      }
      setAvatar("idle"); if (!voice.active()) useVoice.setState({ orb: voiceRef.current ? "listening" : "idle" });
    } catch (err) {
      if (sessionGone(err) && owner && !retried) {
        const next = await freshSession().catch(() => null);
        if (next) { useApp.setState({ messages: useApp.getState().messages.filter((m) => m.id !== id) }); return consume(make, userMsgId, true); }
      }
      if (sessionGone(err) && !owner) { patch(id, { text: "Your visit has ended. Scan the entrance code again to continue.", status: undefined }); setSession(null); }
      else patch(id, { text: `Assistant unavailable: ${(err as Error).message}`, status: undefined });
      setAvatar("idle"); if (!voice.active()) useVoice.setState({ orb: "idle" });
    }
  }


  const photoTurn = useRef(false);
  async function send(message: string, image?: Blob) {
    if (!session || (!message.trim() && !image)) return;
    if (!image && voice.sendText(message.trim())) { setText(""); return; }   // live voice is on: the typed line is its next turn
    if (busy) return;                                                 // one text turn at a time; the line stays in the box
    setBusy(true); setText("");
    photoTurn.current = !!image;
    push({ role: "user", text: message || "Photo of a product" });
    await consume((s) => api.chat(s, message || "What is this product?", image, language));
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
  /** Fallback: record until silence, answer, speak, listen again. Used where live audio is unsupported. */
  async function toggleVoice() {
    if (voiceRef.current) { stopVoice(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      media.current = { stream, ctx: new AudioContext() };
    } catch { push({ role: "assistant", text: "Microphone not available. Please type instead." }); return; }
    voiceRef.current = true; setVoiceOn(true); voice.registerFallback(stopVoice); useVoice.setState({ fallback: true, expanded: true });
    while (voiceRef.current && media.current) {
      useVoice.setState({ orb: "listening" }); setAvatar("listening");
      const heard = await listenOnce(media.current.stream, media.current.ctx, () => !voiceRef.current, (l) => useVoice.setState({ level: l }));
      if (!voiceRef.current) break;
      if (!heard) continue;
      setBusy(true);
      const userId = push({ role: "user", text: "…", voice: { url: URL.createObjectURL(heard.blob) } });
      voicePeaks(heard.blob, userId);
      await consume((s) => api.audio(s, heard.blob, language), userId);
      setBusy(false);
    }
  }
  /** The waveform for a push-to-talk recording, decoded in the browser. */
  async function voicePeaks(blob: Blob, id: number) {
    try {
      const ctx = media.current?.ctx; if (!ctx) return;
      const audio = await ctx.decodeAudioData(await blob.arrayBuffer());
      const url = useApp.getState().messages.find((m) => m.id === id)?.voice?.url;
      patch(id, { voice: { url, seconds: audio.duration, peaks: peaksOf(audio.getChannelData(0)) } });
    } catch { /* no waveform: the note still plays */ }
  }
  function stopVoice() {
    voiceRef.current = false; setVoiceOn(false); voice.registerFallback(null); useVoice.setState({ orb: "idle", level: 0, fallback: false, expanded: false });
    window.speechSynthesis?.cancel();
    media.current?.stream.getTracks().forEach((t) => t.stop());
    media.current?.ctx.close(); media.current = null;
    setAvatar("idle");
  }
  useEffect(() => () => { if (voiceRef.current) stopVoice(); if (owner) voice.end(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-3 px-4 pt-3 pb-2">
        <div className="flex-1 min-w-0">
          <div className="eyebrow">{owner ? "Owner assistant" : store?.brand?.tagline || (session?.mode === "instore" ? "In-store assistant" : "Shopping assistant")}</div>
          <h1 className="text-lg font-semibold leading-tight truncate">{store?.name ?? "Store"}</h1>
        </div>
        {!owner && <Link href="/me" className={`chip ${customer ? "chip-accent" : "chip-muted"}`}>{customer ? (customer.name ? `Hi, ${customer.name.split(" ")[0]}` : "My profile") : "Sign in"}</Link>}
        <select id="lang" value={language} onChange={(e) => setLanguage(e.target.value)} className="chip chip-muted bg-surface border border-line max-w-[7.5rem]" aria-label="Language">
          {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
        <button onClick={() => setSpeak(!speak)} title={speak ? "Mute read-aloud" : "Read replies aloud"} className="text-muted"><IconSpeaker muted={!speak} /></button>
        {owner && canLive && <VoiceDock variant="header" resolveSession={freshSession} />}
      </header>

      {owner && <VoiceStrip />}

      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-3">
        {messages.length === 0 && !talking && offers.length > 0 && (
          <div className="px-1 space-y-1.5">
            <div className="eyebrow">Offers for you</div>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {offers.map((o) => <div key={o.offer_id} className="card px-3 py-2 text-sm shrink-0 max-w-[220px]"><div className="font-semibold truncate">{o.name}</div><div className="text-xs text-muted">{o.detail}</div></div>)}
            </div>
          </div>
        )}
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
            <div className={`reveal px-3.5 py-2.5 text-[15px] max-w-[85%] whitespace-pre-wrap ${m.role === "user" ? "bubble-user" : "bubble-ai"}`}>
              {m.role === "user" && m.voice ? <VoiceNote url={m.voice.url} seconds={m.voice.seconds} peaks={m.voice.peaks} text={m.text} />
                : m.text || (m.status ? <span className="text-muted inline-flex items-center gap-2"><span className="dot animate-pulse" />{m.status}</span> : <span className="text-muted">…</span>)}
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
            {m.offers && (
              <div className="card p-3 text-sm max-w-[85%]">
                <div className="eyebrow mb-1">Offers for you</div>
                {m.offers.length === 0 ? <span className="text-muted">No offers running right now.</span>
                  : m.offers.map((o) => <div key={o.name} className="py-0.5"><b>{o.name}</b> <span className="text-muted">· {o.detail}</span></div>)}
              </div>
            )}
            {m.facts && (
              <div className="mt-2 border border-line rounded-xl p-3 text-sm space-y-1.5 reveal">
                <div className="eyebrow">From public sources</div>
                {m.facts.label?.ingredients && <div><span className="text-muted">Ingredients: </span>{m.facts.label.ingredients}</div>}
                {m.facts.label?.allergens && m.facts.label.allergens.length > 0 && <div><span className="text-muted">Allergens: </span>{m.facts.label.allergens.join(", ")}</div>}
                {m.facts.label?.nutrition_per_100g && <div className="text-muted">Per 100 g: {Object.entries(m.facts.label.nutrition_per_100g).map(([k, v]) => `${k.replace("-", " ")} ${v}`).join(" · ")}{m.facts.label.nutriscore ? ` · Nutri-Score ${m.facts.label.nutriscore}` : ""}</div>}
                <div className="flex flex-wrap gap-x-3 gap-y-1">{m.facts.sources.map((s) => <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="underline text-muted">{s.title}</a>)}</div>
                <div className="text-xs text-muted">{m.facts.note}</div>
              </div>
            )}
            {m.snapshot && (
              <div className="card p-3 text-sm max-w-[95%] space-y-2">
                <div className="grid grid-cols-3 gap-2">
                  {([["Revenue today", `₹${m.snapshot.today.revenue.toLocaleString("en-IN")}`], ["Orders", m.snapshot.today.orders], ["Avg basket", `₹${m.snapshot.today.avg_basket.toLocaleString("en-IN")}`],
                    ["Low stock", m.snapshot.low_stock], ["Out of stock", m.snapshot.out_of_stock], ["Drafts waiting", m.snapshot.open_drafts],
                    ["Exit flags", m.snapshot.open_flags], ["Signed-in customers", m.snapshot.signed_in_customers], ["Live offers", m.snapshot.live_offers]] as [string, string | number][]).map(([l, v]) => (
                    <div key={l}><div className="eyebrow">{l}</div><div className="mono text-base font-semibold">{v}</div></div>
                  ))}
                </div>
                {m.snapshot.attention.length > 0 && <ul className="text-xs text-muted list-disc pl-4">{m.snapshot.attention.map((a) => <li key={a}>{a}</li>)}</ul>}
              </div>
            )}
            {m.rows && m.rows.rows.length > 0 && (
              <div className="card overflow-x-auto max-w-[95%]">
                <table className="w-full text-xs">
                  <thead><tr>{m.rows.columns.map((c) => <th key={c} className="text-left px-2 py-1 text-muted font-medium whitespace-nowrap">{c.replace(/_/g, " ")}</th>)}</tr></thead>
                  <tbody>{m.rows.rows.slice(0, 15).map((r, i) => <tr key={i} className="border-t border-line">{m.rows!.columns.map((c) => <td key={c} className={`px-2 py-1 ${typeof r[c] === "number" ? "mono text-right" : ""}`}>{r[c] === null || r[c] === undefined ? "–" : typeof r[c] === "boolean" ? (r[c] ? "yes" : "no") : String(r[c])}</td>)}</tr>)}</tbody>
                </table>
                {m.rows.rows.length > 15 && <div className="px-2 py-1 text-xs text-muted">{m.rows.rows.length - 15} more rows</div>}
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
        <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={owner ? "Ask about stock, sales, orders" : "Ask about products, prices, aisles"} className="field flex-1 rounded-full py-2.5" />
        {!owner && session?.mode === "online" && canLive && <VoiceDock variant="composer" />}
        {!canLive && !talking && <button type="button" onClick={toggleVoice} className="btn btn-ghost btn-icon rounded-full" title="Talk"><IconMic /></button>}
        <button type="submit" disabled={busy || !text.trim()} className="btn btn-primary btn-icon rounded-full" title="Send"><IconSend /></button>
      </form>
    </div>
  );
}
