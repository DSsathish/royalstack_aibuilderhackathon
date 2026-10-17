# LLD: R1 self-service shops

Any shop owner signs in with Google, registers a shop, sets it up in four steps, and gets a branded shopper app, QR sheet and kiosk PIN. Staff get a reduced dashboard. Payment keys are per shop.

## Models (`app/domain/models.py`)

- `Store` gains `city: str`, `brand: Brand`, `staff_emails: list[str]`, `payments: Payments`, `created_at`.
- `Brand(accent="#27a36e", tagline="", greeting="")` — the shopper app themes itself from `accent`; the assistant greets with `greeting`.
- `Payments(provider: "mock" | "razorpay" = "mock", key_id="")` — the secret lives in Secret Manager as `razorpay-{store_id}`.
- `users/{uid}` gains `roles: {store_id: "owner" | "staff"}` alongside `stores`.

## Registration (`app/api/register.py`)

`POST /owner/register` `{name, city, languages, currency}` (verified Google email required):
1. slug from the name (`[a-z0-9-]`, 3–40 chars); uniqueness in a Firestore transaction, suffix `-2`, `-3` on collision.
2. Store document with defaults: 4 aisles A1–A4 on the standard geometry, item limit 15, high-value ₹500, audit 10%, random 6-digit kiosk PIN, `owner_emails=[email]`.
3. `users/{uid}`: add the store to `stores` and `roles[store]="owner"`.
4. Returns the store and the PIN once; the PIN is also visible later in Loss settings.

`PATCH /owner/{id}/store` — name, city, tagline, greeting, accent (hex), languages, currency, `aisles: [names]` (geometry regenerated).
`POST /owner/{id}/staff` `{email}` and `DELETE /owner/{id}/staff/{email}` — owner only.
`PATCH /owner/{id}/payments` `{key_id, key_secret}` — stores the secret, sets provider `razorpay`; empty body resets to mock.

## Roles (`app/services/auth.py`)

- `owned_stores(uid)` unchanged (owner).
- `staff_stores(uid)`: from `roles` or bootstrap from `stores.staff_emails` by verified email.
- `require_staff(store_id, uid)`: owner or staff. Applied to shelf counts, the verification listing and the kiosk review listing. Everything else stays owner-only.
- `GET /owner/me` returns `{uid, stores, roles}`.

## Payments per store (`app/services/payments.py`, `checkout.py`)

- `secret_for(store_id)` reads `razorpay-{store_id}` from Secret Manager, cached 5 minutes; `store_secret(store_id, value)` creates or adds a version.
- `checkout.intent` chooses the provider from the store's `payments`; mock when no key. The Razorpay order call and signature check use the store's key pair.

## Public store endpoint

`GET /stores/{id}` now excludes `kiosk_pin`, `audit_rate`, `owner_emails`, `staff_emails`, and `payments.key_id` stays (public key, needed by the client).

## Assistant greeting

Session state carries `store_name` and `greeting`; the instruction provider appends "You work at {store_name}. {greeting}". Applies to text and live.

## Frontend

- `/owner`: no store → Register form; after success a "Setup" tab opens with four cards: Import (existing), Aisles, Brand, QR & PIN; plus Team (staff emails) and Payments. Staff see only Inventory (counts) and Loss.
- Shopper app: `--accent` set from `store.brand.accent`; header shows name and tagline; landing page uses the store name from the entrance link.
- QR tab renders large entrance and aisle codes with the store name; "Print" uses the browser print dialog.

## Security

- Registration requires a verified email; slug validated; PIN random; one store per registration call, rate-limited per client.
- Staff cannot read customers, approve orders, change settings, or see payment keys.
- Payment secrets never return to the client; only `key_id` does.

## Tests

`test_api_register.py`: register, duplicate name slug, membership and role, patch store and aisles, staff add and access matrix, payments patch with Secret Manager mocked, public store hides private fields; `test_checkout.py`: provider from store config.
