"use client";
import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { User } from "firebase/auth";
import { API, money, type Aisle } from "@/lib/api";
import { createOwnerAccount, isPasswordUser, refreshVerified, resendVerification, resetPassword, signInWithEmail, signInWithGoogle, signOutOwner, watchUser } from "@/lib/firebase";
import { Customer, Draft, InvRow, Loss, OfferDoc, Overview, Signals, StoreDoc, SyncView, owner } from "@/lib/owner";
import { QRCodeSVG } from "qrcode.react";
import BarcodeScan from "@/components/BarcodeScan";
import FloorMapEditor from "@/components/FloorMapEditor";
import { useApp } from "@/lib/store";
import Chat from "@/components/Chat";
import RevenueChart from "@/components/RevenueChart";

type Tab = "overview" | "inventory" | "reorders" | "signals" | "customers" | "offers" | "loss" | "connectors" | "setup" | "exits" | "chat";
const NAV: { group: string; items: { id: Tab; label: string }[] }[] = [
  { group: "Today", items: [{ id: "overview", label: "Overview" }, { id: "chat", label: "Ask the assistant" }] },
  { group: "Stock", items: [{ id: "inventory", label: "Inventory" }, { id: "reorders", label: "Reorders" }, { id: "signals", label: "Demand signals" }] },
  { group: "Customers", items: [{ id: "customers", label: "Customers" }, { id: "offers", label: "Offers" }] },
  { group: "Trust", items: [{ id: "loss", label: "Loss and shrink" }, { id: "exits", label: "Exit checks" }] },
  { group: "Store", items: [{ id: "setup", label: "Store settings" }, { id: "connectors", label: "Connectors" }] },
];
const STAFF_IDS: Tab[] = ["inventory", "exits"];
const TITLES: Record<Tab, [string, string]> = {
  overview: ["Today", "Sales so far, stock that needs attention, and decisions waiting for you."],
  chat: ["Ask the assistant", "The same assistant your shoppers use, on your side of the counter. Type or talk."],
  inventory: ["Inventory", "Stock on hand, how fast it sells and when to reorder. Click a reorder number to change it."],
  reorders: ["Reorders", "Purchase order drafts grouped by supplier. Nothing is sent until you approve it."],
  signals: ["Demand signals", "What shoppers asked for that you do not carry or had run out of."],
  customers: ["Customers", "Shoppers who chose to sign in, grouped into segments you can target with offers."],
  offers: ["Offers", "Discounts that apply themselves in the cart. The best one wins per item and one per bill."],
  loss: ["Loss and shrink", "Shelf counts against system stock, exit outcomes and the controls behind them."],
  exits: ["Exit checks", "Every receipt scanned at the exit kiosk and how it was cleared."],
  setup: ["Store settings", "Products, aisles, branding, QR codes, team and payments."],
  connectors: ["Connectors", "Bring products in from a file, keep stock in sync with your billing system, print QR codes."],
};

