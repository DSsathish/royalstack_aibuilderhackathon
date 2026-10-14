# LLD: Phase 1 data foundation

Four backend modules, one seed script, one CSV connector, two routers. Each section follows the five-question format in `README.md`.

---

## `app/domain/models.py`

**Responsibility.** Pydantic models for everything stored in Firestore in this phase. Only fields that phase 1 reads or writes; later phases add their own models.

**Inputs / outputs.** Python objects ⇄ Firestore dicts via `model_dump()` / `Model(**doc)`.

**Models.**
- `Store(store_id, name, currency="INR", languages=["en","ta","hi"], self_checkout_item_limit=15, high_value_threshold=500.0, floor_map: list[Aisle])`
- `Aisle(aisle, x, y, w, h)` — SVG rectangle in a 1000×600 space.
- `Product(product_id, store_id, sku, barcode, name, brand, category, subcategory, description, price, mrp, unit, image_url, tags: list[str], substitutes: list[str], is_high_value)`
- `Location(product_id, store_id, aisle, bay, shelf, side, x, y)`
- `Inventory(product_id, store_id, on_hand, reserved=0, reorder_point, reorder_qty, lead_time_days, supplier_id)`
- `Supplier(supplier_id, store_id, name, email, lead_time_days)`
- `DemandSignal(signal_id, store_id, query_text, matched_product_id | None, type: "not_carried"|"out_of_stock"|"found", created_at)`

**Dependencies.** pydantic only.

**Not in scope.** Cart, Order, Session, Verification, PO drafts (phases 3 to 6).

---

## `app/services/db.py`

**Responsibility.** One Firestore client and the collection path helpers, so no other module spells a path.

**Functions.**
- `client() -> firestore.Client` — cached; honours `FIRESTORE_EMULATOR_HOST` automatically through the SDK.
- `store_ref(store_id)`, `products(store_id)`, `locations(store_id)`, `inventory(store_id)`, `suppliers(store_id)`, `demand_signals(store_id)` — return collection or document references.

**Dependencies.** google-cloud-firestore, `config.settings`.

**Not in scope.** Any business logic. No caching of documents.

---

## `app/services/inventory.py`

**Responsibility.** Transactional stock changes. The only module that writes `on_hand` or `reserved`.

**Functions.**
- `reserve(store_id, product_id, qty) -> bool` — in a transaction: if `on_hand - reserved >= qty` then `reserved += qty`, return True; else False.
- `release(store_id, product_id, qty)` — `reserved = max(0, reserved - qty)`.
- `commit(store_id, product_id, qty)` — `on_hand -= qty`, `reserved -= qty`, never below 0.
- `available(store_id, product_id) -> int` — `on_hand - reserved`.

**Dependencies.** db.

**Not in scope.** Reorder logic, alerts, BigQuery.

---

## `app/services/catalog.py`

**Responsibility.** Read-side product lookup for shoppers and the agent: by id, by barcode, by search. Writes demand signals when search finds nothing usable.

**Functions.**
- `get_product(store_id, product_id) -> ProductView | None` — product + available qty + location.
- `get_by_barcode(store_id, barcode) -> ProductView | None`.
- `search(store_id, query, k=6) -> list[ProductView]` — keyword score on name, brand, tags, category (case-insensitive token overlap), plus cosine score on the stored embedding when `embed_query` is available; combined, top k. Records a `DemandSignal` of type `not_carried` when zero hits, `out_of_stock` when all hits have `available == 0`, `found` otherwise.
- `embed_texts(texts) -> list[list[float]]` in `services/gemini.py` — Gemini embedding model; returns `[]` when no API key so keyword search still works.

**Data out.** `ProductView = Product + available: int + location: Location | None`.

**Dependencies.** db, inventory, gemini (optional).

**Not in scope.** Cart, pricing rules, personalisation.

**Performance.** Product list per store cached in memory for 60 s (`functools.lru_cache` with a time bucket). Only the query is embedded at request time.

---

## `app/connectors/csv_connector.py`

**Responsibility.** Turn a CSV file plus a column mapping into Product, Location, Inventory upserts.

**Inputs.** `bytes` (≤ 5 MB, ≤ 10 000 rows), `mapping: dict[canonical_field, csv_header]`, `store_id`.

**Functions.**
- `parse(data: bytes, mapping) -> tuple[list[Row], list[RowError]]` — pure, no I/O; validates required fields (`sku`, `name`, `price`, `on_hand`), coerces numbers, collects per-row errors.
- `upsert(store_id, rows) -> ImportResult(created, updated, errors)` — batched Firestore writes of 400 per batch. `product_id = store_id + "-" + slug(sku)`.

**Dependencies.** db, models. Standard library `csv`.

**Not in scope.** Google Sheets (phase 1 stretch: `sheets_connector.py` fetches the sheet as CSV via the export URL and reuses `parse`/`upsert`). Shopify.

