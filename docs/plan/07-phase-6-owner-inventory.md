# Phase 6: Owner Inventory Intelligence

Goal: the business side of the theme. One stock truth, demand forecasting, reorder drafts with human approval, alerts, demand signals from conversations, and a loss dashboard. This is where "improving operational efficiency" is proven.
Owner: backend for forecasting and jobs, frontend for dashboard. Estimated time: 8 to 10 hours. Depends on phase 1 and phase 2 owner tools.

## 6.1 Owner auth and dashboard shell

- Route `app/owner/*`, Firebase Auth with Google sign-in, `users/{uid}.stores[]` grants access. Seed the demo owner.
- Backend checks the Firebase ID token on every `/owner/*` endpoint and that `store_id` is in the user's stores.
- Layout: left nav with Overview, Inventory, Reorders, Signals, Loss, Connectors, Settings, Chat. Mobile responsive, owner will use a phone too.

## 6.2 Overview page

Live tiles from Firestore listeners and a few BigQuery queries:
- Today's sales by channel (store / online / WhatsApp), order count, average basket.
- Low stock count, out-of-stock count, open reorder drafts, open verification flags.
- "Asked but not found" count today.
- A 14-day sales sparkline (BigQuery `daily_product_sales` aggregated).

Keep charts simple: one line chart and one bar chart with a shared palette. Load the `dataviz` guidance before building them.

## 6.3 Inventory page

- Table of products with on-hand, reserved, reorder point, days of cover (on-hand ÷ forecast daily demand), status badge.
- Filters: low stock, out of stock, dead stock (no sales in 30 days and on-hand > 0), high value.
- Inline edit of reorder point and reorder qty.
- "Quick count" entry for shrink detection: owner enters counted on-hand for a few items; difference vs system is logged as a shrink candidate.
- Export CSV.

## 6.4 Forecasting

BigQuery ML in dataset `retail`:

```sql
CREATE OR REPLACE MODEL retail.demand_arima
OPTIONS(
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'day',
  time_series_data_col = 'qty',
  time_series_id_col = 'product_id',
  auto_arima = TRUE,
  data_frequency = 'DAILY',
  holiday_region = 'IN'
) AS
SELECT product_id, day, qty
FROM retail.daily_product_sales
WHERE store_id = 'demo-grocery';
```

Forecast query:

```sql
SELECT product_id, forecast_timestamp, forecast_value, prediction_interval_lower_bound, prediction_interval_upper_bound
FROM ML.FORECAST(MODEL retail.demand_arima, STRUCT(14 AS horizon, 0.8 AS confidence_level));
```

Pipeline:
- Cloud Run job `forecast-job` (same image, entrypoint `python -m app.jobs.forecast`) runs daily at 02:00 via Cloud Scheduler. Retrains the model (fast at this scale) and writes `stores/{store_id}/forecasts/{product_id}` with 14-day values.
- `forecast_demand` agent tool reads these documents; it does not hit BigQuery at chat time.
- Gemini Pro reasoning layer (`services/reorder.py`): given low-stock items, forecasts, lead times, supplier, and a context block (upcoming festivals from a small static table, active promotions, recent demand signals), produce a reorder recommendation with a one-paragraph rationale per line. Output JSON with pydantic schema. This is the "numbers from ML, judgment from the LLM" split for the deck.

Reorder point logic (deterministic, in code):
`reorder_point = daily_forecast × lead_time_days + safety_stock`, `safety_stock = 1.5 × std of last 30 days`. Gemini can suggest an override with a reason, but the number shown is from code unless the owner accepts the override.

## 6.5 Reorder drafts and approval inbox

- Daily job after forecasting: for each product with `on_hand − reserved ≤ reorder_point`, group by supplier, call the reasoning layer, create `po_drafts` with `status=draft`.
- Owner "Reorders" page lists drafts with lines, quantities, rationale, and supplier. Buttons: Approve, Edit quantities, Reject with reason.
- Approve → `status=approved` → generates a supplier email (Gemini drafts the text, template fallback) and sends via SendGrid free tier or logs to a "sent" view if email is not set up. WhatsApp to supplier via Twilio is a stretch.
- Approve also calls the connector `push_inventory` for the on-order quantity when a connector supports it (Shopify stretch), and logs to audit.
- The owner can also ask in chat: "What should I reorder before Diwali?" → agent uses `get_low_stock`, `forecast_demand`, then `draft_purchase_order`. The draft appears in the inbox; nothing is sent without approval.

## 6.6 Demand signals page

- From `demand_signals`: group by normalized query and type over the last 7 and 30 days.
- "Not carried" list: top queries with no catalog match, with a one-click "Add to catalog" that pre-fills a product form via Gemini (name, category, suggested price range).
- "Out of stock when asked" list: products shoppers wanted but could not buy, with estimated lost sales (count × price).
- This is the slide "data no POS captures today".

## 6.7 Alerts

- Alert rules evaluated by the daily job and on each checkout: stockout risk (days of cover < lead time), overstock (days of cover > 60), dead stock, shrink candidate, verification flags.
- Stored in `stores/{store_id}/alerts`, shown on Overview and as an in-app bell. Email digest via SendGrid is a stretch.

## 6.8 Loss dashboard

- Verification outcomes over time: total exits, clear, spot check, flag, confirmed issue. Flag rate and audit rate.
- Shrink candidates from quick counts.
- Settings exposed here: self-checkout item limit, high-value threshold, random audit rate.
- Shows the owner that fraud control is working and tunable, and shows judges that we understand the shrink problem.

## 6.9 Connectors page

- CSV upload with column mapping UI (map "Item Name" → `name`, etc.), preview, import. Save the mapping per store.
- Google Sheet URL field with "Sync now" and a 15-minute schedule toggle.
- Shopify: "Connect" with store domain and token (stretch, hide if not done).
- Last sync time and row errors visible.

## 6.10 Owner chat

- Same chat component in `mode=owner`. Suggested prompts: "What's running out this week?", "Why is sugar selling more?", "Draft a reorder for Supplier A", "Any suspicious exits yesterday?".

## 6.11 Tests

- Reorder point formula unit tests.
- Draft creation groups by supplier and respects lead time.
- Approval writes audit and changes status; reject requires reason.
- Owner endpoints reject a token for another store.

## Acceptance criteria

- [x] Overview shows live sales from the in-store demo checkout within seconds
- [x] Forecast job produces 14-day forecasts for all seeded products; dashboard shows days of cover
- [x] At least one reorder draft with a Gemini rationale waits in the inbox after the job runs
- [ ] "Oat milk" demand signal from the shopper demo appears on the Signals page
- [ ] Exit verification flag from phase 4 appears on the Loss dashboard
- [x] CSV import with a custom mapping for a second store works end to end

## Risks

- BigQuery ML training needs enough history: seed 90 days, and run the model once on day 1 to confirm it trains.
- Time: dashboard pages are many. Build Overview, Inventory, Reorders, Signals first; Loss and Connectors next; Alerts bell last.