export default function OwnerPage() {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [stores, setStores] = useState<string[]>([]);
  const [roles, setRoles] = useState<Record<string, "owner" | "staff">>({});
  const [store, setStore] = useState("");
  const [tab, setTab] = useState<Tab>("overview");
  const [loadedMe, setLoadedMe] = useState(false);
  const [newPin, setNewPin] = useState("");
  const [verifiedTick, setVerifiedTick] = useState(0);
  const [meError, setMeError] = useState("");
  const onVerified = useCallback(() => setVerifiedTick((t) => t + 1), []);

  useEffect(() => watchUser((u) => { setUser(u); setLoadedMe(false); setMeError(""); }), []);
  useEffect(() => {
    if (!user?.email || (isPasswordUser(user) && !user.emailVerified)) return;
    owner.me().then((m) => { setStores(m.stores); setRoles(m.roles); setStore(m.stores[0] ?? ""); setLoadedMe(true); if (m.roles[m.stores[0]] === "staff") setTab("inventory"); })
      .catch((e) => { setMeError((e as Error).message || "no response"); setLoadedMe(true); });
  }, [user, verifiedTick]);
  const role = roles[store] ?? "owner";
  const nav = NAV.map((g) => ({ ...g, items: g.items.filter((i) => role !== "staff" || STAFF_IDS.includes(i.id)) })).filter((g) => g.items.length);
  const [storeName, setStoreName] = useState("");
  useEffect(() => { if (store) owner.store(store).then((d) => setStoreName(d.name)).catch(() => setStoreName(store)); }, [store]);

  if (user === undefined) return <AuthShell><p className="text-muted">Loading</p></AuthShell>;
  if (!user?.email) return <OwnerSignIn />;          // shoppers signed in by phone are not owners
  if (isPasswordUser(user) && !user.emailVerified) return <VerifyEmail email={user.email} onVerified={onVerified} />;
  if (!store) {
    if (!loadedMe) return <AuthShell><Skeleton /></AuthShell>;
    if (meError) return <ServerError error={meError} email={user.email} retry={() => { setLoadedMe(false); setMeError(""); setVerifiedTick((t) => t + 1); }} />;
    return <RegisterForm email={user.email ?? ""} error="" onDone={(s, pin) => { setStores([s.store_id]); setRoles({ [s.store_id]: "owner" }); setStore(s.store_id); setNewPin(pin); setTab("setup"); }} />;
  }

  const picker = stores.length > 1
    ? <select value={store} onChange={(e) => setStore(e.target.value)} className="field mt-1" aria-label="Store">{stores.map((s) => <option key={s} value={s}>{s}</option>)}</select>
    : <div className="font-semibold text-[15px] leading-tight mt-0.5 truncate">{storeName || store}</div>;
  return (
    <div data-theme="owner" className="min-h-dvh flex bg-bg text-ink">
      <aside className="rail hidden lg:flex">
        <div className="px-4 py-4 border-b border-line"><div className="label">Royal Stack</div>{picker}</div>
        <nav className="flex-1 overflow-y-auto py-2">
          {nav.map((g) => (
            <div key={g.group}>
              <div className="rail-group">{g.group}</div>
              {g.items.map((i) => <button key={i.id} aria-current={tab === i.id ? "page" : undefined} onClick={() => setTab(i.id)} className="rail-link">{i.label}</button>)}
            </div>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-line text-xs text-muted">
          <div className="truncate" title={user.email}>{user.email}</div>
          <div className="flex gap-3 mt-1"><button onClick={() => signOutOwner()} className="underline">Sign out</button><Link href="/" className="underline">Shopper app</Link></div>
        </div>
      </aside>
      <div className="flex-1 min-w-0 flex flex-col h-dvh">
        <header className="lg:hidden flex items-center gap-3 px-4 py-2.5 border-b border-line bg-surface">
          <div className="min-w-0 flex-1"><div className="label">Royal Stack</div>{picker}</div>
          <button onClick={() => signOutOwner()} className="btn btn-ghost py-1.5 text-xs">Sign out</button>
        </header>
        <nav className="lg:hidden flex overflow-x-auto border-b border-line text-sm bg-surface px-1">
          {nav.flatMap((g) => g.items).map((i) => <button key={i.id} onClick={() => setTab(i.id)} className={`px-3 py-2.5 whitespace-nowrap font-medium ${tab === i.id ? "border-b-2 border-accent text-ink" : "text-muted"}`}>{i.label}</button>)}
        </nav>
        <div key={`head-${tab}`} className="page-head reveal"><div><h1>{TITLES[tab][0]}</h1><p>{TITLES[tab][1]}</p></div></div>
      <div key={tab} className="flex-1 overflow-y-auto reveal">
        {tab === "overview" && <OverviewTab store={store} />}
        {tab === "inventory" && <InventoryTab store={store} />}
        {tab === "reorders" && <ReordersTab store={store} />}
        {tab === "signals" && <SignalsTab store={store} />}
        {tab === "customers" && <CustomersTab store={store} />}
        {tab === "offers" && <OffersTab store={store} />}
        {tab === "loss" && <LossTab store={store} />}
        {tab === "connectors" && <ConnectorsTab store={store} />}
        {tab === "setup" && <SetupTab store={store} newPin={newPin} />}
        {tab === "exits" && <ExitsTab store={store} />}
        {tab === "chat" && <OwnerChat store={store} />}
      </div>
      </div>
    </div>
  );
}

/** The frame around every screen before the dashboard. A green brand panel with the one-line promise on wide screens; the form beside it. */
function AuthShell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  return (
    <div data-theme="owner" className="min-h-dvh grid lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] bg-bg text-ink">
      <aside className="hidden lg:flex flex-col justify-between p-10 bg-accent text-accent-ink">
        <div className="flex items-center gap-3"><span className="w-9 h-9 rounded-md bg-white/15 grid place-items-center font-semibold" aria-hidden>R</span><span className="font-semibold text-lg">Royal Stack</span></div>
        <div className="space-y-6">
          <BrandBars />
          <h2 className="text-3xl font-semibold leading-tight max-w-md text-white">One AI commerce agent, one inventory truth.</h2>
          <ul className="space-y-2 text-[15px] text-white/85 max-w-md reveal-stagger">
            <li>See what sells, what runs low and what to reorder, with a reason.</li>
            <li>Shoppers ask by voice in the aisle; the answer comes from your stock.</li>
            <li>Your billing software stays the source of truth.</li>
          </ul>
        </div>
        <p className="text-sm text-white/70">For shop owners and staff.</p>
      </aside>
      <main className="flex flex-col">
        <header className="lg:hidden flex items-center gap-3 px-5 py-3 border-b border-line bg-surface">
          <span className="w-7 h-7 rounded-md bg-accent text-accent-ink grid place-items-center font-semibold text-sm" aria-hidden>R</span>
          <div className="leading-tight"><div className="font-semibold">Royal Stack</div><div className="label">Owner dashboard</div></div>
          <span className="flex-1" /><Link href="/" className="text-sm text-muted underline">Shopper app</Link>
        </header>
        <div className="flex-1 flex items-start sm:items-center justify-center p-4 sm:p-10">
          <div className={`reveal card w-full ${wide ? "max-w-lg" : "max-w-md"} p-6 sm:p-8 space-y-4`}>{children}</div>
        </div>
      </main>
    </div>
  );
}

/** Twelve bars rising once on load: a stock ledger filling up. Decorative, hidden from screen readers. */
function BrandBars() {
  const heights = [34, 52, 44, 70, 58, 86, 64, 96, 78, 110, 90, 120];
  return (
    <svg viewBox="0 0 260 130" className="w-64 h-32" aria-hidden>
      {heights.map((h, i) => <rect key={i} x={i * 21} y={130 - h} width="14" height={h} rx="3" className="bar" style={{ animationDelay: `${i * 70}ms`, fill: `rgba(255,255,255,${0.3 + i * 0.05})` }} />)}
    </svg>
  );
}

function Skeleton({ rows = 3 }: { rows?: number }) {
  return <div className="space-y-2 w-full">{Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton h-10 w-full" style={{ animationDelay: `${i * 120}ms` }} />)}</div>;
}

/** Google, or email and password. New password accounts must verify the address before the API lets them own or join a store. */
function OwnerSignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ text: string; bad: boolean } | null>(null);
  const run = async (fn: () => Promise<unknown>, okText?: string) => {
    setBusy(true); setMsg(null);
    try { await fn(); if (okText) setMsg({ text: okText, bad: false }); } catch (e) { setMsg({ text: authMessage(e), bad: true }); }
    setBusy(false);
  };
  return (
    <AuthShell>
      <div><h1 className="text-2xl font-semibold">Sign in</h1><p className="text-muted text-sm mt-1">For shop owners and staff. Use the Google account or email your store knows.</p></div>
      <button onClick={() => run(signInWithGoogle)} disabled={busy} className="btn btn-primary w-full py-3">Continue with Google</button>
      <div className="flex items-center gap-3 text-xs text-muted"><span className="flex-1 border-t border-line" />or with email<span className="flex-1 border-t border-line" /></div>
      <form onSubmit={(e) => { e.preventDefault(); run(() => signInWithEmail(email, password)); }} className="space-y-3">
        <label className="block text-sm font-medium">Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required className="field mt-1" /></label>
        <label className="block text-sm font-medium">Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" minLength={6} required className="field mt-1" /></label>
        <div className="flex gap-2">
          <button type="submit" disabled={busy || !email || !password} className="btn btn-ink flex-1 py-2.5">Sign in</button>
          <button type="button" onClick={() => run(() => createOwnerAccount(email, password), "Account created. Check your inbox for the verification link.")} disabled={busy || !email || password.length < 6} className="btn btn-ghost flex-1 py-2.5">Create account</button>
        </div>
      </form>
      <button onClick={() => run(() => resetPassword(email), "If that address has an account, a reset link is on its way.")} disabled={busy || !email} className="text-xs text-muted underline">Forgot password?</button>
      {msg && <p className={`chip ${msg.bad ? "chip-bad" : "chip-good"} whitespace-normal`}>{msg.text}</p>}
      <p className="text-xs text-muted">New here? Create an account, verify the email, and the dashboard opens with “Register your shop”. Staff use the email their owner added.</p>
    </AuthShell>
  );
}

/** Waits for the address to be verified: checks on load, every few seconds, and whenever the tab regains focus,
 *  so clicking the link in the mail is enough. An account that no longer exists drops back to the sign-in page. */
function VerifyEmail({ email, onVerified }: { email: string; onVerified: () => void }) {
  const [msg, setMsg] = useState("");
  const [checking, setChecking] = useState(false);
  const check = useCallback(async (manual = false) => {
    setChecking(true);
    try {
      if (await refreshVerified()) { onVerified(); return; }
      if (manual) setMsg("Not verified yet. Open the link in the email, then this page continues by itself.");
    } catch (e) {
      const code = (e as { code?: string }).code ?? "";
      if (code.includes("user-token-expired") || code.includes("user-not-found") || code.includes("user-disabled")) {
        await signOutOwner();                                  // the account is gone: back to the sign-in page
        return;
      }
      setMsg(authMessage(e));
    } finally { setChecking(false); }
  }, [onVerified]);
  useEffect(() => {
    const first = setTimeout(() => check(), 0);            // first check after mount, not during the effect itself
    const id = setInterval(() => check(), 5000);
    const onFocus = () => check();
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    return () => { clearTimeout(first); clearInterval(id); window.removeEventListener("focus", onFocus); document.removeEventListener("visibilitychange", onFocus); };
  }, [check]);
  return (
    <AuthShell>
      <div><h1 className="text-2xl font-semibold">Verify your email</h1><p className="text-muted text-sm mt-1">We sent a link to <b className="text-ink">{email}</b>. Open it in your mail app; this page continues on its own once the address is verified.</p></div>
      <p className="text-xs text-muted">If the link page says it has expired or was already used, the address is usually verified anyway (some mail apps open links ahead of you). Tap Continue.</p>
      <div className="flex flex-wrap gap-2">
        <button onClick={() => check(true)} disabled={checking} className="btn btn-primary">{checking ? "Checking" : "Continue"}</button>
        <button onClick={() => resendVerification().then(() => setMsg("Sent again. Check spam too.")).catch((e) => setMsg(authMessage(e)))} className="btn btn-ghost">Resend link</button>
        <button onClick={() => signOutOwner()} className="btn btn-ghost">Use a different email</button>
      </div>
      {msg && <p className="chip chip-muted whitespace-normal">{msg}</p>}
    </AuthShell>
  );
}

function authMessage(e: unknown): string {
  const code = (e as { code?: string }).code ?? (e as Error).message ?? "";
  if (code.includes("invalid-credential") || code.includes("wrong-password") || code.includes("user-not-found")) return "Wrong email or password.";
  if (code.includes("email-already-in-use")) return "That email already has an account. Sign in instead, or reset the password.";
  if (code.includes("weak-password")) return "Use a password of at least 6 characters.";
  if (code.includes("invalid-email")) return "That email address does not look right.";
  if (code.includes("too-many-requests")) return "Too many attempts. Wait a few minutes and try again.";
  if (code.includes("operation-not-allowed")) return "This sign-in method is not enabled for the project.";
  if (code.includes("popup-closed")) return "The Google window was closed before sign-in finished.";
  return "Could not sign in. Please try again.";
}

function Tile({ label, value, tone = "" }: { label: string; value: string | number; tone?: string }) {
  return <div className="figure"><div className="label">{label}</div><div className={`value ${tone}`}>{value}</div></div>;
}

function OverviewTab({ store }: { store: string }) {
  const [o, setO] = useState<Overview | null>(null);
  useEffect(() => { owner.overview(store).then(setO); const t = setInterval(() => owner.overview(store).then(setO), 15000); return () => clearInterval(t); }, [store]);
  if (!o) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-4 max-w-6xl">
      <div className="figures">
        <Tile label="Today's revenue" value={money(o.today.revenue)} />
        <Tile label="Orders today" value={o.today.orders} />
        <Tile label="Avg basket" value={money(o.today.avg_basket)} />
        <Tile label="Asked, not found (today)" value={o.asked_not_found} tone="text-warn" />
        <Tile label="Low stock" value={o.low_stock} tone={o.low_stock ? "text-warn" : ""} />
        <Tile label="Out of stock" value={o.out_of_stock} tone={o.out_of_stock ? "text-bad" : ""} />
        <Tile label="Reorder drafts waiting" value={o.open_drafts} />
        <Tile label="Exit flags open" value={o.open_flags} tone={o.open_flags ? "text-bad" : ""} />
      </div>
      <RevenueChart series={o.series} />
      <div className="text-sm text-muted">By channel today: {Object.entries(o.today.by_channel).map(([k, v]) => `${k} ${money(v)}`).join(" · ") || "no sales yet"}</div>
    </div>
  );
}

