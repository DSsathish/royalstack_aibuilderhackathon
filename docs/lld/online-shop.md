# Online shop (18 Oct)

Two front doors on the landing page: "Start the store visit" (the in-store flow, unchanged: the entrance QR starts it,
scanning stays there) and "Shop online" (a product-first screen on the same session, cart, checkout and assistant).

## Landing (`app/page.tsx`)
- Start the store visit: resumes a saved in-store session, otherwise explains that the entrance code starts a visit.
- Shop online: one shop goes straight in; several show a short list (`GET /stores`: id, name, city, tagline only).
- The owner link stays, small, below.

## Online screens (`app/shop/page.tsx` in online mode)
Tabs: Shop, Assistant, Cart. No Scan tab and no Map tab online.
- Shop (`components/OnlineHome.tsx`): search bar with a photo button (the photo goes through the assistant's existing
  "what is this product" path, results land in the Assistant tab), category chips, deals (the store's live offers with
  the products they touch), trending (most bought in the last 30 days), recommended (a signed-in shopper's usual items
  and favourite categories; otherwise the next best sellers). Cards show price, MRP, stock and "bought N times this
  month" from real orders. No ratings: there is no review data, so none are shown.
- Product sheet (`components/ProductSheet.tsx`): details, availability, quantity stepper, add to cart, "ask the
  assistant about this", and a label section (ingredients, allergens, nutrition per 100 g, dietary notes) from the same
  guarded facts lookup the assistant uses, charged to the session's lookup budget.
- Cart: a quantity stepper per line (`PATCH /carts/{id}/items/{pid}`; zero removes; in store the stepper only reduces
  because adding needs a scan). Checkout unchanged.
- Voice: online, the compact control is a floating button at the bottom right above the receipt bar, hidden while the
  status strip is open (the strip carries the orb then), so it never covers a card or the bar. In store it stays in the
  bottom bar's Talk slot.

## API (`api/online.py`)
- `GET /stores`: public list for the landing page.
- `GET /stores/{id}/home`: categories (top 12 by count), trending, recommended, deals, the shopper's segment. The
  session header personalises; without it the guest view.
- `GET /stores/{id}/products?category=&q=&limit=&offset=`: a category page (best sellers first) or a search page
  (the assistant's search, so misses still record demand signals). Every product carries `bought_30d`.
- `GET /stores/{id}/products/{pid}/facts`: `facts.lookup` for the product sheet; needs the session header.
- Popularity: units per product from paid orders of the last 30 days, cached five minutes per API instance.
- Public product payloads keep excluding cost, GST and the high-value flag.

## Providers (second pass, after this ships)
A generic MCP connector in the connector agent (URL, credentials in Secret Manager, tool mapping to the product schema)
and one demo provider hosted by Royal Stack with clearly labelled sample prices, so comparisons can be shown before any
real server is approved. Swiggy Instamart has an official MCP server with whitelist-only production access; Zepto has no
official API; Meesho's API is partner-gated. Nothing is fabricated as live data.

## Tests
`tests/test_online.py`: home ranks by real purchases and lists categories and deals; the listing filters by category and
searches; facts needs a session; the cart stepper sets, reduces and removes, and in store refuses to increase.
