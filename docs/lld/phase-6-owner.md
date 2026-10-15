# LLD: Phase 6 owner inventory intelligence

One stock truth, forecasts from BigQuery ML, reorder drafts with a Gemini rationale and human approval, demand signals from conversations, a loss view, and connectors. Numbers come from code and ML; judgment and wording come from the model; nothing is sent without approval.

---

## Owner identity

- Firebase Auth, Google provider (owner enables it once in the console). The dashboard sends the ID token as `Authorization: Bearer`.
- `require_owner` accepts a uid listed in `users/{uid}.stores`, or an email in `stores/{id}.owner_emails`; on first sign-in with a listed email the `users/{uid}` doc is created. Test shortcut `X-Test-Uid` unchanged.
- `Store.owner_emails: list[str]` seeded from `--owner-email` on the seed script.

## Sales history (`app/jobs/sales_sync.py`)

Copies paid orders from Firestore into BigQuery `retail.sales` (load job, idempotent on `order_id`) and rebuilds `retail.daily_product_sales`. Runs at the start of the forecast job. Live demo sales therefore reach the forecast on the next run.

## Forecasting (`app/jobs/forecast.py`, `app/services/forecast.py`)

- BigQuery ML `ARIMA_PLUS` on `daily_product_sales` per product (`holiday_region='IN'`), horizon 14 days. Retrained on every run (170 series, under a minute).
- Results written to `stores/{id}/forecasts/{product_id}`: `{daily: [14 floats], avg_daily, upper_daily, generated_at}`. Products with too little history get `avg_daily` from a 30-day mean instead.
- `forecast.get(store_id, product_id)` and `forecast.all(store_id)` read Firestore only; chat never waits on BigQuery.
- Trigger: `POST /jobs/forecast?store_id=` with header `X-Job-Key` equal to the `JOB_KEY` secret (Cloud Scheduler sends it daily at 02:00 IST). Also runnable as `python -m app.jobs.forecast --store demo-grocery`.

## Reorder (`app/services/reorder.py`)

- `reorder_point(avg_daily, lead_time_days, std_daily) = ceil(avg_daily × lead_time + 1.5 × std_daily)` (deterministic).
- `candidates(store_id)`: products with `available <= reorder_point`, grouped by supplier, suggested qty `max(reorder_qty, ceil(avg_daily × 14))`.
- `draft(store_id, created_by)`: one `PurchaseOrderDraft` per supplier with lines; Gemini Pro (`gemini_pro_model`) writes a one-sentence rationale per line and a summary, given forecasts, lead times, days of cover and a small festival calendar. Falls back to a template sentence if the model fails. Status `draft`.
- `approve(store_id, po_id, by, lines_override)` → status `approved`, generates the supplier email text (stored on the draft, not sent: no mail provider in scope), audit entry. `reject(store_id, po_id, by, reason)`.
- Model: `PurchaseOrderDraft(po_id, store_id, supplier_id, supplier_name, lines[{product_id, name, qty, available, reorder_point, avg_daily, reason}], summary, status: draft|approved|rejected, email_text, created_by, decided_by, decided_at, created_at)`.

## Signals and loss (`app/services/insights.py`)

- `signals(store_id, days)`: not-carried requests grouped by normalised text with counts (agent-sourced first), and out-of-stock requests with `lost_sales = count × price`.
- `shrink(store_id)`: quick counts (`stores/{id}/counts/{product_id}` = counted on_hand, when) vs system on_hand → candidates with difference and value.
- `overview(store_id)`: today's paid orders by channel, revenue, basket size, low stock count, out of stock count, open drafts, open flags, 14-day daily revenue series (BigQuery daily sales + today's Firestore orders).

## Owner API (`app/api/owner.py`), all `require_owner`

| Method | Path | Purpose |
|---|---|---|
| GET | `/owner/{id}/overview` | tiles + 14-day series |
| GET | `/owner/{id}/inventory` | products × inventory × forecast × location: available, days_of_cover, status (ok, low, out, dead, overstock) |
| PATCH | `/owner/{id}/inventory/{product_id}` | reorder_point, reorder_qty |
| POST | `/owner/{id}/counts` | `{product_id, counted}` quick count |
| GET | `/owner/{id}/reorders` | drafts, newest first |
| POST | `/owner/{id}/reorders/draft` | run `reorder.draft` now |
| POST | `/owner/{id}/reorders/{po_id}/approve` / `reject` | decisions |
| GET | `/owner/{id}/signals` | demand signals grouped |
| GET | `/owner/{id}/loss` | verification summary + shrink candidates + settings |
| PATCH | `/owner/{id}/settings` | item limit, high-value threshold, audit rate, kiosk PIN |
| GET | `/owner/{id}/me` | the store ids this user owns (dashboard bootstrap) |