function RegisterForm({ email, error, onDone }: { email: string; error: string; onDone: (s: StoreDoc, pin: string) => void }) {
  const [name, setName] = useState(""); const [city, setCity] = useState(""); const [langs, setLangs] = useState<string[]>(["en"]);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(error);
  const toggle = (l: string) => setLangs(langs.includes(l) ? langs.filter((x) => x !== l) : [...langs, l]);
  async function submit() {
    setBusy(true); setErr("");
    try { const r = await owner.register({ name, city, languages: langs.length ? langs : ["en"], currency: "INR" }); onDone(r.store, r.kiosk_pin); }
    catch (e) { setErr(friendlyApiError(e)); }
    setBusy(false);
  }
  return (
    <AuthShell wide>
      <div><h1 className="text-2xl font-semibold">Register your shop</h1><p className="text-muted text-sm mt-1">Takes a minute. Everything here can be changed later in Store settings.</p></div>
      <div className="flex items-center gap-3 rounded-lg bg-surface-2 px-3 py-2 text-sm">
        <span className="w-8 h-8 rounded-full bg-accent text-accent-ink grid place-items-center font-semibold" aria-hidden>{email.slice(0, 1).toUpperCase()}</span>
        <span className="min-w-0 flex-1 truncate">Signed in as <b>{email}</b></span>
        <button type="button" onClick={() => signOutOwner()} className="text-accent font-medium whitespace-nowrap">Not you? Sign out</button>
      </div>
      <label className="block text-sm font-medium">Shop name<input id="reg-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Sri Murugan Stores" className="field mt-1" /><span className="label block mt-1">Shoppers see this name in the app; it also becomes your store’s web address.</span></label>
      <label className="block text-sm font-medium">City<input id="reg-city" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Chennai" className="field mt-1" /></label>
      <div className="text-sm font-medium">Languages your shoppers use<div className="flex gap-2 mt-1.5">{[["en", "English"], ["ta", "தமிழ்"], ["hi", "हिन्दी"]].map(([k, l]) => <button key={k} type="button" onClick={() => toggle(k)} className={`chip px-3 py-1.5 ${langs.includes(k) ? "bg-ink text-bg" : "chip-muted"}`}>{l}</button>)}</div><span className="label block mt-1">The assistant answers in whichever of these a shopper speaks.</span></div>
      {err && <p className="chip chip-bad whitespace-normal">{err}</p>}
      <button onClick={submit} disabled={busy || name.trim().length < 3} className="btn btn-primary w-full py-3">{busy ? "Creating your shop" : "Create my shop"}</button>
      <p className="text-xs text-muted">Already own a store with a different account? <button type="button" onClick={() => signOutOwner()} className="underline">Switch account</button>.</p>
    </AuthShell>
  );
}

/** The API could not be reached or answered with an error: say where the dashboard is looking, do not pretend the account has no stores. */
function ServerError({ error, email, retry }: { error: string; email: string; retry: () => void }) {
  const local = API.includes("localhost") || API.includes("127.0.0.1");
  return (
    <AuthShell>
      <div><h1 className="text-2xl font-semibold">Can’t reach the store server</h1><p className="text-muted text-sm mt-1">Signed in as {email}, but the dashboard could not load your stores from <span className="mono">{API}</span>.</p></div>
      <p className="chip chip-bad whitespace-normal">{error}</p>
      {local
        ? <p className="text-sm text-muted">This is a local build pointing at a local API. Start the backend with <span className="mono">uvicorn app.main:app --port 8080</span>, or set <span className="mono">NEXT_PUBLIC_API_URL</span> to the live API and rebuild. Your stores live on the deployed site either way.</p>
        : <p className="text-sm text-muted">Check your connection and try again. If it keeps failing, the API may be deploying; it is usually back within a minute.</p>}
      <div className="flex gap-2">
        <button onClick={retry} className="btn btn-primary">Try again</button>
        <button onClick={() => signOutOwner()} className="btn btn-ghost">Sign out</button>
      </div>
    </AuthShell>
  );
}

function friendlyApiError(e: unknown): string {
  const m = (e as Error).message ?? "";
  if (m === "Not Found") return `The API at ${API} does not know this route. Is the backend running, and is NEXT_PUBLIC_API_URL pointing at it?`;
  if (m.includes("verified email")) return "Verify your email first, then register.";
  if (m.includes("Failed to fetch") || m.includes("NetworkError")) return `Could not reach ${API}.`;
  return m || "Something went wrong. Please try again.";
}

