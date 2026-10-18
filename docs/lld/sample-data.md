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
  some spot checks and flags) and three offers. Deterministic ids, so a re-run overwrites the same documents and removes sample orders an earlier run left behind.
  Stock adjustments are updates on the inventory record; reset stock to the catalog baseline before re-running if the
  catalog changed.
- Then `python -m app.jobs.forecast --store <id>` (from `backend/`): orders go to BigQuery, ARIMA_PLUS trains, 14-day
  forecasts come back to Firestore; days of cover, "sold per day" and reorder drafts follow from them.
- `remove_store.py --store <id> [--yes]`: dry run by default. Removes the store document tree, the sessions, carts,
  orders and verifications that point at it, its membership on user records, and its BigQuery rows and model.

## The 18 Oct move
- Backup of both old stores (every subcollection, related top-level documents, the user record) in
  `~/DFiles/aibuildercup-retail-backups/2026-10-18/` as JSON.
- DailyGoods seeded from the catalog; the pharmacy category (Health and First Aid, 38 lines, listed in
  `infra/seed/pharmacy-removed.txt`) was then taken out of the store, `products.csv` and the upload file, since a grocery
  is not a medical shop; 1,541 products remain; the semantic embeddings were copied from the old catalog (same
  products, same text) instead of being recomputed.
- The owner account (`thecaptainjackssparrow@gmail.com`) lists DailyGoods only; `captain-jack-mart` and `demo-grocery`
  were removed with `remove_store.py --yes` on the owner's instruction.
- Upload files for the Inventory tab: `infra/seed/DailyGoods inventory.xlsx` (the full catalog on the template) and
  `infra/seed/DailyGoods new arrivals.xlsx` (twenty products not in the catalog, matching what the demand signals say
  shoppers asked for).
