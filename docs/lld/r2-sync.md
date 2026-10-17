# LLD: R2 data sync, webhook-first

The agent must reflect the shop's own system of record. One generic adapter covers any billing software that can call a URL or publish a CSV: signed inbound updates, a pull endpoint, outbound sale events with retries, and a scheduled feed. Shopify and other named adapters plug into the same contract later.

## Secrets (`services/secrets.py`)
- `get(name)` and `put(name, value)` wrap Secret Manager with a five-minute cache. Names: `razorpay-{store}` (payments, unchanged behaviour) and `sync-{store}`. Tests swap both for an in-memory dict.

## Store settings (`Store.sync`, `Store.catalog_version`)
- `Sync(webhook_url, feed_url, feed_mapping, feed_every_min=15, last_pull_at, has_secret)`; URLs must be https (localhost excepted for development). The public store endpoint never returns `sync`.
- `catalog_version` is bumped by `catalog.bump(store_id)` on every product write (CSV import, add-by-scan, sync). Each API instance keeps its per-store catalog cache and re-reads the version at most every two seconds; a different number reloads the cache. Inventory is always read live. Result: an owner edit or a webhook update is visible to the assistant on every instance within two seconds.

## Inbound (`api/sync.py`, `services/sync.py`)
- Signature: `X-Sync-Timestamp` (unix seconds) and `X-Sync-Signature: sha256=HMAC_SHA256(secret, timestamp + "." + raw_body)`; timestamps older than five minutes are refused; comparison is constant time; bodies above 1 MB and more than 5,000 rows are refused. A store without a secret refuses everything.
- `POST /sync/{store}/inventory` `{event_id, rows: [{sku, on_hand, price?}]}`: `on_hand` is set absolutely and `reserved` is kept, so open carts stay consistent; `price` updates the product and bumps the catalog version; unknown SKUs are returned, not created.
- `POST /sync/{store}/products` `{event_id, rows: [canonical columns]}`: the CSV connector's row shape, upserted through the same code as imports.
- `event_id` is written to `stores/{id}/sync_events` with a create-only write, so a replayed event answers `duplicate: true` and changes nothing.
- `GET /sync/{store}/inventory` with `Authorization: Bearer <secret>` returns `{sku, product_id, on_hand, reserved, available, price}` for the shop's system to pull.
- Every call appends to `stores/{id}/sync_log` (`at, direction, kind, rows, changed, unknown, event_id, ok, error`).

## Outbound (`services/sync.py::notify_sale`)
- After every paid order, `checkout.confirm` calls `notify_sale_async` (daemon thread). If the store has a `webhook_url`, we POST `{event: "sale", order_id, store_id, paid_at, channel, total, items: [{sku, product_id, qty, unit_price}]}` signed exactly like inbound calls, five-second timeout. A failure stores the payload in `stores/{id}/sync_outbox/{order_id}` with `attempts` and `next_at`; `retry_outbox` resends with backoff (1, 5, 30, 120, 480 minutes) and marks the entry `dead` after six attempts for the owner to see.
- "Send test event" from the dashboard delivers `{event: "test"}` the same way and logs the result.

## Scheduled feed (`services/sync.py::pull_feed`, `run_scheduled`)
- A Google Sheet published as CSV or any CSV URL the POS exports to, with the saved column mapping (proposed by the normalizer from a sample file). `pull_feed` downloads (5 MB cap), parses and upserts through the CSV connector, bumps the catalog, sets `last_pull_at` and logs. `run_scheduled` pulls every store whose feed is due and retries every outbox; Cloud Scheduler calls `POST /jobs/sync` every fifteen minutes with the job key.

## Owner API (`api/owner_sync.py`) and Connectors tab
- `GET /owner/{id}/sync` (settings without secrets, last 30 log entries, outbox count); `PATCH /owner/{id}/sync`; `POST /owner/{id}/sync/secret` (new secret, shown once, audit); `POST /owner/{id}/sync/pull`; `POST /owner/{id}/sync/test`. Owner only.
- Connectors tab gains "Live sync": the webhook endpoints with a copyable example, secret generation, sale webhook URL, feed URL with mapping, "Pull now", "Send test event", and the sync log.

## Conflict policy
- Firestore is the record for in-store sales (reservations and commits happen here). The external system is the record for its own stock counts: an inbound `on_hand` wins outright. Differences are visible in the sync log; a shrink candidate from large unexplained drops is a later step.

## Not in scope today
- Shopify adapter (GraphQL plus `orders/create` and `inventory_levels/update` webhooks) and POS file drops in Cloud Storage. Both implement `apply_inventory` / `apply_products` behind a verifier of their own.

## Tests
- `tests/test_sync.py`: signature, timestamp and secret checks; inventory rows keep reservations, report unknown SKUs and dedupe by event id; price updates bump the version; products webhook and pull; catalog cache reload on a version bump from elsewhere; signed sale delivery, outbox and retry; confirm triggers the notification; feed pull with a mocked download; owner settings, secret and log; public store hides sync.
- `tests/test_jobs_customers.py`: `/jobs/sync` key check.
