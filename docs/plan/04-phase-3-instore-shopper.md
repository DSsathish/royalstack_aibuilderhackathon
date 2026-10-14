# Phase 3: In-Store Shopper Experience

Goal: a shopper scans the entrance QR, talks to the agent, is guided to the shelf, scans items, sees a running receipt, pays in sandbox, and gets an exit QR. No app install.
Owner: frontend, with backend for session and checkout. Estimated time: 8 to 10 hours.

## 3.1 QR entry and store session

Backend:

- `POST /sessions/instore` body `{store_id, qr_token}` → validates the signed token, creates `sessions/{session_id}` with `mode=instore`, `expires_at = now + 4h`, returns `session_id` and a Firebase custom token if the user is anonymous.
- QR token: HMAC-SHA256 over `store_id|entrance|date` with `QR_SESSION_SIGNING_KEY`. Printed QR for the entrance encodes `https://<app>/s/<store_id>?t=<token>`. Rotate daily via a Scheduler job that regenerates the printable PDF (stretch; for the demo a static token for the hackathon window is fine, but document the rotation).
- Aisle QR codes encode `https://<app>/s/<store_id>?t=<token>&aisle=A3`. Scanning one inside an existing session updates `aisle_hint`.
- Owner dashboard has a "Print QR codes" page that renders entrance and aisle QRs with the `qrcode` package.

Frontend route `app/(shopper)/s/[storeId]/page.tsx`:

1. Read `t` and `aisle` from the query string.
2. Sign in anonymously with Firebase Auth (silent).
3. Call `POST /sessions/instore`, store `session_id` in `localStorage` and in Zustand state.
4. Redirect to `/shop` with the session active.
5. If the token is invalid or expired show "Scan the QR at the store entrance to start".

"Only works in the store" is enforced by: signed QR token, 4-hour session expiry, and self-checkout being disabled when `mode != instore`. Document this honestly in the deck; GPS geofencing is deliberately not used.

## 3.2 PWA shell

- `next-pwa` or a hand-written `manifest.json` + service worker for installability and an offline "reconnecting" screen. Keep the service worker minimal; do not cache API responses.
- Layout: bottom tab bar with Chat, Scan, Cart, Map. A floating mic button on Chat.
- Theme: light and dark via `prefers-color-scheme`, large tap targets, Tamil and Hindi font fallback (Noto Sans Tamil, Noto Sans Devanagari from Google Fonts).

## 3.3 Chat UI

- Message list with streaming tokens via SSE from `/agent/chat`.
- Render `action` events:
  - `show_products` → horizontal product cards (image, name, price, stock badge, "Add", "Where?").
  - `highlight_map` → inline mini-map with the aisle highlighted plus "Open map" button.
  - `cart_updated` → update cart badge and running total.
  - `checkout_ready` → button to the checkout screen.
  - `confirm_identification` → three candidate cards after an image, tap to confirm.
- Language selector (Auto, English, தமிழ், हिन्दी) in the header; sets `state.language`.
- 2D avatar: a small animated SVG head in the header that switches between idle, listening, thinking, speaking states driven by the chat state. Two hours max. 3D only in phase 7 if time allows.

## 3.4 Voice

- Mic button records with `MediaRecorder` (webm/opus on Chrome and Android, mp4/aac on iOS Safari). Stop on release or after 10 s silence.
- POST to `/agent/audio`. Show the transcript as the user's message when the server returns it.
- Speak replies with `speechSynthesis`, choosing a voice whose `lang` starts with `ta`, `hi`, or `en`. Toggle "Read aloud" in settings. If no voice for the language exists on the device, stay silent and show text.

## 3.5 Navigation and map

- `components/StoreMap.tsx` renders the store's `floor_map` as SVG: aisles as rectangles with labels, entrance and checkout markers.
- `highlight_map` action supplies `{aisle, bay, side, x, y}`; the map pulses the bay and draws a simple polyline from the current `aisle_hint` (or entrance) along the main corridor to the target. Routing is a fixed corridor graph, not pathfinding: entrance → main corridor → target aisle → bay. That is enough and reliable.
- "You are here" updates when the shopper scans an aisle QR (the Scan tab recognizes aisle QR URLs and calls `PATCH /sessions/{id}` with `aisle_hint`).

