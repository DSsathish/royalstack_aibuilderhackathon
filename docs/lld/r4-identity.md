# LLD: R4 shopper identity (optional)

Shoppers stay anonymous by default. Signing in with a phone number is optional and buys them history, a profile that shapes suggestions, and (in R5) offers and points. The shop owner gets customer insight only from shoppers who chose to sign in.

## Identity
- Firebase phone sign-in on the web (invisible reCAPTCHA; Indian numbers, `+91` prefixed by the client). The project has phone sign-in enabled with three test numbers (`+91 99999 00001/2/3`, code `123456`) that never send an SMS, for demos and CI. The client sends the ID token; the API verifies it with the existing `verify_id_token` and reads `phone_number` from the claims (`auth.require_phone`).
- `POST /sessions/{id}/link` with the bearer token attaches `customer_id = uid` to the current session and records the store in `people/{uid}`. Anonymous sessions keep working unchanged.
- Orders created by a linked session carry `customer_id`. Conversation memory for a signed-in shopper is keyed by uid and store (`conversation.shopper_key`), so it spans visits at the same shop without leaking one shop's conversation to another; guests keep per-visit memory. `DELETE /sessions/{id}/link` signs out on the device: the visit continues as a guest.
- A later visit by the same signed-in shopper can reopen old receipts (`GET /orders/{id}` accepts the paying session or a session linked to the same customer).

## Customer record (`customers/{store_id}/people/{uid}`)
- `Customer(uid, store_id, phone_last4, name, language, dietary: list[str], favourite_categories: list[str], usual_items: list[product_id], substitution: ask|same_brand|any, consent_at, created_at, last_seen, visits, spend, points: int)`.
- Created on first link with the shop; `visits`, `spend`, `last_seen` and `usual_items` (products in at least two of the last 20 paid orders, most frequent first) updated at checkout confirm by `customers.record_order`; `points` lives here for R5. A missing record (account deleted after linking) is ignored, the sale stays anonymous.
- `GET /me/profile?store_id=` and `PATCH /me/profile` (bearer) read and update the profile.
- `GET /me/orders?store_id=` lists the shopper's paid orders, newest first.
- `GET /me/export` returns everything we hold (profiles per store, orders, turns); `DELETE /me` removes the profiles, the points ledgers (a subcollection does not go with its parent document), the per-store turns and the `people` index, anonymises orders and open sessions (`customer_id` cleared, in batches of 400), and writes a `customer_deleted` audit entry per store. Receipts stay because they are the shop's sales records. Signing in again afterwards starts a fresh record.

## What the assistant sees
- `prompts.customer_state(session)` reads the customer record once per turn (usual item ids resolved to names through the cached catalog); `prompts.customer_block` turns it into one short paragraph: greet by name once, preferred language, dietary limits never violated, favourite categories, usual items only when relevant, substitution preference. Text chat and live voice both include it. Guests see no change (empty block).

## Owner view
- `GET /owner/{id}/customers` (owner only): up to 500 signed-in customers ordered by spend, with last-four digits, visits, spend, points, preferences, last visit. Guests appear as counts in Overview. Phone-only Firebase users are not owners: the dashboard treats a user without an email as signed out.

## Client
- `lib/firebase.ts`: `sendOtp` / `confirmOtp` (invisible reCAPTCHA, verifier reset after a failed challenge), `firstAuthState` (resolves once persisted sign-in is restored), `phoneUser`. `lib/authed.ts` is the one bearer-token call used by both `lib/owner.ts` and `lib/me.ts`. `linkShopper(session)` links the visit and stores `{uid, name}` in app state.
- `components/PhoneSignIn.tsx`: number, code, friendly error mapping, optional Skip.
- Entrance page: after a new visit opens, a returning shopper on the same phone is linked silently; otherwise a sheet offers sign-in with one line of consent and "Skip for now". Aisle QR scans inside a visit never prompt.
- `/me`: profile (name, language, dietary chips, favourite categories, substitution), usual items with names, receipts with "Receipt" and "Buy again" (online: adds to cart) or "Where are these?" (in store: aisle per item, out of stock or no longer stocked), visits/spend/points tiles, "Download my data", "Sign out", "Delete my account" (confirm dialog).
- Chat header: "Hi, {first name}" chip linking to `/me` when signed in, "Sign in" otherwise; hidden for owner sessions. The shop page restores the chip after a reload.
- Owner dashboard: Customers tab (tiles plus table).

## Security and privacy
- Phone number is never stored in full; only the last four digits for display. The uid is the key.
- All `/me/*` routes and the link call require a token from a phone sign-in (`require_phone`); Google tokens get 403. A profile exists only for stores the shopper linked.
- Input limits: name 60, dietary 8 entries, categories 12, each entry 32 characters; language and substitution are enumerated.
- Consent timestamp recorded; export and delete are self-service; audit entry on delete. Owners see preferences and spend, never the number or the conversation.

## Tests
- `tests/test_api_me.py`: link creates the record and marks orders; visits, spend and usual items after two orders; profile patch and the prompt block; guests untouched; Google token refused; export and delete (orders and sessions anonymised, fresh record afterwards); owner listing owner-only; old receipts reopen for the same shopper only.
- `tests/conftest.py` resets the in-memory rate limiter per test since the whole suite shares one client address.