Existing: `/owner/{id}/import/csv`, `/owner/{id}/qr`, `/owner/{id}/verifications`.

## Agent owner tools (`app/agent/tools.py`)

- `forecast_demand(product_id | None, horizon_days=14)` → from Firestore forecasts.
- `draft_purchase_order()` → `reorder.draft`, returns po ids and a summary. Prompt says the owner must approve in the dashboard.
- `get_anomalies(days=7)` → verification summary + shrink candidates.

## Frontend `/owner`

Single page with tabs: Overview, Inventory, Reorders, Signals, Loss, Connectors, Chat. Google sign-in gate (Firebase JS SDK, Google provider). Tiles and a 14-day revenue bar chart (inline SVG). Inventory table with filters and inline reorder-point edit. Reorder cards with approve/reject. Signals lists. Loss summary with settings form. Connectors: CSV upload with a column-mapping form. Chat reuses the chat component in owner mode (session created with the owner token).

## Tests

- `test_reorder.py`: reorder point maths, candidate grouping, draft creation with the model mocked, approve/reject state and audit.
- `test_insights.py`: signals grouping and lost sales, shrink candidates, overview counts (BigQuery part mocked).
- `test_forecast.py`: Firestore read helpers and the fallback for sparse history; BigQuery call mocked.
- `test_api_owner.py`: every endpoint happy path + 401/403, owner-by-email bootstrap, job key check.
- Live: one run of the real forecast job against BigQuery and one Gemini rationale.

## Rulings

- No email provider: approved drafts store the generated supplier email; sending is a one-line addition later.
- No separate alerts collection: alerts are derived from inventory status and shown on Overview.
- Google sign-in requires the owner to enable the provider once in the Firebase console; the dashboard shows a clear message until then.

## Findings during implementation

- BigQuery ML `ARIMA_PLUS` on 170 series × 90 days trains and forecasts in about 70 s (29 s via the deployed endpoint on a warm dataset). Milk forecasts ~8.4/day, dead-stock items near zero; 35 reorder lines across four suppliers on the first run.
- The seed's `sales` table predated order ids; the sync step adds the column if missing, so live demo sales flow into the next forecast.
- The `retail` dataset lives in the US multi-region (created with the default); queries work cross-region, so it was left as is.
- Owner chat sessions come only from `POST /owner/{id}/session` with a verified owner; the dev `/sessions` path refuses owner mode outside dev/test.
- Cloud Scheduler job `forecast-demo-grocery` runs daily at 20:30 IST with the `X-Job-Key` secret.
- Owner bootstrap by email: the first Google sign-in with an email listed in `owner_emails` creates the `users/{uid}` membership.
- Drafting with one Gemini Pro call per supplier in sequence took 84 s and one call timed out; rationales now run in parallel with low thinking and a 20 s cap, falling back to a template sentence.
- Rationale uses the Flash model with a fresh client per supplier thread: the shared client raised "client has been closed" under parallel use, and Pro exceeded 20 s on a 23-line order. Pro stays configured for future batch reasoning.

## Review fixes (fresh-eyes review)

- Owner bootstrap by email requires `email_verified` on the token; an unverified email never gains membership (test added).
- The owner's manual reorder point is a floor under the forecast-derived point; `reorder_qty = 0` means "do not reorder" (discontinued). Test added.
- Drafting skips suppliers that already have an open draft, so repeated "prepare orders" cannot duplicate drafts or model calls. Test added.
- Forecast job: order day computed in Asia/Kolkata, sparse-history fallback zero-fills missing days, SQL parameterised, ARIMA model named per store.
- Rationale calls: shared client (the "client has been closed" error came from a temporary client being garbage-collected), 12 s timeout, one retry on 504.
- Firestore client rules (deny all) deployed; API key referrer restriction and authorized domains are console settings for the owner.

Deferred minors: dashboard effects do not guard stale responses when switching stores quickly (single store in the demo); membership is not revoked when an email is removed from `owner_emails`.
