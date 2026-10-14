# Phase 4: Layered Exit Verification

Goal: a self-checkout that a retailer would actually trust. Six cheap layers plus Gemini vision as a confidence signal, with a staff fallback. This directly addresses the documented self-checkout shrink problem and is the fraud focus area of the theme.
Owner: backend for logic, frontend for kiosk. Estimated time: 6 to 8 hours. Depends on phase 3 checkout.

## 4.1 Design principles

- Deterministic layers decide first. Vision only raises or lowers confidence.
- Every flag goes to a human. The system never accuses; it asks staff to check.
- Shopper privacy: the bag photo is processed in memory and discarded. Store verdict, confidence, and a SHA-256 of the image only.
- Everything is logged for the owner's loss dashboard.

## 4.2 The layers

| # | Layer | Check | Result |
|---|---|---|---|
| 1 | Receipt validity | Exit QR `receipt_token` verifies (signature, not expired, not already used) | fail → flag "invalid receipt" |
| 2 | Order state | `orders/{id}.status == paid` and not previously `verified` | fail → flag "already exited" |
| 3 | Item count | Staff or kiosk enters or the vision counts items; must be within ±1 of receipt count for ≤10 items, ±10% above | mismatch → flag |
| 4 | Item limit | Order items ≤ `self_checkout_item_limit` (defensive re-check) | fail → flag |
| 5 | High-value | Any line with `is_high_value` or price ≥ threshold | always → "spot check" prompt, low severity |
| 6 | Random audit | `random() < store.audit_rate` (default 10%, configurable; raise automatically for a shopper with a prior flag in the session) | → spot check |
| 7 | Vision assist | Gemini compares bag photo to receipt lines | returns `confidence` 0..1 and `unexpected_items[]`; confidence < 0.5 or any unexpected high-value item → flag |

Verdict:
- `clear` if layers 1 to 4 pass, no layer 5 or 6 trigger, vision confidence ≥ 0.5 or vision skipped.
- `spot_check` if only layer 5 or 6 triggered.
- `flag` otherwise, with reasons.

## 4.3 Backend

`services/verification.py`:

```python
def verify_exit(receipt_token: str, image_bytes: bytes | None, counted_items: int | None, kiosk_id: str) -> Verification
```

Steps: decode token → load order → run layers → optional vision → persist `verifications/{id}` → mark order `verified` or `flagged` → audit log → return verdict and reasons.

Vision call (`services/vision.py`):

Prompt to Gemini Flash with the image and the receipt lines as JSON:

```
You are checking a grocery self-checkout. Here is the paid receipt: [...].
Look at the photo of the shopper's bag or basket.
Return JSON only:
{ "visible_items": [{"name": "...", "qty": n, "matches_receipt_line": idx_or_null}],
  "unexpected_items": ["..."],
  "receipt_items_not_visible": [idx...],
  "confidence": 0.0-1.0,
  "notes": "short" }
Be conservative. Items hidden under others are expected; do not list them as unexpected.
```

Use `response_mime_type="application/json"` and a pydantic schema. Timeout 8 s; on timeout, skip vision and record `vision_skipped=true`.

Endpoints:

| Method | Path | Purpose |
|---|---|---|
| POST | `/exit/verify` | multipart: `receipt_token`, optional `image`, optional `counted_items` |
| POST | `/exit/{verification_id}/review` | staff sets `cleared` / `confirmed_issue`, with note |
| GET | `/owner/verifications?days=7` | list for the loss dashboard |

Receipt token is single-use: store `used_at` on the order inside the same transaction as the verdict.

## 4.4 Exit kiosk UI

Route `/kiosk/[storeId]` on a tablet near the exit, staff-only (owner login or a kiosk PIN).

Flow:
1. Big "Scan your exit QR" camera view (ZXing QR mode).
2. On decode: show receipt summary (items, total, time).
3. "Show your bag to the camera" → capture one photo → spinner "Checking…".
4. Result screen:
   - Green `clear`: "Thank you, have a nice day" with a 5 s auto reset.
   - Amber `spot_check`: "Please show your [ghee tin] to staff" with a staff button "Checked, clear".
   - Red `flag`: reasons listed for staff, buttons "Cleared" / "Issue confirmed", requires PIN.
5. All results auto-reset to step 1.

Also a **shopper-side exit** (no kiosk): the shopper's own phone shows the exit QR, staff scans it with the owner app's "Verify" screen (same endpoint, image optional). This makes the demo work even without a tablet.

## 4.5 Shrink and anomaly signals

- Each `verification` adds to daily aggregates per store: total, clear, spot_check, flag, confirmed_issue.
- `services/anomaly.py` computes for the last N days: expected on-hand (received − sold) vs counted on-hand after an owner stock count; difference above a threshold per product is a "shrink candidate". Owner can enter a quick count via CSV or the dashboard.
- These feed the owner's loss dashboard in phase 6 and the `get_anomalies` agent tool.

## 4.6 Privacy and data retention

- Image bytes never written to disk or Cloud Storage. Compute hash, call Gemini, discard.
- Store: `image_hash`, `vision_confidence`, `unexpected_items` (names only), `verdict`, `reasons`, `reviewed_by`.
- Signage text for the deck and the kiosk screen: "A photo of your bag is checked by AI and not stored."
- Retention: verifications older than 90 days are deleted by a Scheduler job (stretch; document it).

## 4.7 Tests

- Unit tests for every layer with a fake order.
- Token reuse rejected.
- Vision parse failure falls back to `vision_skipped` and still returns a verdict.
- High-value item always produces at least `spot_check`.
- Audit rate honored over 1000 simulated exits (±3%).

## Acceptance criteria

- [ ] Clear path: normal basket, valid receipt → green in under 6 s including vision
- [ ] High-value item → amber with the item named
- [ ] Reused receipt QR → red "already used"
- [ ] Vision timeout → verdict still returned, `vision_skipped=true`
- [ ] Owner sees the verification in the loss dashboard within seconds
- [ ] No image bytes anywhere in Firestore or Storage

## Risks

- Vision false positives on full bags: the prompt is conservative, confidence threshold is 0.5, and the only hard flag from vision is an unexpected high-value item. State these limits in the deck; judges reward honesty here.
- Tablet camera permissions in kiosk mode: test on the actual device on day 3.