function SetupTab({ store, newPin }: { store: string; newPin: string }) {
  const [doc, setDoc] = useState<StoreDoc | null>(null);
  const [aisles, setAisles] = useState<string[]>([]);
  const [brand, setBrand] = useState({ tagline: "", greeting: "", accent: "#27a36e" });
  const [team, setTeam] = useState<{ owner_emails: string[]; staff_emails: string[] } | null>(null);
  const [staffEmail, setStaffEmail] = useState("");
  const [pay, setPay] = useState({ key_id: "", key_secret: "" });
  const [qr, setQr] = useState<{ entrance_url: string; aisles: { aisle: string; url: string }[] } | null>(null);
  const [msg, setMsg] = useState("");
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [savingMap, setSavingMap] = useState(false);
  const load = () => owner.store(store).then((d) => { setDoc(d); setAisles(d.floor_map.map((a) => a.aisle)); setBrand({ tagline: d.brand.tagline, greeting: d.brand.greeting, accent: d.brand.accent }); });
  useEffect(() => {
    load(); owner.team(store).then(setTeam).catch(() => {}); owner.qr(store).then(setQr).catch(() => {});
    owner.inventory(store).then((rows) => setCounts(rows.reduce((m, r) => (r.aisle ? { ...m, [r.aisle]: (m[r.aisle] ?? 0) + 1 } : m), {} as Record<string, number>))).catch(() => {});
  }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function save(body: Parameters<typeof owner.patchStore>[1], note: string) { await owner.patchStore(store, body); setMsg(note); load(); owner.qr(store).then(setQr).catch(() => {}); }
  async function saveMap(fm: Aisle[]) { setSavingMap(true); try { await save({ floor_map: fm }, "Floor map saved. Shoppers see it on their next visit."); } catch (e) { setMsg((e as Error).message); } setSavingMap(false); }
  if (!doc) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-6 max-w-4xl">
      {newPin && <div className="card border-accent p-3 text-sm"><b>Your exit kiosk PIN is {newPin}.</b> It is also shown in the Loss tab under Controls. Enter it once on the tablet at the exit.</div>}
      {msg && <div className="chip chip-good">{msg}</div>}
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">1. Products</h2>
        <p className="text-sm text-muted">Import a CSV from your billing software in the Connectors tab, or add products one by one from the Inventory tab by scanning their barcodes.</p>
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">2. Floor map</h2>
        <p className="text-sm text-muted">Draw your shop the way it is laid out. Shoppers see this map with the route to the product they asked for, and the assistant uses the aisle names in directions. {aisles.length} aisle{aisles.length === 1 ? "" : "s"} so far.</p>
        <FloorMapEditor key={doc.floor_map.map((a) => `${a.aisle}:${a.x},${a.y},${a.w},${a.h}`).join("|")} aisles={doc.floor_map} counts={counts} saving={savingMap} onSave={saveMap} />
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">3. Brand</h2>
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <label>Tagline<input value={brand.tagline} onChange={(e) => setBrand({ ...brand, tagline: e.target.value })} placeholder="Fresh every day" className="field mt-1" /></label>
          <label>Accent colour<div className="flex items-center gap-2 mt-1"><input type="color" value={brand.accent} onChange={(e) => setBrand({ ...brand, accent: e.target.value })} className="h-10 w-14 rounded border border-line bg-transparent" /><span className="mono text-xs">{brand.accent}</span></div></label>
          <label className="sm:col-span-2">Assistant greeting<input value={brand.greeting} onChange={(e) => setBrand({ ...brand, greeting: e.target.value })} placeholder="Vanakkam! Welcome to Sri Murugan Stores." className="field mt-1" /></label>
        </div>
        <button onClick={() => save(brand, "Brand saved")} className="btn btn-primary py-2">Save brand</button>
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">4. QR codes</h2>
        <p className="text-sm text-muted">Print the entrance code for the door and one code per aisle. Shoppers scan with their phone camera; no app needed.</p>
        {qr && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 print:grid-cols-3">
            {[{ aisle: "Entrance", url: qr.entrance_url }, ...qr.aisles].map((q) => (
              <div key={q.aisle} className="card p-3 flex flex-col items-center gap-2 text-center">
                <div className="bg-white p-1 rounded"><QRCodeSVG value={q.url} size={120} /></div>
                <div className="text-xs font-semibold">{doc.name}</div><div className="eyebrow">{q.aisle}</div>
              </div>
            ))}
          </div>
        )}
        <button onClick={() => window.print()} className="btn btn-ghost py-2">Print this page</button>
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">Team</h2>
        <p className="text-sm text-muted">Staff can run the exit kiosk and record shelf counts. They cannot approve orders, change settings or see customers.</p>
        {team && <ul className="text-sm">{team.owner_emails.map((e) => <li key={e} className="flex justify-between py-1 border-t border-line"><span>{e}</span><span className="chip chip-accent">owner</span></li>)}
          {team.staff_emails.map((e) => <li key={e} className="flex justify-between py-1 border-t border-line"><span>{e}</span><button onClick={async () => setTeam({ ...team, ...(await owner.removeStaff(store, e)) })} className="text-xs text-bad underline">remove</button></li>)}</ul>}
        <div className="flex gap-2"><input value={staffEmail} onChange={(e) => setStaffEmail(e.target.value)} placeholder="staff@gmail.com" className="field flex-1" /><button onClick={async () => { if (team) setTeam({ ...team, ...(await owner.addStaff(store, staffEmail)) }); setStaffEmail(""); }} className="btn btn-primary py-2">Add staff</button></div>
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">Payments</h2>
        <p className="text-sm text-muted">Status: <span className={`chip ${doc.payments.provider === "razorpay" ? "chip-good" : "chip-muted"}`}>{doc.payments.provider === "razorpay" ? `Razorpay · ${doc.payments.key_id}` : "sandbox (no real money)"}</span></p>
        <div className="grid sm:grid-cols-2 gap-3 text-sm">
          <label>Razorpay key id<input value={pay.key_id} onChange={(e) => setPay({ ...pay, key_id: e.target.value })} className="field mt-1" /></label>
          <label>Razorpay key secret<input type="password" value={pay.key_secret} onChange={(e) => setPay({ ...pay, key_secret: e.target.value })} className="field mt-1" /></label>
        </div>
        <div className="flex gap-2">
          <button onClick={async () => { await owner.patchPayments(store, pay); setPay({ key_id: "", key_secret: "" }); setMsg("Payment keys saved"); load(); }} disabled={!pay.key_id || !pay.key_secret} className="btn btn-primary py-2">Save keys</button>
          <button onClick={async () => { await owner.patchPayments(store, {}); setMsg("Back to sandbox"); load(); }} className="btn btn-ghost py-2">Use sandbox</button>
        </div>
      </section>
    </div>
  );
}

function ExitsTab({ store }: { store: string }) {
  const [data, setData] = useState<{ summary: Loss["summary"]; items: Loss["recent"] } | null>(null);
  useEffect(() => { owner.verifications(store).then(setData); }, [store]);
  if (!data) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-3 max-w-4xl">
      <div className="figures"><Tile label="Exits (7d)" value={data.summary.total} /><Tile label="Clear" value={data.summary.clear} /><Tile label="Spot checks" value={data.summary.spot_check} tone="text-warn" /><Tile label="Flags" value={data.summary.flag} tone="text-bad" /></div>
      <ul className="text-sm">{data.items.slice(0, 30).map((v) => <li key={v.verification_id} className="border-t border-line py-1.5"><span className={`chip ${v.verdict === "flag" ? "chip-bad" : v.verdict === "spot_check" ? "chip-warn" : "chip-good"}`}>{v.verdict}</span> · {new Date(v.created_at).toLocaleString()} {v.reasons.length > 0 && <span className="text-muted">· {v.reasons.join("; ")}</span>}</li>)}</ul>
    </div>
  );
}

function AddByScan({ store, onSaved }: { store: string; onSaved: () => void }) {
  const [code, setCode] = useState("");
  const [form, setForm] = useState({ name: "", brand: "", category: "", price: "", mrp: "", on_hand: "", aisle: "" });
  const [looking, setLooking] = useState(false);
  const [found, setFound] = useState<boolean | null>(null);
  const [msg, setMsg] = useState("");
  async function onCode(c: string) {
    setCode(c); setLooking(true); setFound(null);
    try { const r = await owner.lookup(store, c); setFound(r.found); if (r.found) setForm((f) => ({ ...f, name: r.name ?? "", brand: r.brand ?? "", category: r.category ?? "" })); }
    catch { setFound(false); }
    setLooking(false);
  }
  async function save() {
    try {
      await owner.createProduct(store, { barcode: code, name: form.name, brand: form.brand, category: form.category, price: Number(form.price), mrp: form.mrp ? Number(form.mrp) : undefined, on_hand: Number(form.on_hand), aisle: form.aisle || undefined });
      setMsg(`Saved ${form.name}.`); setCode(""); setForm({ name: "", brand: "", category: "", price: "", mrp: "", on_hand: "", aisle: "" }); onSaved();
    } catch (e) { setMsg(`Could not save: ${(e as Error).message}`); }
  }
  if (!code) return <div className="space-y-2">{msg && <div className="chip chip-good">{msg}</div>}<BarcodeScan onCode={onCode} onClose={onSaved} /></div>;
  return (
    <div className="card p-3 space-y-2 text-sm">
      <div className="flex items-center gap-2"><span className="mono">{code}</span>{looking ? <span className="chip chip-muted">Looking up</span> : found ? <span className="chip chip-good">Found in barcode database</span> : found === false ? <span className="chip chip-warn">Unknown barcode, fill in the details</span> : null}</div>
      <div className="grid sm:grid-cols-2 gap-2">
        {([["name", "Product name"], ["brand", "Brand"], ["category", "Category"], ["price", "Selling price (₹)"], ["mrp", "MRP (₹)"], ["on_hand", "Stock on shelf"], ["aisle", "Aisle"]] as const).map(([k, l]) => (
          <label key={k} className="text-xs">{l}<input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} inputMode={["price", "mrp", "on_hand"].includes(k) ? "decimal" : undefined} className="field mt-1 py-1.5 text-sm" /></label>
        ))}
      </div>
      <div className="flex gap-2"><button onClick={save} disabled={!form.name || !form.price || form.on_hand === ""} className="btn btn-primary py-2">Save product</button><button onClick={() => setCode("")} className="btn btn-ghost py-2">Scan another</button></div>
    </div>
  );
}

