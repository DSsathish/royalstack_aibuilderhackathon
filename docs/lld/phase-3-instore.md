# LLD: Phase 3 in-store shopper

Shopper scans the entrance QR, gets a store session, chats, scans, sees a running receipt, pays in sandbox, gets an exit QR. Backend first (test-first), then the PWA.

---

## Backend

### `app/services/qr.py`

**Responsibility.** Sign and verify the small tokens that gate entry and exit. HMAC-SHA256 with `QR_SESSION_SIGNING_KEY`, no external library.

**Functions.**
- `sign(payload: dict, ttl_s: int | None) -> str` — base64url(JSON payload + `exp`) + "." + hex HMAC.
- `verify(token) -> dict | None` — None on bad signature or expiry.
- `entrance_token(store_id) -> str` — payload `{kind: "entrance", store_id}`, no expiry (printed on paper; rotate by changing the key).
- `receipt_token(order_id, store_id, count) -> str` — payload `{kind: "receipt", order_id, store_id, count}`, 30 min expiry.

Entrance QR URL: `https://<app>/s/<store_id>?t=<token>&aisle=A3` (aisle optional, for aisle QRs).

### `app/services/checkout.py`

**Responsibility.** Turn a cart into a paid order. Sandbox only.

**Functions.**
- `intent(session) -> Order` — cart must be non-empty and open; in-store mode must not exceed the item limit; creates `orders/{order_id}` with `status="pending"`, `amount`, `payment_provider` ("mock" or "razorpay"). With Razorpay keys set, creates a Razorpay test order over HTTPS and stores `payment_ref`.
- `confirm(order_id, payment_id, signature) -> Order` — verifies the payment (mock: `signature == "mock"`; Razorpay: HMAC-SHA256 of `order_ref|payment_id` with the key secret), commits every reservation via `inventory.commit`, marks the cart `checked_out`, sets `status="paid"`, `paid_at`, `receipt_token`. Idempotent: confirming a paid order returns it unchanged.
- `get(order_id) -> Order | None`.

**Model.** `Order(order_id, store_id, session_id, cart_id, channel, items: list[CartItem], subtotal, savings, total, status: pending|paid|verified|flagged, payment_provider, payment_ref, payment_id, receipt_token, created_at, paid_at)`.

**Not in scope.** Exit verification (phase 4), BigQuery sales copy (phase 6 job), refunds.

### `app/api/shop.py`

Shopper-facing endpoints. The session id is the shopper's credential; cart and order endpoints check the session owns them.

| Method | Path | Body / params | Returns |
|---|---|---|---|
| POST | `/sessions/instore` | `{store_id, token, aisle?}` | Session (401 on bad token) |
| PATCH | `/sessions/{session_id}` | `{aisle_hint}` | Session |
| GET | `/carts/{cart_id}` | header `X-Session-Id` | cart + totals |
| POST | `/carts/{cart_id}/items` | `{product_id, qty, via}` | cart + totals, or 409 `{error}` |
| DELETE | `/carts/{cart_id}/items/{product_id}` | | cart + totals |
| POST | `/checkout/intent` | `{session_id}` | `{order_id, amount, provider, razorpay_key_id?, razorpay_order_id?}` |
| POST | `/checkout/confirm` | `{order_id, payment_id, signature, session_id}` | Order with receipt token |
| GET | `/orders/{order_id}` | header `X-Session-Id` | Order |
| GET | `/owner/{store_id}/qr` | owner auth | `{entrance_url, aisles: [{aisle, url}]}` |

Checkout is refused unless `session.mode == "instore"` or `"online"`; owner sessions cannot buy.

---

## Frontend (`frontend/`)

Next.js app router, TypeScript, Tailwind. No Firebase SDK in this phase: the server-issued session id in `localStorage` is the credential. Optional sign-in is a later phase.

| Path | File | Purpose |
|---|---|---|
| `/s/[storeId]` | `app/s/[storeId]/page.tsx` | Reads `t`, `aisle`; calls `/sessions/instore`; stores session; redirects to `/shop` |
| `/shop` | `app/shop/page.tsx` | Tab shell: Chat, Scan, Cart, Map. Sticky total bar on every tab |
| `/checkout` | `app/checkout/page.tsx` | Review, pay (mock or Razorpay), success with exit QR |
| `/receipt/[orderId]` | `app/receipt/[orderId]/page.tsx` | Re-open receipt and exit QR |

