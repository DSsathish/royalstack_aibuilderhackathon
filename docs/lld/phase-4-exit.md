# LLD: Phase 4 layered exit verification

Deterministic layers decide; Gemini vision only adjusts confidence; every flag goes to a human. Bag photos are never stored.

---

## Models (`app/domain/models.py`)

- `Store` gains `audit_rate: float = 0.10` and `kiosk_pin: str = "1234"` (demo default, owner changes it in phase 6).
- `Verification(verification_id, store_id, order_id, kiosk_id, layers: Layers, verdict: clear|spot_check|flag, reasons: list[str], vision: VisionResult | None, image_hash: str, reviewed_by, review_note, review_outcome: cleared|issue_confirmed|None, created_at)`
- `Layers(receipt_ok, order_ok, count_ok: bool | None, limit_ok, high_value: list[str], random_audit: bool)`
- `VisionResult(confidence: float, visible_items: list[str], unexpected_items: list[str], notes: str, skipped: bool)`
- `Order.status` gains `verified` and `flagged` transitions; `Order.exited_at`.

## `app/services/vision.py`

**Responsibility.** One Gemini Flash call: bag photo + receipt lines → structured JSON. Conservative prompt. 8 s timeout. Any failure → `VisionResult(skipped=True, confidence=1.0)` so a model outage never blocks an exit.

**Function.** `check_bag(image: bytes, mime: str, lines: list[str]) -> VisionResult`. Uses `response_mime_type="application/json"` with a pydantic schema.

## `app/services/verification.py`

**Responsibility.** Run the layers, persist the verdict, mark the receipt used.

**Function.** `verify_exit(store_id, receipt_token, *, image: tuple[bytes, str] | None, counted_items: int | None, kiosk_id: str) -> Verification`

| # | Layer | Check | On failure |
|---|---|---|---|
| 1 | receipt | token verifies, `kind == receipt`, `store_id` matches | flag "invalid receipt" |
| 2 | order | order exists, `status == paid` (not already `verified`/`flagged`) | flag "receipt already used" / "order not paid" |
| 3 | count | if `counted_items` given: within ±1 for ≤ 10 items, ±10% above | flag "item count mismatch" |
| 4 | limit | `sum(qty) <= store.self_checkout_item_limit` | flag "over self-checkout limit" |
| 5 | high value | lines with `is_high_value` (looked up from products) | spot_check "show <item>" |
| 6 | random audit | `random() < store.audit_rate` | spot_check "random audit" |
| 7 | vision | if image: `check_bag`; `confidence < 0.5` → flag; any `unexpected_items` → flag | |

Verdict: `flag` if any flag reason; else `spot_check` if any spot reason; else `clear`.
Persist `verifications/{id}`; inside the same transaction set `orders/{id}.status` to `verified` (clear/spot_check) or `flagged`, and `exited_at`. The receipt is therefore single-use.

`review(verification_id, outcome, by, note)` — staff decision; sets `review_outcome`, and if `issue_confirmed` keeps order `flagged`, else sets `verified`.

`summary(store_id, days) -> dict` — counts by verdict and review outcome, flag rate, audit rate. Used by phase 6.

## `app/api/exit.py`

Kiosk auth: header `X-Kiosk-Pin` must equal `store.kiosk_pin`. Simple, works for a tablet without Google sign-in; the owner rotates it.

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/exit/{store_id}/verify` | multipart `receipt_token`, optional `image` (≤ 4 MB image/*), optional `counted_items`, `kiosk_id` | Verification (+ `order_summary`: items, total, paid_at) |
| POST | `/exit/{store_id}/review/{verification_id}` | `{outcome, note}` | Verification |
| GET | `/owner/{store_id}/verifications?days=7` | owner auth | `{summary, items}` |

Receipt tokens come either as the raw token or as the full exit URL `…/exit/?r=<token>`; the endpoint accepts both.

## Frontend `/kiosk`

`app/kiosk/page.tsx`, client only. Steps: PIN (saved in localStorage) → store id → scan loop (QR via the same detector as the scanner) → receipt summary → "Show your bag" camera capture → result: green auto-resets in 5 s, amber shows the item to check with "Checked, clear", red lists reasons with "Cleared" / "Issue confirmed". Every result auto-resets after the staff action. Shows the privacy line: "A photo of your bag is checked by AI and not stored."

## Tests

- `test_verification.py`: every layer with a fake order; token reuse; vision mocked (monkeypatch `vision.check_bag`); vision skipped → verdict still returned; high value → spot_check; audit rate honoured over 500 runs (±4%); review changes order status.
- `test_api_exit.py`: PIN required; verify from full exit URL; review; owner listing.
- Live vision: `test_vision_live.py` under `LIVE_GEMINI=1` with a generated test image.

## Rulings

- Kiosk PIN instead of staff Google sign-in. Cost if wrong: swap the dependency for owner auth later.
- Vision failure never blocks an exit (`skipped=True`); deterministic layers always run.
- No image storage anywhere; only a SHA-256 of the bytes.

## Rulings and findings during implementation

- Live bag check on Vertex `gemini-3.5-flash`: ~4 s typical, correctly listed an unpaid whisky bottle as unexpected on a synthetic photo. One call hit a server-side 504; the layer was skipped and the exit still produced a verdict. Timeout set to 12 s so the kiosk never hangs.
- Receipt token accepted either raw or as the full `/exit/?r=` URL, so the kiosk can scan the QR directly.
- Composite index `verifications(store_id, created_at)` added in `firestore.indexes.json` for the owner listing.
- Kiosk settings (store, PIN, name) live in the tablet's localStorage; "Settings" clears them.