**Security.** Size and row caps enforced before parsing. Headers in mapping must match `^[A-Za-z0-9 _./-]{1,64}$`. Numeric fields parsed with `Decimal`, rejected if negative.

---

## `app/services/auth.py`

**Responsibility.** Verify Firebase ID tokens and owner membership.

**Functions.**
- `verify_id_token(token) -> dict` — `google.oauth2.id_token.verify_firebase_token`; raises 401 on failure.
- `require_owner(store_id)` — FastAPI dependency: verifies token, checks `users/{uid}.stores` contains `store_id`, else 403.
- When `settings.env == "test"` and header `X-Test-Uid` is present, trust it. Test-only path, never enabled in prod.

**Dependencies.** google-auth, db.

---

## Routers

`app/api/catalog.py` (public, read-only):

| Method | Path | Returns |
|---|---|---|
| GET | `/stores/{store_id}` | Store |
| GET | `/stores/{store_id}/products/{product_id}` | ProductView or 404 |
| GET | `/stores/{store_id}/products/by-barcode/{barcode}` | ProductView or 404 |
| GET | `/stores/{store_id}/search?q=&k=` | list[ProductView] |

`app/api/owner_import.py` (owner-only):

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/owner/{store_id}/import/csv` | multipart `file`, `mapping` JSON | ImportResult |

Path params validated with `^[a-z0-9-]{3,40}$`; barcode `^[0-9]{8,14}$`; `q` ≤ 200 chars.

---

## `infra/seed/`

- `products.csv` — ~200 grocery rows with canonical headers.
- `make_sales.py` — writes `sales.csv`: 90 days × product, weekly seasonality, festival spike for sweets and oil in the last 14 days, decline for 10 dead-stock items. Pure Python, deterministic seed.
- `seed.py --store demo-grocery` — upserts store doc, products, locations, inventory, suppliers via the CSV connector; loads `sales.csv` into BigQuery `retail.sales` with a load job (BigQuery sandbox does not support streaming inserts); builds `retail.daily_product_sales`. Idempotent.

---

## Tests (`backend/tests/`)

Run against the Firestore emulator (`FIRESTORE_EMULATOR_HOST=localhost:8089`). Each test uses a fresh random `store_id`.

| File | Covers |
|---|---|
| `test_models.py` | defaults, `is_high_value` derivation |
| `test_inventory.py` | reserve succeeds / fails on shortage, release, commit floors at 0, concurrent reserve of last unit |
| `test_catalog.py` | by id, by barcode, keyword search ranking, demand signal types |
| `test_csv_connector.py` | parse with mapping, row errors, caps, upsert idempotent |
| `test_api_catalog.py` | endpoints and validation |
| `test_api_owner_import.py` | 401 without token, 403 wrong store, 200 import |

---

## Rulings made during implementation

- **Google Sheets connector deferred to phase 6** (owner connectors page), CSV covers the demo. Cost if wrong: one extra file later.
- **BigQuery streaming inserts are not available in the sandbox (no billing)**, so sales load by load job. Checkout (phase 3) will write orders to Firestore; a job copies them to BigQuery. Cost if wrong: dashboard lags by one job run.
- **170 products instead of ~200.** Enough for every demo path. Cost if wrong: none.
- **No composite indexes yet.** Phase 1 has no filtered queries. Added when a query needs one.
- **Inventory tolerates a missing `reserved` field** because imports never overwrite live reservations. Found by smoke test, covered by `test_imported_inventory_works_with_reserve`.
- **Substitutes in CSV are SKUs**, converted to product ids by the connector so the agent can resolve them directly.
- **Demo store name "Royal Stack Supermarket"**, taken from the repo name. Rename in `infra/seed/seed.py` if wanted.

## Review fixes (fresh-eyes review before merge)

Fixed, each with a regression test:
- Bearer-token uid read from `sub` claim (google-auth returns raw JWT claims; `uid` only exists in firebase-admin). Was a 500 on every real owner call.
- Re-import no longer wipes stored embeddings (`exclude={"embedding"}` on the merge write).
- `side` normalised and validated in `parse`, so a bad value is a row error, not a 500 mid-batch.
- Non-UTF-8 files, malformed CSV, and `Infinity` numbers are 400 or row errors, not 500. Mapping must be a JSON object; file is required.
- `reserve`/`release`/`commit` ignore `qty <= 0`.
- Search on a nonexistent store is 404 before any Gemini call or Firestore write.
- Transactions retry up to 10 times under contention.
- Seed generates `sales.csv` if missing.

Deferred minors (noted, not changed):
- Multipart body is spooled before the 5 MB check; Cloud Run's 32 MB request cap bounds it.
- `slug()` can collide distinct SKUs like `A-1` and `A_1`; acceptable for the demo catalog.
- Per-search Gemini embed and demand-signal write for valid stores is by design; rate limiting lands in phase 7.