Shared code in `lib/` and `components/`:
- `lib/api.ts` — `apiUrl()`, `sessionId()`, typed fetch helpers, `streamChat()` that parses SSE into events.
- `lib/sse.ts` — pure `parseSse(chunk)` line parser (unit tested).
- `lib/store.ts` — zustand: session, cart, language, map highlight.
- `components/Chat.tsx` — messages, product cards from `show_products`, inline map from `highlight_map`, mic button, avatar.
- `components/Scanner.tsx` — `BarcodeDetector` when available else `@zxing/browser`; on decode → barcode lookup → product sheet → add.
- `components/Cart.tsx`, `components/TotalBar.tsx`, `components/StoreMap.tsx` (SVG floor map, highlight, you-are-here), `components/Avatar.tsx` (idle/listening/thinking/speaking).
- `public/manifest.json`, `app/sw.js` registration for installability only.

Voice: `MediaRecorder` → `/agent/audio`; replies read with `speechSynthesis` when a voice for the language exists.

**Tests.** Backend: pytest as before. Frontend: vitest on `lib/sse.ts` and `lib/api.ts` URL helpers; UI verified by `npm run build` and a manual run through the demo script. (Ruling: no component tests in a 4-day build.)

---

## Security notes for this phase

- Entrance token is HMAC-signed; a guessed `store_id` without a valid token gets 401.
- Session id is a 128-bit random hex; carts and orders are only reachable with the owning session id.
- Checkout totals are computed from the server cart, never from the client.
- Payment confirmation verifies an HMAC signature; the mock provider is only enabled when no Razorpay key is configured and `ENV != "prod"`.
- Receipt token expires in 30 minutes and is bound to the order id and item count.
- Images and audio are capped at 4 MB and checked by content type (phase 2).

---

## Rulings made during implementation

- **No Firebase Auth on the shopper side in this phase.** The server-issued 128-bit session id in localStorage is the credential; carts and orders are bound to it. Sign-in to save receipts is deferred. Cost if wrong: one extra phase-5 task.
- **No React component tests.** Pure helpers (`lib/sse.ts`, `lib/api.ts`) are unit-tested with vitest; the UI is verified by `next build`, lint, and an end-to-end run of the API sequence the UI performs. Browser automation was unavailable in the build session. Cost if wrong: a UI regression is caught only by a manual run.
- **Cart quantity controls are "+" and remove**, not a full stepper. Cost if wrong: minor UX.
- **Photo from the Scan tab is handed to Chat** with a fixed prompt; the multimodal model identifies the product and calls `search_products` (phase 2 ruling).
- **Receipt page reuses the checkout success component.** One source of truth for the exit QR.
- **Payment provider auto-selects:** mock unless both Razorpay keys are set. Mock is refused when `ENV=prod`.
- **Smoke test on 15 Oct** ran the full flow against the real demo store; stock was restored by re-running the seed.

## Review fixes (fresh-eyes review before merge)

Fixed, each with a regression test or a build check:
- The dev `/sessions` endpoint could mint an in-store session without an entrance token, bypassing the QR gate. Now refused; only `/sessions/instore` issues them.
- Two checkout intents on one cart could both be confirmed and commit stock twice. `confirm` now refuses when the cart is no longer open.
- Session, cart and order ids are validated as 32-char hex; non-ASCII tokens are rejected instead of raising. No more 500s from malformed ids.
- The default signing key is refused when `ENV` is not dev or test, so a Cloud Run deploy without the secret fails fast instead of accepting forged entrance codes.
- Shop page drops the session only on 401 or 404, not on a transient network error.
- Pay button stays disabled while the Razorpay modal is open.
- Scanning an aisle QR mid-visit no longer wipes chat history.
- Model failures mid-stream now arrive as an `error` event with a clear message; the UI shows the real reason.

Deferred minor:
- `cart.add` is read-modify-write without a transaction; a simultaneous add from chat and scan could drop one line while both reservations stand. Acceptable for a single-shopper demo; fix in phase 7 if time allows.
