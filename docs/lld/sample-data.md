# Store data tools: seed, sample activity, removal (18 Oct)

One store for the demo, DailyGoods (`dailygoods`), seeded from the full catalog, with sample activity so every owner tab
has something to show, and the two earlier stores removed.

## Tools (`infra/seed`, `infra/scripts`)
- `seed.py --store <id> --name <name> --owner-email <email> [--embed] [--skip-bq]`: store document with the floor map
  (six aisles, chiller, freezer), suppliers, then products, inventory and locations from `products.csv` through the
  same CSV connector the owner upload uses. Idempotent.
- `sample_activity.py --store <id>`: sixty days of paid orders (store and online, weekends and evenings busier, today's
  orders up to now), forty customers whose visits, spend and recency give every segment (vip, regular, new, at risk) with
  usual items from their orders, demand signals from the last week (not carried, in three languages, and out of stock
  linked to products run down to zero), low-stock lines, shelf counts with discrepancies, exit checks (mostly clear,
  some spot checks and flags) and three offers. Deterministic ids, so a re-run overwrites the same documents.
- Then `python -m app.jobs.forecast --store <id>` (from `backend/`): orders go to BigQuery, ARIMA_PLUS trains, 14-day
  forecasts come back to Firestore; days of cover, "sold per day" and reorder drafts follow from them.
- `remove_store.py --store <id> [--yes]`: dry run by default. Removes the store document tree, the sessions, carts,
  orders and verifications that point at it, its membership on user records, and its BigQuery rows and model.

## The 18 Oct move
- Backup of both old stores (every subcollection, related top-level documents, the user record) in
  `~/DFiles/aibuildercup-retail-backups/2026-10-18/` as JSON.
- DailyGoods seeded from the 1,579-product catalog; the semantic embeddings were copied from the old catalog (same
  products, same text) instead of being recomputed.
- The owner account (`thecaptainjackssparrow@gmail.com`) now lists DailyGoods only. Removal of `captain-jack-mart` and
  `demo-grocery` is the owner's call with `remove_store.py --yes`.
- Upload files for the Inventory tab: `infra/seed/DailyGoods inventory.xlsx` (the full catalog on the template) and
  `infra/seed/DailyGoods new arrivals.xlsx` (twenty products not in the catalog, matching what the demand signals say
  shoppers asked for).
