/** Signed-in shopper calls (phone OTP token) and the link step that ties the visit to the person. */
import { API, Order, Session } from "./api";
import { authed } from "./authed";
import { useApp } from "./store";

export type Profile = { uid: string; store_id: string; phone_last4: string; name: string; language: "auto" | "en" | "ta" | "hi"; dietary: string[];
  favourite_categories: string[]; usual_items: string[]; substitution: "ask" | "same_brand" | "any"; consent_at: string;
  visits: number; spend: number; points: number; last_seen: string };

export type LedgerEntry = { entry_id: string; kind: "earn" | "redeem" | "release" | "adjust" | "expire"; delta: number; remaining: number; reason: string; order_id: string; created_at: string; expires_at: string | null };

export const me = {
  link: (s: Session) => authed<{ customer_id: string; name: string; visits: number }>(`/sessions/${s.session_id}/link`, { method: "POST" }),
  profile: (store_id: string) => authed<Profile>(`/me/profile?store_id=${store_id}`),
  patch: (body: Partial<Profile> & { store_id: string }) => authed<Profile>("/me/profile", { method: "PATCH", body: JSON.stringify(body) }),
  orders: (store_id: string) => authed<Order[]>(`/me/orders?store_id=${store_id}`),
  points: (store_id: string) => authed<{ balance: number; min_redeem: number; entries: LedgerEntry[] }>(`/me/points?store_id=${store_id}`),
  unlink: (s: Session) => fetch(`${API}/sessions/${s.session_id}/link`, { method: "DELETE" }),
  exportAll: () => authed<unknown>("/me/export"),
  deleteAll: () => authed<{ deleted: boolean }>("/me", { method: "DELETE" }),
};

/** Attach the signed-in shopper to the current visit and remember who they are in app state. */
export async function linkShopper(s: Session): Promise<{ uid: string; name: string }> {
  const r = await me.link(s);
  const app = useApp.getState();
  app.updateSession({ ...s, customer_id: r.customer_id });
  app.setCustomer({ uid: r.customer_id, name: r.name });
  return { uid: r.customer_id, name: r.name };
}
