"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Offer, Product, api } from "@/lib/api";
import { GuardMode, LiveFrame, LiveState, liveSupported, startLive } from "@/lib/live";
import { UiEvent } from "@/lib/sse";
import { Msg, sayAloud, useApp } from "@/lib/store";
import { LANGUAGES } from "@/lib/languages";
import { listenOnce } from "@/lib/voice";
import { PillMode, pillText, tapAction } from "@/lib/voicePill";
import { IconCamera, IconSend, IconSpeaker } from "./Icons";
import ProductCard from "./ProductCard";
import StoreMap from "./StoreMap";
import VoicePill from "./VoicePill";

const STATUS: Record<string, string> = {
  search_products: "Checking the shelves", navigate_to: "Finding the aisle", add_to_cart: "Adding to your cart",
  suggest_substitutes: "Looking for alternatives", view_cart: "Opening your cart", start_checkout: "Preparing checkout",
  get_low_stock: "Checking stock levels", forecast_demand: "Reading the forecast", draft_purchase_order: "Drafting orders",
  get_anomalies: "Checking exits and counts", record_demand_signal: "Noting your request", get_offers: "Checking offers",
  product_facts: "Looking up facts", get_product: "Reading the label",
  store_snapshot: "Pulling today's figures", find_products: "Searching the inventory", sales_report: "Totting up sales", reorder_drafts: "Opening the drafts",
  demand_signals: "Reading demand signals", customers_overview: "Looking at customers", list_offers: "Listing offers", exit_summary: "Checking exits",
  sync_status: "Checking the sync", floor_map_summary: "Reading the floor map", set_reorder_rule: "Updating the reorder rule", adjust_stock: "Updating stock",
  record_shelf_count: "Recording the count", update_price: "Updating the price", move_product: "Moving the product", create_offer: "Creating the offer",
  set_offer_active: "Updating the offer", adjust_points: "Updating points", approve_purchase_order: "Approving the order",
};
const clock = () => Date.now();                                   // event-time reads, kept out of render for the compiler lint
const cadence = () => 0.35 + Math.random() * 0.4;                 // browser TTS exposes no signal; a simulated speech level
const SUGGESTIONS = ["Where is atta?", "பால் எங்கே இருக்கு?", "Do you have oat milk?", "Something for a headache"];
const OWNER_SUGGESTIONS = ["How are we doing today?", "What should I reorder?", "Which products are not selling?", "Create 10% off on Dairy for everyone", "Who are my VIP customers?", "What did shoppers ask for that we don't have?"];

