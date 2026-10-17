"use client";
import { create } from "zustand";
import { CartView, Location, Product, Session, Store, loadSession, saveSession } from "./api";

export type Msg = { id: number; role: "user" | "assistant"; text: string; products?: Product[]; map?: Location; status?: string; checkout?: boolean; fromPhoto?: boolean;
  lowStock?: { product_id: string; name: string; available: number; reorder_point: number }[];
  drafts?: { po_id: string; supplier: string; lines: number; summary: string }[];
  offers?: { name: string; detail: string }[];
  snapshot?: { today: { revenue: number; orders: number; avg_basket: number }; low_stock: number; out_of_stock: number; open_drafts: number; open_flags: number; signed_in_customers: number; live_offers: number; attention: string[] };
  rows?: { columns: string[]; rows: Record<string, unknown>[] };
  facts?: { summary: string; sources: { title: string; url: string }[]; note: string;
    label?: { ingredients?: string | null; allergens?: string[]; nutrition_per_100g?: Record<string, number> | null; nutriscore?: string | null } | null } };

type State = {
  session: Session | null;
  store: Store | null;
  cart: CartView | null;
  messages: Msg[];
  highlight: Location | null;
  language: string;                       // "auto" or a code from lib/languages
  speak: boolean;
  avatar: "idle" | "listening" | "thinking" | "speaking";
  customer: { uid: string; name: string } | null;      // signed-in shopper; null for guests
  setCustomer: (c: State["customer"]) => void;
  setSession: (s: Session | null) => void;
  updateSession: (s: Session) => void;
  setStore: (s: Store | null) => void;
  setCart: (c: CartView | null) => void;
  push: (m: Omit<Msg, "id">) => number;
  patch: (id: number, m: Partial<Msg>) => void;
  setHighlight: (l: Location | null) => void;
  setLanguage: (l: State["language"]) => void;
  setSpeak: (v: boolean) => void;
  setAvatar: (a: State["avatar"]) => void;
};

let nextId = 1;
export const useApp = create<State>((set) => ({
  session: typeof window === "undefined" ? null : loadSession(),
  store: null, cart: null, messages: [], highlight: null, language: "auto", speak: true, avatar: "idle", customer: null,
  setCustomer: (customer) => set({ customer }),
  setSession: (session) => { saveSession(session); set({ session, cart: null, messages: [], highlight: null, customer: null }); },
  updateSession: (session) => { saveSession(session); set({ session }); },
  setStore: (store) => set({ store }),
  setCart: (cart) => set({ cart }),
  push: (m) => { const id = nextId++; set((s) => ({ messages: [...s.messages, { ...m, id }] })); return id; },
  patch: (id, m) => set((s) => ({ messages: s.messages.map((x) => (x.id === id ? { ...x, ...m } : x)) })),
  setHighlight: (highlight) => set({ highlight }),
  setLanguage: (language) => set({ language }),
  setSpeak: (speak) => set({ speak }),
  setAvatar: (avatar) => set({ avatar }),
}));

/** Read a reply aloud; resolves when speech ends. */
export async function sayAloud(text: string, lang: State["language"]): Promise<void> {
  const { speak, languageOf } = await import("./voice");
  await speak(text, languageOf(text, lang));
}