function InventoryTab({ store }: { store: string }) {
  const [rows, setRows] = useState<InvRow[]>([]);
  const [filter, setFilter] = useState<"all" | InvRow["status"]>("all");
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [aisleNames, setAisleNames] = useState<string[]>([]);
  const [moving, setMoving] = useState<{ pid: string; aisle: string; bay: string; side: "left" | "right" } | null>(null);
  const load = () => owner.inventory(store).then(setRows);
  useEffect(() => { load(); owner.store(store).then((d) => setAisleNames(d.floor_map.map((a) => a.aisle))).catch(() => {}); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function move() {
    if (!moving) return;
    try { await owner.setLocation(store, moving.pid, { aisle: moving.aisle, bay: Number(moving.bay) || 1, side: moving.side }); setMoving(null); load(); }
    catch (e) { alert?.((e as Error).message); }
  }
  const shown = rows.filter((r) => (filter === "all" || r.status === filter) && r.name.toLowerCase().includes(q.toLowerCase()));
  const STATUS: Record<InvRow["status"], string> = { ok: "Healthy", low: "Low", out: "Out of stock", dead: "Not selling", overstock: "Overstocked" };
  const FILTERS: [typeof filter, string][] = [["all", "All"], ["low", "Low"], ["out", "Out of stock"], ["dead", "Not selling"], ["overstock", "Overstocked"], ["ok", "Healthy"]];
  const counts = rows.reduce((m, r) => ({ ...m, [r.status]: (m[r.status] ?? 0) + 1 }), {} as Record<string, number>);
  async function edit(r: InvRow, field: "reorder_point" | "reorder_qty") {
    const v = window.prompt?.(`${field.replace("_", " ")} for ${r.name}`, String(r[field]));
    if (v && /^\d+$/.test(v)) { await owner.patchInventory(store, r.product_id, { [field]: Number(v) }); load(); }
  }
  async function count(r: InvRow) {
    const v = window.prompt?.(`Counted on shelf for ${r.name} (system says ${r.on_hand})`);
    if (v && /^\d+$/.test(v)) { await owner.count(store, r.product_id, Number(v)); alert?.("Count recorded. See Loss tab for discrepancies."); }
  }
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        {FILTERS.map(([f, l]) => <button key={f} onClick={() => setFilter(f)} className={`chip ${filter === f ? "bg-ink text-bg" : "chip-muted"}`}>{l}{f !== "all" && counts[f] ? ` ${counts[f]}` : f === "all" ? ` ${rows.length}` : ""}</button>)}
        <input id="inv-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search products" className="field ml-auto w-56" />
        <button onClick={() => setAdding(!adding)} className="btn btn-primary py-1.5 text-sm">{adding ? "Close" : "Add by scan"}</button>
      </div>
      {adding && <AddByScan store={store} onSaved={() => { load(); }} />}
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Product</th><th>Status</th><th className="num">On hand</th><th className="num">Sold per day</th><th className="num">Days of cover</th><th className="num">Reorder at</th><th className="num">Order qty</th><th>Aisle</th><th></th></tr></thead>
          <tbody>{shown.map((r) => (
            <React.Fragment key={r.product_id}>
            <tr>
              <td className="font-medium">{r.name}</td>
              <td><span className={`status status-${r.status}`}>{STATUS[r.status]}</span></td>
              <td className="num">{r.available}</td><td className="num">{r.avg_daily ?? "–"}</td><td className="num">{r.days_of_cover ?? "–"}</td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_point")} className="mono underline decoration-dotted">{r.reorder_point}</button></td>
              <td className="text-right"><button onClick={() => edit(r, "reorder_qty")} className="mono underline decoration-dotted">{r.reorder_qty}</button></td>
              <td>{r.aisle || <span className="text-muted">not placed</span>} <button onClick={() => setMoving({ pid: r.product_id, aisle: r.aisle || aisleNames[0] || "", bay: "1", side: "left" })} className="text-xs text-accent font-medium ml-1">Move</button></td>
              <td><button onClick={() => count(r)} className="text-xs text-accent font-medium">Count shelf</button></td>
            </tr>
            {moving?.pid === r.product_id && (
              <tr><td colSpan={9} className="bg-surface-2">
                <div className="flex flex-wrap items-center gap-2 text-sm py-1">
                  <span className="text-muted">Place <b className="text-ink">{r.name}</b> in</span>
                  <select value={moving.aisle} onChange={(e) => setMoving({ ...moving, aisle: e.target.value })} className="field w-auto py-1.5">{aisleNames.map((a) => <option key={a} value={a}>{a}</option>)}</select>
                  <span className="text-muted">bay</span><input value={moving.bay} onChange={(e) => setMoving({ ...moving, bay: e.target.value })} inputMode="numeric" className="field w-16 py-1.5 mono" />
                  <select value={moving.side} onChange={(e) => setMoving({ ...moving, side: e.target.value as "left" | "right" })} className="field w-auto py-1.5"><option value="left">left side</option><option value="right">right side</option></select>
                  <button onClick={move} disabled={!moving.aisle} className="btn btn-primary py-1.5">Save</button>
                  <button onClick={() => setMoving(null)} className="btn btn-ghost py-1.5">Cancel</button>
                  {aisleNames.length === 0 && <span className="text-xs text-warn">Draw the floor map in Store settings first.</span>}
                </div>
              </td></tr>
            )}
            </React.Fragment>))}</tbody>
        </table>
        {shown.length === 0 && <p className="p-6 text-sm text-muted">{rows.length ? "Nothing matches this filter." : "No products yet. Add one by scanning its barcode, or import a file in Connectors."}</p>}
      </div>
    </div>
  );
}

function ReordersTab({ store }: { store: string }) {
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<string | null>(null);
  const load = () => owner.reorders(store).then(setDrafts);
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function makeDrafts() { setBusy(true); try { await owner.draft(store); await load(); } finally { setBusy(false); } }
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-3 max-w-6xl">
      <div className="flex items-center gap-3">
        <button onClick={makeDrafts} disabled={busy} className="btn btn-primary">{busy ? "Drafting with Gemini" : "Draft reorders now"}</button>
        <span className="text-xs text-muted">Nothing is sent to a supplier until you approve.</span>
      </div>
      {drafts.length === 0 && <p className="text-muted text-sm">No drafts yet.</p>}
      {drafts.map((d) => (
        <div key={d.po_id} className={`card p-3 space-y-2 ${d.status === "draft" ? "border-accent" : ""}`}>
          <div className="flex items-center gap-2">
            <div className="font-semibold">{d.supplier_name}</div>
            <span className={`chip ${d.status === "approved" ? "chip-good" : d.status === "rejected" ? "chip-muted" : "chip-warn"}`}><span className="dot" />{d.status}</span>
            <span className="text-xs text-muted">{d.lines.length} lines · {new Date(d.created_at).toLocaleString()}</span>
          </div>
          <p className="text-sm text-muted">{d.summary}</p>
          <ul className="text-sm space-y-1">{d.lines.map((l) => <li key={l.product_id}><b>{l.name}</b> × {l.qty} <span className="text-muted mono text-xs">· {l.available} left, point {l.reorder_point}{l.avg_daily ? `, ${l.avg_daily}/day` : ""}</span><div className="text-xs text-muted">{l.reason}</div></li>)}</ul>
          {d.status === "draft" && (
            <div className="flex gap-2">
              <button onClick={async () => { await owner.approve(store, d.po_id, {}); load(); }} className="btn btn-primary py-2">Approve</button>
              <button onClick={async () => { const r = window.prompt?.("Reason") ?? ""; await owner.reject(store, d.po_id, r); load(); }} className="btn btn-ghost py-2">Reject</button>
            </div>
          )}
          {d.status === "approved" && <button onClick={() => setOpen(open === d.po_id ? null : d.po_id)} className="text-xs underline text-muted">{open === d.po_id ? "Hide" : "Show"} supplier email</button>}
          {open === d.po_id && <pre className="text-xs whitespace-pre-wrap bg-surface-2 rounded-[10px] p-3 mono">{d.email_text}</pre>}
        </div>
      ))}
    </div>
  );
}

function SignalsTab({ store }: { store: string }) {
  const [s, setS] = useState<Signals | null>(null);
  const [days, setDays] = useState(7);
  useEffect(() => { owner.signals(store, days).then(setS); }, [store, days]);
  if (!s) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-4 max-w-4xl">
      <div className="flex gap-2 text-xs">{[1, 7, 30].map((d) => <button key={d} onClick={() => setDays(d)} className={`chip ${days === d ? "bg-ink text-bg" : "chip-muted"}`}>{d === 1 ? "Today" : `${d} days`}</button>)}</div>
      <section>
        <h2 className="text-base font-semibold">Asked for, but we don&apos;t carry it</h2>
        <p className="text-xs text-muted mb-2">Captured from shopper conversations. The assistant records these itself.</p>
        {s.not_carried.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.not_carried.map((r) => <li key={r.query} className="flex justify-between border-t border-line py-1.5"><span>{r.query} {r.source === "agent" && <span className="chip chip-accent ml-1">assistant</span>}</span><b className="mono">{r.count}×</b></li>)}</ul>}
      </section>
      <section>
        <h2 className="text-base font-semibold">Asked for, but out of stock</h2>
        {s.out_of_stock.length === 0 ? <p className="text-sm text-muted">Nothing yet.</p> : <ul className="text-sm space-y-1">{s.out_of_stock.map((r) => <li key={r.product_id} className="flex justify-between border-t border-line py-1.5"><span>{r.name}</span><span className="mono">{r.count}× · lost {money(r.lost_sales)}</span></li>)}</ul>}
      </section>
    </div>
  );
}

