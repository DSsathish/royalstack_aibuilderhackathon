"use client";
/** Tool results become cards, maps, tables and cart updates on the assistant bubble `id`. One place for the text path
 *  (SSE events) and the live path (websocket frames). */
import { Msg, useApp } from "./store";
import { Product, api } from "./api";

export function applyAction(name: string, data: Record<string, unknown>, id: number, fromPhoto = false) {
  const { patch, setHighlight } = useApp.getState();
  if (name === "show_products") patch(id, { products: (data.products as Product[]) ?? [], fromPhoto: fromPhoto });
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

export async function refreshCart() {
  const { session, setCart } = useApp.getState();
  if (session) setCart(await api.cart(session));
}
