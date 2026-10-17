"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Order, api, money } from "@/lib/api";
import { firstAuthState, signOutShopper } from "@/lib/firebase";
import { Profile, linkShopper, me } from "@/lib/me";
import { useApp } from "@/lib/store";
import PhoneSignIn from "@/components/PhoneSignIn";

const DIETARY = ["Vegetarian", "Vegan", "Jain", "Halal", "No sugar", "Gluten-free", "Lactose-free", "Nut allergy"];
const CATEGORIES = ["Dairy", "Staples", "Snacks", "Beverages", "Fruits & Vegetables", "Bakery", "Personal care", "Household", "Baby"];
const LANGS = [["auto", "Auto"], ["en", "English"], ["ta", "தமிழ்"], ["hi", "हिन्दी"]] as const;
const SUBS = [["ask", "Ask me first"], ["same_brand", "Same brand, another size"], ["any", "Any equivalent"]] as const;

/** /me: the signed-in shopper's preferences, receipts and data controls. Guests are offered phone sign-in. */
export default function MePage() {
  const router = useRouter();
  const { session, setCustomer, updateSession, setCart } = useApp();
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [form, setForm] = useState<Partial<Profile>>({});
  const [msg, setMsg] = useState("");
  const [aisles, setAisles] = useState<Record<string, string>>({});

  useEffect(() => { firstAuthState().then((u) => setSignedIn(!!u?.phoneNumber)); }, []);
  useEffect(() => {
    if (!signedIn || !session) return;
    (async () => {
      try {
        if (!session.customer_id) await linkShopper(session);        // signed in, but this visit was not linked yet
        let p: Profile;
        try { p = await me.profile(session.store_id); } catch { await linkShopper(session); p = await me.profile(session.store_id); }
        setProfile(p);
        setForm({ name: p.name, language: p.language, dietary: p.dietary, favourite_categories: p.favourite_categories, substitution: p.substitution });
        setCustomer({ uid: p.uid, name: p.name });
        setOrders(await me.orders(session.store_id));
      } catch (e) { setMsg((e as Error).message); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signedIn]);

  const names = useMemo(() => { const m: Record<string, string> = {}; orders.forEach((o) => o.items.forEach((i) => { m[i.product_id] = i.name; })); return m; }, [orders]);

  async function save() {
    if (!session) return;
    try { const p = await me.patch({ store_id: session.store_id, ...form }); setProfile(p); setCustomer({ uid: p.uid, name: p.name }); setMsg("Saved."); }
    catch (e) { setMsg((e as Error).message); }
  }
  async function buyAgain(o: Order) {
    if (!session) return;
    if (session.mode === "online") {
      for (const i of o.items) { try { setCart(await api.addItem(session, i.product_id, i.qty, "chat")); } catch {} }
      router.push("/shop");
      return;
    }
    const found: Record<string, string> = {};
    await Promise.all(o.items.map(async (i) => {
      try { const p = await api.product(session.store_id, i.product_id); found[i.product_id] = p.available <= 0 ? "out of stock today" : p.location ? `aisle ${p.location.aisle}, bay ${p.location.bay}` : "ask the assistant"; }
      catch { found[i.product_id] = "no longer stocked"; }
    }));
    setAisles((a) => ({ ...a, ...found }));
  }
  async function download() {
    const data = await me.exportAll();
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = "my-data.json"; a.click(); URL.revokeObjectURL(url);
  }
  async function remove() {
    if (!confirm("Delete your profile, preferences and conversation history? Receipts stay with the shop, without your name.")) return;
    try { await me.deleteAll(); } catch (e) { setMsg((e as Error).message); return; }
    await signOutShopper(); setCustomer(null);
    if (session) updateSession({ ...session, customer_id: null });
    router.replace("/shop");
  }
  async function signOut() { await signOutShopper(); setCustomer(null); router.replace("/shop"); }

  if (!session) return <main className="p-6 text-center space-y-3"><p className="text-muted">Open a store first.</p><Link href="/" className="btn btn-ghost">Home</Link></main>;
  if (signedIn === null) return <main className="p-6 text-muted">Loading</main>;
  if (!signedIn) return (
    <main className="flex-1 flex flex-col items-center justify-center p-6">
      <div className="card p-5 w-full max-w-sm space-y-3">
        <div className="eyebrow">Your profile</div>
        <h1 className="text-xl font-semibold">Sign in with your mobile number</h1>
        <p className="text-sm text-muted">Offers, your usual items and past receipts. Optional, and you can delete everything later.</p>
        <PhoneSignIn onDone={() => setSignedIn(true)} onSkip={() => router.replace("/shop")} />
      </div>
    </main>
  );
  if (!profile) return <main className="p-6 text-muted">{msg || "Loading your profile"}</main>;
  const toggle = (key: "dietary" | "favourite_categories", v: string) =>
    setForm((f) => { const cur = f[key] ?? []; return { ...f, [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] }; });
  const chips = (key: "dietary" | "favourite_categories", items: string[]) =>
    <div className="flex flex-wrap gap-1.5 mt-1">{items.map((d) => <button key={d} onClick={() => toggle(key, d)} className={`chip ${form[key]?.includes(d) ? "chip-accent" : "chip-muted"}`}>{d}</button>)}</div>;

  return (
    <main className="p-4 space-y-4 max-w-xl mx-auto w-full">
      <header className="flex items-center gap-3">
        <div className="flex-1 min-w-0"><div className="eyebrow">Signed in · ····{profile.phone_last4}</div><h1 className="text-xl font-semibold truncate">{profile.name || "Your profile"}</h1></div>
        <Link href="/shop" className="btn btn-ghost py-1.5 text-xs">Back to shop</Link>
      </header>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="card p-2"><div className="text-lg font-semibold mono">{profile.visits}</div><div className="eyebrow">Visits</div></div>
        <div className="card p-2"><div className="text-lg font-semibold mono">{money(profile.spend)}</div><div className="eyebrow">Spent</div></div>
        <div className="card p-2"><div className="text-lg font-semibold mono">{profile.points}</div><div className="eyebrow">Points</div></div>
      </div>

      <section className="card p-4 space-y-3">
        <div className="eyebrow">Preferences</div>
        <label className="block text-sm">Name<input value={form.name ?? ""} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={60} className="field mt-1" /></label>
        <label className="block text-sm">Language<select value={form.language ?? "auto"} onChange={(e) => setForm({ ...form, language: e.target.value as Profile["language"] })} className="field mt-1">{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <div className="text-sm">Dietary{chips("dietary", DIETARY)}</div>
        <div className="text-sm">Favourite categories{chips("favourite_categories", CATEGORIES)}</div>
        <div className="text-sm">When something is out of stock
          <div className="flex flex-wrap gap-1.5 mt-1">{SUBS.map(([v, l]) => <button key={v} onClick={() => setForm({ ...form, substitution: v })} className={`chip ${form.substitution === v ? "chip-accent" : "chip-muted"}`}>{l}</button>)}</div>
        </div>
        {profile.usual_items.length > 0 && (
          <div className="text-sm">Your usual items
            <div className="flex flex-wrap gap-1.5 mt-1">{profile.usual_items.map((id) => <span key={id} className="chip chip-muted">{names[id] ?? id}</span>)}</div>
            <p className="text-xs text-muted mt-1">Learned from your receipts. The assistant uses these when you ask what you might be forgetting.</p>
          </div>
        )}
        <div className="flex items-center gap-2"><button onClick={save} className="btn btn-primary">Save</button>{msg && <span className="text-xs text-muted">{msg}</span>}</div>
      </section>

      <section className="card p-4 space-y-2">
        <div className="eyebrow">Your receipts</div>
        {orders.length === 0 && <p className="text-sm text-muted">No purchases yet at this store.</p>}
        {orders.map((o) => (
          <div key={o.order_id} className="border-t border-line pt-2 text-sm">
            <div className="flex items-center gap-2"><span className="flex-1">{new Date(o.paid_at ?? o.created_at).toLocaleDateString()} · {o.items.reduce((n, i) => n + i.qty, 0)} items</span><span className="mono font-semibold">{money(o.total)}</span></div>
            <div className="text-xs text-muted truncate">{o.items.map((i) => i.name).join(", ")}</div>
            <div className="flex gap-2 mt-1">
              <Link href={`/receipt?order=${o.order_id}`} className="btn btn-ghost py-1 text-xs">Receipt</Link>
              <button onClick={() => buyAgain(o)} className="btn btn-ghost py-1 text-xs">{session.mode === "online" ? "Buy again" : "Where are these?"}</button>
            </div>
            {o.items.some((i) => aisles[i.product_id]) && <ul className="text-xs text-muted mt-1">{o.items.map((i) => aisles[i.product_id] && <li key={i.product_id}>{i.name}: {aisles[i.product_id]}</li>)}</ul>}
          </div>
        ))}
      </section>

      <section className="card p-4 space-y-2 text-sm">
        <div className="eyebrow">Your data</div>
        <p className="text-muted text-xs">Consent given {new Date(profile.consent_at).toLocaleDateString()}. We keep your name, preferences, receipts at this store and your conversations with the assistant, nothing else.</p>
        <div className="flex flex-wrap gap-2">
          <button onClick={download} className="btn btn-ghost py-1.5 text-xs">Download my data</button>
          <button onClick={signOut} className="btn btn-ghost py-1.5 text-xs">Sign out</button>
          <button onClick={remove} className="btn btn-danger py-1.5 text-xs">Delete my account</button>
        </div>
      </section>
    </main>
  );
}
