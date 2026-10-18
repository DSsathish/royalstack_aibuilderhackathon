# Product details and editing in the Inventory tab (18 Oct)

Field report: the Inventory tab listed stock and reorder numbers, but the owner could not see or change the rest of a
product (barcode, price, MRP, pack, place on the floor, status, tags).

## API (`api/products.py`)
- `GET /owner/{store}/products/{id}`: the product view (every catalog field, availability, shelf spot) and its stock
  record. Staff may read.
- `PATCH /owner/{store}/products/{id}`: `ProductPatch`, every editable field across the three records, only the fields
  sent change. Product fields go to the product document (price also refreshes the high-value flag against the store's
  threshold; MRP below price is refused). Stock fields go to the inventory record. Place fields go to the location
  record (the aisle must be on the floor map; bay, shelf and side default to the current spot). The SKU is not editable:
  it forms the product id that carts, orders and forecasts point at. Owner only; audited as `product_edited` with the
  field names. The catalog cache is bumped so the shopper assistant sees the change within seconds. The semantic
  embedding is kept as it is (the text rarely changes enough to matter; a re-import refreshes it).
- `insights.inventory` rows now carry sku, barcode, brand, mrp, unit, pack size, bay, shelf and side, so the table can
  show them without a second call.

## UI (`app/owner/page.tsx`)
- The table gains a Price column and shows the barcode and pack under the name. The name opens the product drawer.
- `ProductDrawer`: one modal, five groups (Identity, Pricing, Stock, Place, Details). Fields validate like the add form
  (numbers, barcode of 8 to 14 digits, bay 1 to 12, shelf 1 to 8, MRP at or above price). Save sends only what changed,
  then the list reloads.

## Tests
`tests/test_api_products.py`: an owner edits fields across all three records and reads them back on the detail and the
inventory list; staff can read but not edit; a bad barcode, an MRP below the price and an aisle off the map are refused.
