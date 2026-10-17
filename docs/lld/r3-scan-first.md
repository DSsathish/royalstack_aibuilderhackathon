# LLD: R3 scan-first cart and owner add-by-scan

## Shopper, in store
- Cart items enter only by a barcode scan (`via=scan`) or a confirmed photo match (`via=vision`). The cart API rejects `via=chat` for in-store sessions with 409 `scan_required`.
- `add_to_cart` is removed from the in-store tool set; the prompt tells the assistant to guide to the shelf and say "scan it to add". Online keeps the tool.
- In the chat UI, product cards show "Where?" in store; "Add" appears only on cards produced by a photo turn (counts as vision) and in online mode.

## Owner, add product by scan
- `GET /owner/{id}/lookup/{barcode}`: Open Food Facts v2 product lookup (name, brand, category, image), 5 s timeout, cached in `barcode_lookups/{barcode}` for 30 days; `found=false` on miss.
- `POST /owner/{id}/products`: `{sku?, barcode, name, brand?, category?, price, mrp?, on_hand, aisle?}` → one row through the CSV connector's upsert, so validation and ids are identical to imports. Returns the product view. Owner only, audited.
- Inventory tab: "Add by scan" opens the camera; on a barcode, the form is prefilled from the lookup; owner enters price, stock, aisle; unknown barcode → manual form with the barcode kept.

## Tests
- `test_api_shop.py`: in-store `via=chat` → 409; `via=scan` ok; online `via=chat` ok.
- `test_agent_tools.py`: in-store tool set lacks `add_to_cart`; online has it.
- `test_api_products.py`: lookup with the HTTP call mocked (hit, miss, cached), product create and update, validation, owner-only.
- Live eval: the cart scenario moves to an online session.
