# LLD: product classification, floor blocks and floors, scan-to-cart, voice language

## Classification (`app/domain/classify.py`)
- Every product is born classified in `Product.from_row`: `storage` (ambient, chilled, frozen) and `use` (human, pet, household, personal_care) from name, category, subcategory and tags. Whole-word keyword rules with exclusion lists ("milk powder" is ambient, "butter cookies" is ambient, "cat eye" is not a pet); apparel categories are always ambient and human. Owners can still move a product by hand; `infra/scripts/reclassify.py` applies the rules to an existing store, adds Chiller and Freezer blocks when the store has cold products, moves cold products there and ambient ones back.
- Search (`catalog.search`): a query that names pets, household or personal care returns only that use; a query that does not never returns pet products. Alternatives (`tools._alternatives`) stay within the same use: substitutes, then the same subcategory, then the same category.

## Floor blocks and floors (`Aisle.kind`, `Aisle.floor`)
- A floor-map block is an aisle, a chiller, a freezer or a service counter, on floor 1 to 6. Names are unique across floors. The shopper map shows the floor of the target (or of the shopper), with a floor switcher and a stairs or lift marker on upper floors; chillers, freezers and counters have their own tints.
- `navigate_to` speaks the kind and the floor: "Chiller Dairy, bay 2, left side, first floor". Add-by-scan places chilled and frozen products in the first chiller or freezer block when the owner gave no aisle.
- The editor (Store settings) has floor tabs, "Add floor", and buttons for each block kind; "Line up aisles" arranges shelf aisles on the current floor only.

## Scan to cart (`components/Scanner.tsx`)
- Scan → identify by barcode → add one unit → the cart updates and the card shows the line quantity and the cart count. The same barcode within 2.5 seconds is one scan; after that it adds another unit (two packs scanned twice). Plus and minus on the card adjust the line. Unknown barcode, no stock and the self-checkout limit each get their own message. The cart is the server's cart; nothing is held locally.

## Voice language
- Fallback voice (`/agent/audio`): the transcription prompt requires the spoken language and script, never translation or transliteration; the shopper's chosen language, when not "auto", is passed as a hint. Live voice uses the model's own transcription, which keeps the spoken language, and the reply rule in the prompt.
- Live turn detection: low start and end sensitivity, 400 ms prefix and 1100 ms silence so a short pause or a passing noise does not cut a turn. On iOS the client resumes a suspended audio graph when the page is visible again instead of dropping the session; user transcript chunks already shown stay in the bubble.

## Tests
- `tests/test_classify.py` (rules, exclusions, apparel, query intent, blocks), `tests/test_agent_tools.py` (pet products only for pet queries; alternatives never cross use; directions with kind and floor), `tests/test_csv_connector.py` (classified at import), `tests/test_api_products.py` (cold add-by-scan placement), `tests/test_api_register.py` (floors and kinds), `tests/test_live.py` (turn detection settings).
