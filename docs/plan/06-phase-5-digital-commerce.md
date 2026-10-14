# Phase 5: Digital Commerce

Goal: the same agent and the same inventory serve online shoppers through three channels: the PWA as a storefront, an embeddable widget for any existing website, and WhatsApp. This covers the "digital" half of "physical and digital commerce" and the regional social-commerce story.
Owner: frontend, backend for WhatsApp webhook. Estimated time: 6 to 8 hours. Depends on phase 2 agent API and phase 3 cart/checkout.

## 5.1 Online storefront mode

Route `app/(shopper)/shop/[storeId]/page.tsx` without a QR token.

- Creates a session with `mode=online` via `POST /sessions/online` (anonymous Firebase auth).
- Same chat component as in-store, with the online prompt block: no aisles, delivery options, order tracking.
- Home screen: search bar that is actually the chat input, category chips, "Popular this week" from BigQuery top sellers, so it feels like a store and not just a chat.
- Product page `/shop/[storeId]/p/[productId]`: full details, stock badge ("In stock online", "Only in store", "Out of stock, notify me"), "Ask about this" button that opens chat with the product in context.
- Cart and checkout reuse phase 3 components. Checkout collects a delivery address and sets `channel=online`. Stock decrements from the shared pool, so an in-store sale reduces online availability in real time. Demonstrate this in the video: buy the last unit in store, refresh the website, it shows out of stock.
- Order tracking page `/orders/[orderId]` with status timeline (paid → packed → out for delivery → delivered). Owner can advance status from the dashboard; the agent can answer "where is my order" via a `get_order_status` tool (add to the online tool set).

## 5.2 Embeddable widget

Purpose: the retailer keeps their existing website; one script tag adds the agent. This is the replacement for the browser extension idea.

Build:
- `frontend/widget/` is a separate Vite or Next.js export producing one file `widget.js` (IIFE, self-contained CSS, no framework globals leaking). Use Preact to keep it under 100 KB.
- Hosted on Firebase Hosting at `https://<app>/widget.js`.
- Embed snippet:

```html
<script src="https://<app>/widget.js" data-store="demo-grocery" data-lang="auto" defer></script>
```

- The script mounts a floating button bottom-right; tap opens a bottom sheet on mobile or a side panel on desktop with the chat. Uses the same `/agent/chat` SSE endpoint with `mode=online` and an iframe-free DOM so it works inside Shopify, WooCommerce, or any HTML page.
- Product cards link to `data-product-url-template` if the host site provides one, e.g. `/products/{handle}`, otherwise to our storefront product page.
- Deep link in: if the host page has `<meta name="retail-agent-product" content="prod_123">`, the widget opens with that product in context.
- Demo host: a static "Retailer's existing website" page under `/demo-site` that looks like a plain Shopify theme, with the widget embedded. Show this in the video.

## 5.3 WhatsApp channel

Priority: implement on 17 Oct after 5.1 and 5.2 are done. Regional judges will respond to it, and the cost is low.

Setup:
- Twilio account, WhatsApp Sandbox. Teammates join the sandbox by sending the join code from their phones.
- Store `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` in Secret Manager.

Backend `api/whatsapp.py`:

- `POST /channels/whatsapp` receives Twilio form fields (`From`, `Body`, `MediaUrl0`, `NumMedia`). Validate the Twilio signature.
- Map `From` phone to a session: `sessions` lookup by `phone`, create with `mode=online`, `channel=whatsapp` if missing.
- Media: if an image is attached, download with Twilio auth, upload to `/uploads`, pass `image_ref` so the shopper can send a product photo.
- Run the agent turn (non-streaming). Convert `actions` to WhatsApp-friendly output: product cards become numbered lines with price and stock, plus the product image as a media message for the top result. "Reply with the number to add to cart."
- Checkout on WhatsApp: agent calls `start_checkout`, we reply with a Razorpay test payment link (Payment Links API) and the storefront order URL.
- Respond with TwiML or via the REST API (REST is simpler for multiple messages).

Agent prompt tweak for `channel=whatsapp`: plain text, no markdown, max 6 lines, use numbers for choices.

## 5.4 Compatibility note for the deck

The canonical catalog and inventory layer can later publish to Google's Universal Commerce Protocol and Shopify's agentic storefront feeds. We do not build that in the hackathon; one slide states the path. This positions the project as complementary to Google's own commerce agents rather than a competitor.

## 5.5 Tests

- Online session cannot call `navigate_to` or `start_checkout` with in-store rules.
- Shared stock: an in-store order for the last unit makes the online product page show out of stock on next fetch.
- Widget loads on a plain HTML page with no console errors and no global CSS leakage (check a sample host page with aggressive CSS).
- WhatsApp webhook rejects a request with a bad Twilio signature.

## Acceptance criteria

- [ ] Online storefront: search, chat, product page, cart, sandbox checkout with address, order tracking
- [ ] Widget embedded in the demo host page with one script tag, works on mobile and desktop
- [ ] WhatsApp: text query returns products, photo query identifies a product, "1" adds to cart, checkout returns a payment link
- [ ] Buying the last unit in-store makes it out of stock online within seconds

## Risks

- Twilio sandbox needs every demo phone to join first. Do it the day before the video.
- Widget CSS conflicts with host sites: use a Shadow DOM root for the widget UI.
- Don't let WhatsApp eat the day: time-box it to 3 hours; if it slips, show the storefront and widget only and mention WhatsApp as next.
