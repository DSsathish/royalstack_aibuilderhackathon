# Phase 1: Data Foundation

Goal: one canonical commerce schema, a seeded grocery demo store, and connectors that load it from CSV or Google Sheets. Every agent tool and every UI reads from this layer.
Owner: backend. Estimated time: 5 to 6 hours. Runs in parallel with phase 2.

## 1.1 Canonical schema

Define as pydantic models in `backend/app/domain/models.py`. All documents carry `store_id` for multi-tenancy.

| Entity | Key fields |
|---|---|
| Store | `store_id`, `name`, `type` (grocery), `currency`, `languages`, `self_checkout_item_limit` (default 15), `high_value_threshold` (default 500), `floor_map` (list of aisles with x,y,w,h) |
| Product | `product_id`, `store_id`, `sku`, `barcode` (EAN-13), `name`, `brand`, `category`, `subcategory`, `description`, `price`, `mrp`, `unit` (pc/kg/l), `image_url`, `tags[]`, `substitutes[]` (product_ids), `is_high_value` |
| Location | `product_id`, `store_id`, `aisle`, `bay`, `shelf`, `side` (left/right), `x`, `y` |
| Inventory | `product_id`, `store_id`, `channel` (store/online/shared), `on_hand`, `reserved`, `reorder_point`, `reorder_qty`, `lead_time_days`, `supplier_id`, `updated_at` |
| Supplier | `supplier_id`, `name`, `email`, `whatsapp`, `lead_time_days` |
| Session | `session_id`, `store_id`, `mode` (instore/online/owner), `user_id` (nullable), `created_at`, `expires_at`, `aisle_hint` |
| Cart | `cart_id`, `session_id`, `items[] {product_id, qty, unit_price, scanned_via (barcode/vision/chat)}`, `subtotal`, `discount`, `total`, `status` |
| Order | `order_id`, `store_id`, `session_id`, `channel`, `items[]`, `total`, `payment_ref`, `status` (paid/verified/flagged/refunded), `receipt_token`, `created_at` |
| Verification | `verification_id`, `order_id`, `layers {receipt_ok, count_ok, limit_ok, high_value_flag, vision_confidence, random_audit}`, `verdict` (clear/flag), `image_hash`, `reviewed_by`, `created_at` |
| DemandSignal | `signal_id`, `store_id`, `query_text`, `matched_product_id` (nullable), `type` (not_carried/out_of_stock/found), `session_mode`, `created_at` |
| PurchaseOrderDraft | `po_id`, `store_id`, `supplier_id`, `lines[] {product_id, qty, reason}`, `forecast_ref`, `status` (draft/approved/rejected/sent), `created_by` (agent), `approved_by` |
| AuditLog | `log_id`, `store_id`, `actor` (agent/user/system), `action`, `payload`, `created_at` |

## 1.2 Firestore layout

Top-level collections, keyed by `store_id` in document IDs or filtered by field:

```
stores/{store_id}
stores/{store_id}/products/{product_id}
stores/{store_id}/locations/{product_id}
stores/{store_id}/inventory/{product_id}
stores/{store_id}/suppliers/{supplier_id}
stores/{store_id}/po_drafts/{po_id}
stores/{store_id}/demand_signals/{signal_id}
stores/{store_id}/audit/{log_id}
sessions/{session_id}
carts/{cart_id}
orders/{order_id}
verifications/{verification_id}
```

Composite indexes needed (create via `firestore.indexes.json`):
- `products`: `category ASC, name ASC`
- `inventory`: `on_hand ASC`
- `orders`: `store_id ASC, created_at DESC`
- `demand_signals`: `store_id ASC, type ASC, created_at DESC`

Stock updates must be transactional: `db.transaction()` reading `inventory/{product_id}`, checking `on_hand - reserved >= qty`, then decrementing. Put this in `services/inventory.py` as `reserve()`, `commit()`, `release()`.

## 1.3 BigQuery tables

Dataset `retail`:

```sql
CREATE TABLE retail.sales (
  store_id STRING, order_id STRING, product_id STRING, channel STRING,
  qty INT64, unit_price NUMERIC, sold_at TIMESTAMP
) PARTITION BY DATE(sold_at);

CREATE TABLE retail.daily_product_sales (
  store_id STRING, product_id STRING, day DATE, qty INT64
);

CREATE TABLE retail.demand_signals (
  store_id STRING, product_id STRING, type STRING, query_text STRING, created_at TIMESTAMP
);
```

A Cloud Run job (phase 6) streams `orders` into `retail.sales`. For the hackathon, also write each paid order directly from the checkout service using the BigQuery streaming insert, so the dashboard reflects the demo in real time.