const SEGMENTS: Record<Customer["segment"], string> = { new: "New", regular: "Regular", vip: "VIP", at_risk: "At risk" };
const OFFER_SEGMENTS: [OfferDoc["segment"], string][] = [["all", "Everyone"], ["signed_in", "Signed-in shoppers"], ["new", "New customers"], ["regular", "Regulars"], ["vip", "VIP"], ["at_risk", "At risk (win back)"]];

function CustomersTab({ store }: { store: string }) {
  const [rows, setRows] = useState<Customer[] | null>(null);
  const [filter, setFilter] = useState<Customer["segment"] | "all">("all");
  const [editing, setEditing] = useState<{ uid: string; delta: string; reason: string } | null>(null);
  const [msg, setMsg] = useState("");
  const load = () => owner.customers(store).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!rows) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  const counts = rows.reduce((m, r) => ({ ...m, [r.segment]: (m[r.segment] ?? 0) + 1 }), {} as Record<string, number>);
  const shown = rows.filter((r) => filter === "all" || r.segment === filter);
  async function savePoints() {
    if (!editing) return;
    try { await owner.adjustPoints(store, editing.uid, Number(editing.delta), editing.reason); setMsg("Points updated."); setEditing(null); load(); }
    catch (e) { setMsg((e as Error).message); }
  }
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-3 max-w-6xl">
      <div className="figures">
        <Tile label="Signed-in customers" value={rows.length} /><Tile label="Their spend" value={money(rows.reduce((n, r) => n + r.spend, 0))} />
        <Tile label="Repeat (2+ visits)" value={rows.filter((r) => r.visits >= 2).length} /><Tile label="Points outstanding" value={rows.reduce((n, r) => n + r.points, 0)} />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <button onClick={() => setFilter("all")} className={`chip ${filter === "all" ? "chip-accent" : "chip-muted"}`}>All {rows.length}</button>
        {(Object.keys(SEGMENTS) as Customer["segment"][]).map((k) => <button key={k} onClick={() => setFilter(k)} className={`chip ${filter === k ? "chip-accent" : "chip-muted"}`}>{SEGMENTS[k]} {counts[k] ?? 0}</button>)}
      </div>
      <p className="text-xs text-muted">Only shoppers who chose to sign in appear here, with the last four digits of their number. Segments: new (one visit), regular (two or more), VIP (five visits and ₹5,000), at risk (no visit in 45 days). Target offers at a segment in the Offers tab.</p>
      {msg && <div className="chip chip-muted">{msg}</div>}
      {shown.length === 0 ? <p className="text-sm text-muted">No customers in this view.</p> : (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>Customer</th><th className="pr-2">Segment</th><th className="pr-2">Visits</th><th className="pr-2">Spend</th><th className="pr-2">Points</th><th className="pr-2">Prefers</th><th>Last visit</th></tr></thead>
          <tbody>{shown.map((r) => (
            <React.Fragment key={r.uid}>
              <tr>
                <td className="py-1.5 pr-2">{r.name || "Shopper"} <span className="text-muted mono text-xs">····{r.phone_last4}</span></td>
                <td className="pr-2"><span className={`chip ${r.segment === "vip" ? "chip-accent" : r.segment === "at_risk" ? "chip-warn" : "chip-muted"}`}>{SEGMENTS[r.segment]}</span></td>
                <td className="num">{r.visits}</td><td className="num">{money(r.spend)}</td>
                <td className="num">{r.points} <button onClick={() => setEditing({ uid: r.uid, delta: "", reason: "" })} className="text-accent text-xs font-semibold ml-1">Adjust</button></td>
                <td className="text-xs text-muted pr-2">{[...r.dietary, ...r.favourite_categories].join(", ") || "–"}</td>
                <td className="text-xs text-muted">{new Date(r.last_seen).toLocaleDateString()}</td>
              </tr>
              {editing?.uid === r.uid && (
                <tr><td colSpan={7} className="pb-2">
                  <div className="card p-2 flex flex-wrap items-center gap-2 text-sm">
                    <input value={editing.delta} onChange={(e) => setEditing({ ...editing, delta: e.target.value })} inputMode="numeric" placeholder="+50 or -20" className="field w-28 py-1.5 mono" />
                    <input value={editing.reason} onChange={(e) => setEditing({ ...editing, reason: e.target.value })} placeholder="Reason (kept in the audit log)" className="field flex-1 py-1.5 min-w-[200px]" />
                    <button onClick={savePoints} disabled={!editing.delta || !editing.reason} className="btn btn-primary py-1.5">Save</button>
                    <button onClick={() => setEditing(null)} className="btn btn-ghost py-1.5">Cancel</button>
                  </div>
                </td></tr>
              )}
            </React.Fragment>
          ))}</tbody>
        </table></div>
      )}
    </div>
  );
}

function OffersTab({ store }: { store: string }) {
  const [rows, setRows] = useState<OfferDoc[] | null>(null);
  const [form, setForm] = useState({ name: "", kind: "product" as OfferDoc["kind"], product_id: "", product_name: "", category: "", min_total: "", value_type: "percent" as "percent" | "amount", value: "", segment: "all" as OfferDoc["segment"], ends_at: "" });
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<{ product_id: string; name: string; category: string }[]>([]);
  const [msg, setMsg] = useState("");
  const load = () => owner.offers(store).then(setRows).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function find() { try { setFound(await owner.searchProducts(store, query)); } catch { setFound([]); } }
  async function create() {
    try {
      await owner.createOffer(store, { name: form.name, kind: form.kind, product_id: form.product_id, category: form.category, min_total: Number(form.min_total || 0),
        percent_off: form.value_type === "percent" ? Number(form.value) : 0, amount_off: form.value_type === "amount" ? Number(form.value) : 0,
        segment: form.segment, ends_at: form.ends_at ? new Date(form.ends_at + "T23:59:59").toISOString() : null });
      setMsg("Offer is live."); setForm({ ...form, name: "", value: "", product_id: "", product_name: "" }); load();
    } catch (e) { setMsg((e as Error).message); }
  }
  const ready = form.name && Number(form.value) > 0 && (form.kind === "cart" || (form.kind === "product" ? !!form.product_id : !!form.category));
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-4 max-w-6xl">
      <section className="card p-4 space-y-3 text-sm">
        <div><div className="eyebrow">New offer</div><p className="text-xs text-muted">Offers apply by themselves in the cart, the best one wins per item and one per bill. No codes.</p></div>
        <div className="grid sm:grid-cols-2 gap-2">
          <label className="text-xs">Name shown to shoppers<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} maxLength={60} className="field mt-1 py-1.5 text-sm" placeholder="Dairy week" /></label>
          <label className="text-xs">Kind<select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as OfferDoc["kind"] })} className="field mt-1 py-1.5 text-sm"><option value="product">One product</option><option value="category">A category</option><option value="cart">Whole bill above an amount</option></select></label>
          {form.kind === "product" && (
            <div className="text-xs sm:col-span-2">Product
              <div className="flex gap-2 mt-1"><input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); find(); } }} placeholder="Search by name" className="field py-1.5 text-sm" /><button onClick={find} className="btn btn-ghost py-1.5">Find</button></div>
              {form.product_id && <div className="chip chip-accent mt-1">{form.product_name}</div>}
              {found.length > 0 && <div className="flex flex-wrap gap-1.5 mt-1">{found.map((p) => <button key={p.product_id} onClick={() => { setForm({ ...form, product_id: p.product_id, product_name: p.name }); setFound([]); }} className="chip chip-muted">{p.name}</button>)}</div>}
            </div>
          )}
          {form.kind === "category" && <label className="text-xs">Category<input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} maxLength={40} className="field mt-1 py-1.5 text-sm" placeholder="Dairy" /></label>}
          {form.kind === "cart" && <label className="text-xs">Bill must be above (₹)<input value={form.min_total} onChange={(e) => setForm({ ...form, min_total: e.target.value })} inputMode="decimal" className="field mt-1 py-1.5 text-sm" placeholder="500" /></label>}
          <label className="text-xs">Discount
            <div className="flex gap-2 mt-1">
              <select value={form.value_type} onChange={(e) => setForm({ ...form, value_type: e.target.value as "percent" | "amount" })} className="field w-auto py-1.5 text-sm"><option value="percent">% off</option><option value="amount">₹ off{form.kind !== "cart" ? " each" : ""}</option></select>
              <input value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} inputMode="decimal" className="field py-1.5 text-sm" placeholder={form.value_type === "percent" ? "10" : "20"} />
            </div>
          </label>
          <label className="text-xs">Who gets it<select value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value as OfferDoc["segment"] })} className="field mt-1 py-1.5 text-sm">{OFFER_SEGMENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label className="text-xs">Ends on (optional)<input type="date" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} className="field mt-1 py-1.5 text-sm" /></label>
        </div>
        <div className="flex items-center gap-2"><button onClick={create} disabled={!ready} className="btn btn-primary py-2">Create offer</button>{msg && <span className="text-xs text-muted">{msg}</span>}</div>
      </section>
      <section className="section space-y-2">
        <div className="eyebrow">Offers</div>
        {!rows ? <p className="text-muted text-sm">Loading</p> : rows.length === 0 ? <p className="text-sm text-muted">No offers yet.</p> : rows.map((o) => (
          <div key={o.offer_id} className="card p-3 flex flex-wrap items-center gap-2 text-sm">
            <div className="flex-1 min-w-[200px]"><div className="font-semibold">{o.name}</div><div className="text-xs text-muted">{o.detail} · {OFFER_SEGMENTS.find(([v]) => v === o.segment)?.[1]}{o.ends_at ? ` · until ${new Date(o.ends_at).toLocaleDateString()}` : ""}</div></div>
            <span className={`chip ${o.active ? "chip-good" : "chip-muted"}`}>{o.active ? "Live" : "Paused"}</span>
            <button onClick={() => owner.patchOffer(store, o.offer_id, { active: !o.active }).then(load)} className="btn btn-ghost py-1.5 text-xs">{o.active ? "Pause" : "Resume"}</button>
            <button onClick={() => { if (confirm(`Delete "${o.name}"?`)) owner.deleteOffer(store, o.offer_id).then(load); }} className="btn btn-ghost py-1.5 text-xs text-bad">Delete</button>
          </div>
        ))}
      </section>
    </div>
  );
}

