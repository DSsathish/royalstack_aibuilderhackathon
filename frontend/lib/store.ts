"use client";
import { create } from "zustand";
import { CartView, Location, Product, Session, Store, loadSession, saveSession } from "./api";

export type Msg = { id: number; role: "user" | "assistant"; text: string; products?: Product[]; map?: Location; status?: string; checkout?: boolean;
  lowStock?: { product_id: string; name: string; available: number; reorder_point: number }[];
  drafts?: { po_id: string; supplier: string; lines: number; summary: string }[] };

type State = {
  session: Session | null;
  store: Store | null;
  cart: CartView | null;
  messages: Msg[];
  highlight: Location | null;
  language: "auto" | "en" | "ta" | "hi";
  speak: boolean;
  avatar: "idle" | "listening" | "thinking" | "speaking";
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
  store: null, cart: null, messages: [], highlight: null, language: "auto", speak: true, avatar: "idle",
  setSession: (session) => { saveSession(session); set({ session, cart: null, messages: [], highlight: null }); },
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