## 1.4 Product search

Agent needs semantic search ("something for a headache", "breakfast cereal for kids").

Option A (simplest, recommended for 4 days): embed `name + brand + category + description + tags` with the Gemini embedding model at seed time, store the vector in the Firestore product document, and do a brute-force cosine search in memory over the store's products (200 to 2000 products is fine). Cache the product list per store in the API process.

Option B: Firestore vector search (`find_nearest`) if time allows.

Keyword fallback: lowercase token match on `name`, `brand`, `tags` for exact brand queries.

`services/catalog.py` exposes `search(store_id, query, k=8) -> list[ProductHit]` combining both and returning stock and location joined in.

## 1.5 Seed data

Build `infra/seed/products.csv` with about 200 grocery SKUs across 12 categories (staples, snacks, beverages, dairy, personal care, household, baby, fruits and vegetables, bakery, frozen, pharmacy OTC, pet). Columns match the Product and Location models. Include:

- Real-looking EAN-13 barcodes (generate with a valid check digit).
- 10 high-value items (price above the store threshold), for the exit verification demo.
- 5 items with `on_hand = 0`, each with substitutes, for the out-of-stock demo.
- 3 Tamil and Hindi name aliases in `tags` for multilingual search.
- Product images: use open license placeholder images or generate simple labeled tiles. Store under `frontend/public/products/`.

Floor map: 6 aisles, 4 bays each, 2 sides, mapped to a 1000x600 SVG coordinate space.

Sales history: `infra/seed/generate_sales.py` creates 90 days of daily sales per product with weekly seasonality, a festival spike in the last 2 weeks for sweets and oil, and a declining trend for 10 dead-stock items. Writes `sales.csv` and loads into `retail.sales` and `retail.daily_product_sales`.

Seed script `infra/seed/seed.py`:

```bash
python infra/seed/seed.py --store demo-grocery --project $PROJECT_ID --csv infra/seed/products.csv --sales infra/seed/sales.csv
```

Idempotent: upserts by `product_id`.

## 1.6 Connectors

Interface in `connectors/base.py`:

```python
class Connector(Protocol):
    def pull_products(self, store_id) -> list[Product]: ...
    def pull_inventory(self, store_id) -> list[Inventory]: ...
    def push_inventory(self, store_id, updates: list[Inventory]) -> None: ...
```

- `connectors/csv_connector.py`: upload endpoint `POST /owner/import/csv` accepts a file, validates headers, maps to canonical, upserts. Returns row-level errors.
- `connectors/sheets_connector.py`: owner pastes a Google Sheet URL shared as "anyone with link can view". Read via the Sheets API with the runtime service account, same mapping as CSV. Scheduled re-sync every 15 minutes via Cloud Scheduler hitting `POST /jobs/sync`.
- `connectors/shopify_connector.py` (stretch): Admin GraphQL API, `products` and `inventoryLevels`, write back with `inventoryAdjustQuantities`. Needs a dev store and a custom app token in Secret Manager.

Column mapping is configurable per store in `stores/{store_id}.connector_config`, so a different retailer's sheet can be mapped without code changes. This is the "adaptive" claim in the deck.

## 1.7 API endpoints delivered in this phase

| Method | Path | Purpose |
|---|---|---|
| GET | `/stores/{store_id}` | Store config and floor map |
| GET | `/stores/{store_id}/products/{product_id}` | Product + stock + location |
| GET | `/stores/{store_id}/products/by-barcode/{barcode}` | Scan lookup |
| GET | `/stores/{store_id}/search?q=` | Semantic + keyword search |
| POST | `/owner/import/csv` | CSV connector |
| POST | `/owner/import/sheet` | Sheets connector |
| POST | `/jobs/sync` | Scheduled re-sync (Scheduler only, OIDC protected) |

## Acceptance criteria

- [ ] Seed loads 200 products, locations, inventory, 1 store, 3 suppliers, 90 days of sales
- [ ] `search?q=headache tablet` returns the OTC product first
- [ ] `search?q=பால்` (Tamil for milk) returns milk
- [ ] Barcode lookup returns product with stock and aisle
- [ ] CSV import of a second small store (20 rows) works with a different column mapping
- [ ] Inventory decrement is transactional; two concurrent reserves of the last unit, one fails
- [ ] Unit tests for mapping, reserve/commit/release, search ranking

## Risks

- Embedding 200 products takes seconds; embedding on every search would be slow. Embed only the query at runtime.
- Firestore reads cost and latency: cache product list per store in process memory with a 60 s TTL.