function LossTab({ store }: { store: string }) {
  const [l, setL] = useState<Loss | null>(null);
  const [form, setForm] = useState<Partial<Loss["settings"]>>({});
  const load = () => owner.loss(store).then((x) => { setL(x); setForm(x.settings); });
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (!l) return <div className="px-4 lg:px-6"><Skeleton /></div>;
  const s = l.summary;
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-4 max-w-4xl">
      <div className="figures">
        <Tile label="Exits (7d)" value={s.total} /><Tile label="Clear" value={s.clear} /><Tile label="Spot checks" value={s.spot_check} tone="text-warn" /><Tile label="Flags" value={s.flag} tone="text-bad" />
        <Tile label="Flag rate" value={`${Math.round(s.flag_rate * 100)}%`} /><Tile label="Issues confirmed" value={s.issue_confirmed} /><Tile label="Random audits" value={`${Math.round(s.audit_rate * 100)}%`} />
      </div>
      <section>
        <h2 className="text-base font-semibold">Shrink candidates (shelf count vs system)</h2>
        {l.shrink.length === 0 ? <p className="text-sm text-muted">No discrepancies. Use &quot;count&quot; on the Inventory tab to record shelf counts.</p> :
          <ul className="text-sm">{l.shrink.map((r) => <li key={r.product_id} className="flex justify-between border-t border-line py-1.5"><span>{r.name}</span><span className="mono">{r.counted} vs {r.system} · <b>{r.difference > 0 ? "+" : ""}{r.difference}</b> · {money(r.value)}</span></li>)}</ul>}
      </section>
      <section>
        <h2 className="text-base font-semibold">Recent exits</h2>
        <ul className="text-sm">{l.recent.slice(0, 10).map((v) => <li key={v.verification_id} className="border-t border-line py-1.5"><span className={`chip ${v.verdict === "flag" ? "chip-bad" : v.verdict === "spot_check" ? "chip-warn" : "chip-good"}`}>{v.verdict}</span> · {new Date(v.created_at).toLocaleTimeString()} {v.reasons.length > 0 && <span className="text-muted">· {v.reasons.join("; ")}</span>}{v.review_outcome && <span className="text-xs"> · {v.review_outcome}</span>}</li>)}</ul>
      </section>
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">Controls</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label>Self-checkout item limit<input type="number" value={form.self_checkout_item_limit ?? ""} onChange={(e) => setForm({ ...form, self_checkout_item_limit: Number(e.target.value) })} className="field mt-1" /></label>
          <label>High-value threshold (₹)<input type="number" value={form.high_value_threshold ?? ""} onChange={(e) => setForm({ ...form, high_value_threshold: Number(e.target.value) })} className="field mt-1" /></label>
          <label>Random audit rate (0–1)<input type="number" step="0.05" value={form.audit_rate ?? ""} onChange={(e) => setForm({ ...form, audit_rate: Number(e.target.value) })} className="field mt-1" /></label>
          <label>Kiosk PIN<input value={form.kiosk_pin ?? ""} onChange={(e) => setForm({ ...form, kiosk_pin: e.target.value })} className="field mt-1" /></label>
        </div>
        <button onClick={async () => { await owner.settings(store, form); load(); }} className="btn btn-primary">Save</button>
      </section>
    </div>
  );
}

function ConnectorsTab({ store }: { store: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({ sku: "sku", name: "name", price: "price", on_hand: "on_hand", barcode: "barcode", category: "category", aisle: "aisle" });
  const [analysis, setAnalysis] = useState<{ notes: string[]; questions: string[]; confidence: number; source: string; header: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string>("");
  const [qr, setQr] = useState<{ entrance_url: string; aisles: { aisle: string; url: string }[] } | null>(null);
  async function analyse() {
    if (!file) return;
    setBusy(true); setResult("");
    try {
      const r = await owner.propose(store, file);
      setMapping(r.proposal.mapping);
      setAnalysis({ ...r.proposal, header: r.header });
    } catch (e) { setResult(`Analysis failed: ${(e as Error).message}`); }
    setBusy(false);
  }
  async function run() {
    if (!file) return;
    const clean = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v));
    try { const r = await owner.importCsv(store, file, clean); setResult(`Created ${r.created}, updated ${r.updated}, ${r.errors.length} row errors${r.errors[0] ? ` (line ${r.errors[0].line}: ${r.errors[0].message})` : ""}.`); }
    catch (e) { setResult(`Import failed: ${(e as Error).message}`); }
  }
  const fields = ["sku", "name", "price", "on_hand", "barcode", "brand", "category", "subcategory", "mrp", "unit", "aisle", "supplier_id", "reorder_point", "reorder_qty", "lead_time_days", "tags"];
  return (
    <div className="px-4 lg:px-6 pb-10 space-y-4 max-w-4xl">
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">Import products from any file</h2>
        <p className="text-xs text-muted">Export from your POS, Excel, Google Sheets or Shopify as CSV. The assistant reads the header and a few rows, proposes how the columns map to ours, and you confirm. Your data is converted by the connector, not by the model.</p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept=".csv,text/csv" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setAnalysis(null); }} className="text-sm" />
          <button onClick={analyse} disabled={!file || busy} className="btn btn-primary">{busy ? "Analysing" : "Analyse with AI"}</button>
        </div>
        {analysis && (
          <div className="card border-accent p-3 text-sm space-y-1">
            <div className="flex items-center gap-2"><b>Proposed mapping</b><span className="chip chip-accent">{analysis.source === "model" ? `AI · ${Math.round(analysis.confidence * 100)}% confident` : "heuristic"}</span></div>
            {analysis.notes.map((n) => <div key={n} className="text-muted">· {n}</div>)}
            {analysis.questions.map((q) => <div key={q} className="text-warn">? {q}</div>)}
            <div className="text-xs text-muted">Columns in your file: {analysis.header.join(", ")}</div>
          </div>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
          {fields.map((k) => <label key={k} className="text-xs">{k}{["sku", "name", "price", "on_hand"].includes(k) && <span className="text-bad">*</span>}
            {analysis ? (
              <select value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="field py-1.5 text-sm">
                <option value="">not in file</option>{analysis.header.map((h) => <option key={h} value={h}>{h}</option>)}
              </select>
            ) : <input value={mapping[k] ?? ""} onChange={(e) => setMapping({ ...mapping, [k]: e.target.value })} className="field py-1.5 text-sm" />}
          </label>)}
        </div>
        <button onClick={run} disabled={!file} className="btn btn-ink">Import with this mapping</button>
        {result && <p className="text-sm">{result}</p>}
      </section>
      <LiveSync store={store} mapping={mapping} />
      <section className="section space-y-2">
        <h2 className="text-base font-semibold">Printable QR codes</h2>
        <button onClick={() => owner.qr(store).then(setQr)} className="btn btn-ghost">Show entrance and aisle links</button>
        {qr && <ul className="text-xs break-all space-y-1"><li><b>Entrance:</b> {qr.entrance_url}</li>{qr.aisles.map((a) => <li key={a.aisle}><b>{a.aisle}:</b> {a.url}</li>)}</ul>}
      </section>
    </div>
  );
}