export default function Chat() {
  const { session, store, messages, push, patch, setCart, setHighlight, language, setLanguage, speak, setSpeak, setAvatar, customer } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [orb, setOrb] = useState<PillMode>("idle");            // what the voice pill shows: listening, a tool running, speaking
  const [activity, setActivity] = useState<string | null>(null);   // the tool the agent is running right now, in plain words
  const [voiceOn, setVoiceOn] = useState(false);               // record-and-answer loop (fallback)
  const voiceRef = useRef(false);
  const media = useRef<{ stream: MediaStream; ctx: AudioContext } | null>(null);
  const [live, setLive] = useState<LiveState>("closed");       // speech-to-speech
  const lastLive = useRef<LiveState>("closed");
  const [guard, setGuard] = useState<GuardMode>("unknown");    // loudspeaker or headphones, as measured by the echo guard
  const [canLive, setCanLive] = useState(false);
  useEffect(() => { setTimeout(() => setCanLive(liveSupported()), 0); }, []);
  const liveStop = useRef<(() => void) | null>(null);
  const liveInterrupt = useRef<(() => void) | null>(null);
  const liveConnecting = useRef(false);
  const liveMsg = useRef<{ user: number | null; assistant: number | null }>({ user: null, assistant: null });
  const speechEnded = useRef(0);                                // when the assistant last stopped speaking
  const bottom = useRef<HTMLDivElement>(null);
  const talking = live !== "closed" || voiceOn;
  const owner = session?.mode === "owner";
  const [offers, setOffers] = useState<Offer[]>([]);
  useEffect(() => {
    if (!session || owner) return;
    api.offers(session.store_id, session).then(setOffers).catch(() => {});
  }, [session, owner]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function consume(stream: AsyncGenerator<UiEvent>, userMsgId?: number) {
    const id = push({ role: "assistant", text: "" });
    let buffer = "";
    setAvatar("thinking"); setOrb("thinking");
    try {
      for await (const e of stream) {
        if (e.type === "transcript" && userMsgId) patch(userMsgId, { text: e.text });
        else if (e.type === "status") { const what = STATUS[e.tool] ?? "Working"; patch(id, { status: what }); setActivity(what); }
        else if (e.type === "token") { buffer += e.text; patch(id, { text: buffer, status: undefined }); setActivity(null); }
        else if (e.type === "done") { buffer = e.text || buffer; patch(id, { text: buffer, status: undefined }); setActivity(null); }
        else if (e.type === "action") handleAction(e.name, e.data, id);
        else if (e.type === "error") { buffer = ""; patch(id, { text: e.text, status: undefined }); setActivity(null); }
      }
      setActivity(null);
      if ((speak || voiceRef.current) && buffer) {
        setAvatar("speaking"); setOrb("speaking");
        const pulse = setInterval(() => setLevel(cadence()), 90);
        await sayAloud(buffer, language);
        clearInterval(pulse); setLevel(0); speechEnded.current = clock();
      }
      setAvatar("idle"); setOrb(voiceRef.current ? "listening" : "idle");
    } catch (err) {
      patch(id, { text: `Assistant unavailable: ${(err as Error).message}`, status: undefined });
      setActivity(null); setAvatar("idle"); setOrb("idle");
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
    else if (name === "show_offers") patch(id, { offers: (data.offers as Msg["offers"]) ?? [] });
    else if (name === "show_snapshot" && data.today) patch(id, { snapshot: data as unknown as Msg["snapshot"] });
    else if (name === "show_rows" && Array.isArray(data.rows) && Array.isArray(data.columns)) patch(id, { rows: { columns: data.columns as string[], rows: data.rows as Record<string, unknown>[] } });
    else if (name === "show_facts" && data.ok) patch(id, { facts: { summary: String(data.summary ?? ""), sources: (data.sources as { title: string; url: string }[]) ?? [], note: String(data.note ?? ""), label: (data.label as NonNullable<Msg["facts"]>["label"]) ?? null } });
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
      const ctl = await startLive(session.session_id, language, {
        onLevel: (l) => setLevel(l),
        onGuard: setGuard,
        onState: (st) => {
          if (lastLive.current === "speaking" && st !== "speaking") speechEnded.current = clock();
          lastLive.current = st;
          setLive(st);
          setOrb(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "connecting" ? "connecting" : st === "reconnecting" ? "reconnecting" : "idle");
          if (st === "speaking") setActivity(null);
          setAvatar(st === "speaking" ? "speaking" : st === "listening" ? "listening" : st === "closed" ? "idle" : "thinking");
          if (st === "closed") { closedEarly = true; liveStop.current = null; liveInterrupt.current = null; liveMsg.current = { user: null, assistant: null }; setLevel(0); setGuard("unknown"); setActivity(null); }
        },
        onFrame: (f: LiveFrame) => {
          if (f.type === "transcript") {
            const slot = f.role, cur = liveMsg.current[slot];
            if (cur === null) liveMsg.current[slot] = push({ role: slot, text: f.text });
            else patch(cur, { text: (useApp.getState().messages.find((m) => m.id === cur)?.text ?? "") + f.text });
            if (slot === "user") liveMsg.current.assistant = null;
          } else if (f.type === "turn_complete") { liveMsg.current = { user: null, assistant: null }; setActivity(null); }
          else if (f.type === "echo") { const cur = liveMsg.current.user; if (cur !== null) patch(cur, { text: "(echo from the speaker)" }); liveMsg.current.user = null; }
          else if (f.type === "status") { setOrb("thinking"); setActivity(STATUS[f.tool] ?? "Working"); }   // a tool is running; the voice resumes when audio arrives
          else if (f.type === "action") { const id = liveMsg.current.assistant ?? (liveMsg.current.assistant = push({ role: "assistant", text: "" })); handleAction(f.name, f.data, id); }
          else if (f.type === "error") push({ role: "assistant", text: f.text });
        },
      });
      if (closedEarly) ctl.stop(); else { liveStop.current = ctl.stop; liveInterrupt.current = ctl.interrupt; }
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
      if (session) await consume(api.audio(session, heard.blob, language), userId);
      setBusy(false);
    }
  }
  function stopVoice() {
    voiceRef.current = false; setVoiceOn(false); setOrb("idle"); setLevel(0); setActivity(null);
    window.speechSynthesis?.cancel();
    media.current?.stream.getTracks().forEach((t) => t.stop());
    media.current?.ctx.close(); media.current = null;
    setAvatar("idle");
  }
  function toggleTalk() { if (canLive) toggleLive(); else toggleVoice(); }
  function endTalk() { if (liveStop.current) liveStop.current(); if (voiceRef.current) stopVoice(); }
  useEffect(() => () => { if (voiceRef.current) stopVoice(); liveStop.current?.(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  const liveLang = useRef(language);
  useEffect(() => {                                                 // the live session's language is fixed when it connects: restart it
    if (liveLang.current === language) return;
    liveLang.current = language;
    if (liveStop.current) { liveStop.current(); setTimeout(() => { void toggleLive(); }, 400); }
  }, [language]);   // eslint-disable-line react-hooks/exhaustive-deps

  // The pill: live connection states first, otherwise whatever the agent is doing (a tool running, a reply being read aloud).
  const mode: PillMode = live === "connecting" ? "connecting" : live === "reconnecting" ? "reconnecting" : orb;
  const { label, sub } = pillText(mode, guard, activity);
  function onPillTap() {
    const action = tapAction(mode, clock() - speechEnded.current);
    if (action === "start") toggleTalk();
    else if (action === "interrupt") { if (liveInterrupt.current) liveInterrupt.current(); else window.speechSynthesis?.cancel(); }
    else if (action === "end") endTalk();
  }

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center gap-2 px-4 pt-3 pb-2">
        <div className="flex-1 min-w-0">
          <h1 className="text-[17px] font-semibold leading-tight truncate">{store?.name ?? "Store"}</h1>
          <div className="text-xs text-muted truncate">{owner ? "Owner assistant" : store?.brand?.tagline || (session?.mode === "instore" ? "In-store assistant" : "Shopping assistant")}</div>
        </div>
        {!owner && <Link href="/me" className={`chip ${customer ? "chip-accent" : "chip-muted"}`}>{customer ? (customer.name ? `Hi, ${customer.name.split(" ")[0]}` : "My profile") : "Sign in"}</Link>}
        <select id="lang" value={language} onChange={(e) => setLanguage(e.target.value)} className="chip chip-muted bg-surface border border-line max-w-[6.5rem]" aria-label="Language">
          {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
        <button onClick={() => setSpeak(!speak)} aria-label={speak ? "Mute read-aloud" : "Read replies aloud"} title={speak ? "Mute read-aloud" : "Read replies aloud"} className="text-muted p-1"><IconSpeaker muted={!speak} /></button>
      </header>

      {/* The thread is the page; the voice pill floats over its bottom-right corner within thumb reach. */}
      <div className="relative flex-1 min-h-0">
        <div className="h-full overflow-y-auto px-3 pb-20 space-y-3">
          {messages.length === 0 && (
            <div className="px-1 pt-1 space-y-4 reveal">
              <p className="text-[17px] font-semibold leading-snug max-w-[26ch]">{store?.brand?.greeting || (owner ? "What do you want to know about the shop?" : "What are you looking for today?")}</p>
              {!owner && offers.length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-xs font-semibold text-muted">Offers for you</div>
                  <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
                    {offers.map((o) => <div key={o.offer_id} className="card px-3 py-2 text-sm shrink-0 max-w-[220px]"><div className="font-semibold truncate">{o.name}</div><div className="text-xs text-muted">{o.detail}</div></div>)}
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {(owner ? OWNER_SUGGESTIONS : SUGGESTIONS).map((q) => <button key={q} onClick={() => send(q)} className="btn btn-ghost text-sm py-2">{q}</button>)}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
              <div className={`reveal px-3.5 py-2.5 text-[15px] max-w-[85%] whitespace-pre-wrap ${m.role === "user" ? "bubble-user" : "bubble-ai"}`}>
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
        <div className="absolute right-3 bottom-3 z-10">
          <VoicePill mode={mode} level={level} label={label} sub={sub} onTap={onPillTap} onHold={endTalk} />
        </div>
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(text); }} className="flex items-center gap-2 px-3 py-2 border-t border-line bg-bg">
        {!owner && (
          <label className="text-muted cursor-pointer p-2" title="Send a photo of a product">
            <IconCamera />
            <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) send(text, f); e.target.value = ""; }} />
          </label>
        )}
        <input id="chat-input" value={text} onChange={(e) => setText(e.target.value)} placeholder={owner ? "Ask about stock, sales, orders" : talking ? "Or type while you talk" : "Ask about products, prices, aisles"} className="field flex-1 rounded-full py-2.5" disabled={busy} />
        <button type="submit" disabled={busy || !text.trim()} className="btn btn-primary w-11 h-11 p-0 rounded-full" title="Send" aria-label="Send"><IconSend /></button>
      </form>
    </div>
  );
}