## 3.6 Barcode scan and vision scan

- Scan tab uses `@zxing/browser` `BrowserMultiFormatReader` on the rear camera. On a decoded EAN-13, call `GET /stores/{id}/products/by-barcode/{code}`, show the product sheet with "Add to cart" and quantity stepper.
- Prefer the native `BarcodeDetector` API when available (Chrome on Android) for speed, fall back to ZXing.
- "Can't find the barcode?" button captures a photo, uploads to `/uploads`, and sends a chat turn with `image_ref`; the agent calls `identify_product_from_image` and the UI shows candidates to confirm.
- Haptic feedback with `navigator.vibrate(50)` on a successful scan.

## 3.7 Cart and running receipt

- Cart tab shows every line with image, qty stepper, unit price, line total, and how it was added (scan, photo, chat).
- Sticky footer: item count, subtotal, savings (MRP minus price), total. This is always visible on every tab as a compact bar. This directly answers the Amazon finding that shoppers want to see the receipt as they shop.
- Item limit: when `items >= store.self_checkout_item_limit`, show "Self-checkout limit reached, please use a counter for more items" and disable Add. The limit is configurable by the owner.
- Backend `services/cart.py`: `add` reserves stock transactionally, `remove` releases, `get` recalculates totals server-side. The UI never computes money.

## 3.8 Checkout (sandbox)

Backend `services/checkout.py`:

1. `POST /checkout/intent` → validates cart (stock still reserved, item limit, mode instore), creates a Razorpay test order via their Orders API, returns `order_id`, `amount`, `key_id`.
2. Frontend opens Razorpay Checkout in test mode. Use the test card `4111 1111 1111 1111` or test UPI `success@razorpay`.
3. `POST /checkout/confirm` with `razorpay_payment_id`, `razorpay_order_id`, `razorpay_signature` → verify HMAC with `RAZORPAY_KEY_SECRET`, commit reservations to decrements, create `orders/{order_id}` with `status=paid`, generate `receipt_token` (signed JWT with order id and item count, 30 min expiry), stream the sale to BigQuery, log audit.
4. Response includes the receipt and the exit QR payload: `https://<app>/exit/<receipt_token>`.

If Razorpay signup is slow, implement a `MOCK_PAYMENTS=true` mode that skips the gateway and goes straight to confirm. Keep the real flow as the default and mention sandbox clearly in the demo.

Frontend `/checkout`:
- Review screen → Pay → success screen with a large exit QR, receipt lines, and "Show this at the exit".
- Receipt is also stored under the user's orders so it can be reopened from the Cart tab.

## 3.9 Optional sign-in

- "Save my receipts" prompt after first checkout: link anonymous account to Google or phone with Firebase `linkWithPopup` / `linkWithPhoneNumber`. Non-blocking.

## 3.10 Demo data hooks

- Seed ensures a scripted demo path: Tamil query for milk → aisle 2; "Aashirvaad atta" → aisle 1; "oat milk" not carried → substitute soya milk; one high-value item (a 1 kg ghee tin above threshold) for the exit flag.

## Acceptance criteria

- [x] Scanning the entrance QR on a phone opens the app and a session without any login step
- [ ] Tamil voice question returns the aisle and highlights the map (needs Gemini credits)
- [x] Barcode scan adds an item in under 2 s; photo scan returns the right candidate in top 3
- [x] Running total visible on every tab and matches the server
- [x] Item limit blocks adds beyond the configured number
- [x] Sandbox payment completes and the exit QR renders; stock in the owner dashboard decreases immediately
- [x] Session expires after 4 hours and self-checkout is unavailable outside in-store mode

## Risks

- iOS Safari camera and MediaRecorder quirks: test on a real iPhone and a real Android on day 2, not on day 4.
- SSE through Firebase Hosting rewrites to Cloud Run can buffer: call the Cloud Run URL directly from the browser with CORS enabled, rather than proxying.
- ZXing can be slow in low light: show a torch toggle where supported and accept manual barcode entry.