/** Keep the assistant in step with the shop's own system: signed webhooks in, sale events out, a CSV feed on a schedule. */
function LiveSync({ store, mapping }: { store: string; mapping: Record<string, string> }) {
  const [view, setView] = useState<SyncView | null>(null);
  const [form, setForm] = useState({ webhook_url: "", feed_url: "", feed_every_min: "15" });
  const [secret, setSecret] = useState("");
  const [msg, setMsg] = useState("");
  const load = () => owner.sync(store).then((v) => { setView(v); setForm({ webhook_url: v.settings.webhook_url, feed_url: v.settings.feed_url, feed_every_min: String(v.settings.feed_every_min) }); }).catch((e) => setMsg(e.message));
  useEffect(() => { load(); }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function save(withMapping = false) {
    try {
      const clean = Object.fromEntries(Object.entries(mapping).filter(([, v]) => v));
      setView(await owner.patchSync(store, { webhook_url: form.webhook_url, feed_url: form.feed_url, feed_every_min: Number(form.feed_every_min), ...(withMapping ? { feed_mapping: clean } : {}) }));
      setMsg(withMapping ? "Saved with the mapping above." : "Saved.");
    } catch (e) { setMsg((e as Error).message); }
  }
  async function rotate() {
    if (view?.settings.has_secret && !confirm("Rotating the secret breaks the shop system's current signature until it is updated there. Continue?")) return;
    try { setSecret((await owner.rotateSyncSecret(store)).secret); load(); } catch (e) { setMsg((e as Error).message); }
  }
  if (!view) return <section className="section space-y-2"><h2 className="text-base font-semibold">Live sync</h2><p className="text-sm text-muted">{msg || "Loading"}</p></section>;
  return (
    <section className="section space-y-3">
      <div>
        <h2 className="text-base font-semibold">Live sync with your billing system</h2>
        <p className="text-xs text-muted">Your software posts stock changes to us the moment they happen, pulls our stock, and receives every sale we take. Requests are signed with a shared secret (HMAC-SHA256 over the timestamp and body). Catalog version {view.settings.catalog_version}.</p>
      </div>
      <div className="card p-3 text-xs space-y-1 break-all">
        <div><b>Stock in:</b> POST {view.endpoints.inventory} <span className="text-muted">· body {"{event_id, rows:[{sku, on_hand, price?}]}"}</span></div>
        <div><b>Products in:</b> POST {view.endpoints.products} <span className="text-muted">· rows use the import columns (sku, name, price, on_hand, …)</span></div>
        <div><b>Stock out:</b> GET {view.endpoints.pull} <span className="text-muted">· Authorization: Bearer &lt;secret&gt;</span></div>
        <div className="text-muted">Headers for POSTs: X-Sync-Timestamp (unix seconds) and X-Sync-Signature: sha256=HMAC_SHA256(secret, timestamp + {'"."'} + body). Repeated event_ids are ignored.</div>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className={`chip ${view.settings.has_secret ? "chip-good" : "chip-warn"}`}>{view.settings.has_secret ? "Secret set" : "No secret yet"}</span>
        <button onClick={rotate} className="btn btn-ghost py-1.5 text-xs">{view.settings.has_secret ? "Rotate secret" : "Generate secret"}</button>
        {secret && <span className="mono text-xs break-all card px-2 py-1">{secret}</span>}
        {secret && <span className="text-xs text-warn">Shown once. Copy it into your billing software now.</span>}
      </div>
      <div className="grid sm:grid-cols-2 gap-2 text-sm">
        <label className="text-xs sm:col-span-2">Sale webhook URL (we POST each paid order here)<input value={form.webhook_url} onChange={(e) => setForm({ ...form, webhook_url: e.target.value })} placeholder="https://your-system.example/royalstack" className="field mt-1 py-1.5 text-sm" /></label>
        <label className="text-xs">CSV feed URL (a Sheet published as CSV, or a POS export)<input value={form.feed_url} onChange={(e) => setForm({ ...form, feed_url: e.target.value })} placeholder="https://docs.google.com/…/pub?output=csv" className="field mt-1 py-1.5 text-sm" /></label>
        <label className="text-xs">Pull every (minutes)<input value={form.feed_every_min} onChange={(e) => setForm({ ...form, feed_every_min: e.target.value })} inputMode="numeric" className="field mt-1 py-1.5 text-sm" /></label>
      </div>
      <div className="flex flex-wrap gap-2 items-center">
        <button onClick={() => save(false)} className="btn btn-primary py-2">Save</button>
        <button onClick={() => save(true)} className="btn btn-ghost py-2" title="Uses the column mapping from the import section above">Save with current mapping</button>
        <button onClick={() => owner.pullNow(store).then((r) => { setMsg(`Pull: ${JSON.stringify(r)}`); load(); })} disabled={!view.settings.feed_url} className="btn btn-ghost py-2">Pull now</button>
        <button onClick={() => owner.testWebhook(store).then((r) => { setMsg(r.ok ? "Test event delivered." : `Test failed: ${r.error}`); load(); })} disabled={!view.settings.webhook_url || !view.settings.has_secret} className="btn btn-ghost py-2">Send test event</button>
        {msg && <span className="text-xs text-muted">{msg}</span>}
      </div>
      <div className="text-xs text-muted">Feed mapping: {Object.keys(view.settings.feed_mapping).length ? Object.entries(view.settings.feed_mapping).map(([k, v]) => `${k}←${v}`).join(", ") : "not set"} · last pull {view.settings.last_pull_at ? new Date(view.settings.last_pull_at).toLocaleString() : "never"} · outbox {view.outbox.pending} waiting{view.outbox.dead ? `, ${view.outbox.dead} given up` : ""}</div>
      {view.log.length > 0 && (
        <div className="table-wrap"><table className="table">
          <thead><tr><th>When</th><th className="pr-2">Direction</th><th className="pr-2">Kind</th><th className="pr-2">Rows</th><th className="pr-2">Changed</th><th>Result</th></tr></thead>
          <tbody>{view.log.map((e, i) => <tr key={i}><td className="py-1 pr-2">{new Date(e.at).toLocaleString()}</td><td className="pr-2">{e.direction === "in" ? "In" : "Out"}</td><td className="pr-2">{e.kind}</td><td className="num">{e.rows}</td><td className="num">{e.changed}</td><td>{e.ok ? <span className="chip chip-good">ok{e.unknown?.length ? ` · unknown: ${e.unknown.slice(0, 3).join(", ")}` : ""}{e.errors ? ` · ${e.errors} row errors` : ""}</span> : <span className="chip chip-bad">{e.error || "failed"}</span>}</td></tr>)}</tbody>
        </table></div>
      )}
    </section>
  );
}

function OwnerChat({ store }: { store: string }) {
  const { session, setSession, setStore } = useApp();
  const [err, setErr] = useState("");
  useEffect(() => {
    if (session?.mode === "owner" && session.store_id === store) return;
    owner.session(store).then((s) => { setSession(s); }).catch((e) => setErr(e.message));
    import("@/lib/api").then(({ api }) => api.store(store).then(setStore).catch(() => {}));
  }, [store]);   // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <p className="p-4 chip chip-bad">{err}</p>;
  if (session?.mode !== "owner") return <p className="px-4 lg:px-6 text-muted">Starting the owner assistant</p>;
  return <div className="h-full"><Chat /></div>;
}
