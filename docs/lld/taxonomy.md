# Taxonomy, storage and placement (18 Oct)

Field report: a search for "healthy food" showed a page of unrelated items (free-text search had no relevance floor and
matched the word "food"), and the floor plan put every non-grocery category into one aisle.

## One chain: product → category → subcategory → storage → department → block
- `domain/taxonomy.py` holds the departments: block id, label, and the categories or subcategories that live there.
  Default grocery layout (`FLOOR_MAP`): A1 Staples & Cooking, A2 Snacks, Beverages & Sweets, A3 Personal Care & Baby,
  A4 Household, Pooja & Pets, A5 Home, Kitchen & Hardware, A6 Stationery, Toys & Sports, Produce (fruit and
  vegetables), Fashion (clothing and footwear), Chiller, Freezer. Blocks carry a `label` the map and directions show.
- Storage (`domain/classify.py`) decides first: the subcategory wins (Frozen Foods is frozen; Dairy, Eggs, Fresh Meat
  and Seafood are chilled), non-food categories are always ambient, then the name words (milk, curd, paneer, batter,
  dough, tofu, chicken, fish, cold-pressed juice, tender coconut are chilled; frozen, ice cream, french fries, nuggets
  are frozen; powders, chocolates, tetra-pack plant milks and biscuits with dairy words stay ambient).
- Use: the Pet Products category is pet whatever the name says; the other rules stand.
- `taxonomy.place(floor_map, product)` gives the block: the chiller or freezer block for chilled or frozen products,
  else the department's block, with a bay, shelf and side spread deterministically by subcategory and name. The
  importer places every product that arrives without a shelf spot (file, sheet, API, database, MCP, add by hand or by
  scan), so inventory, product details, search, category pages, the assistant, the map and navigation all agree.

## Search that understands sections
- `catalog.section_for(store, query)`: the query's stemmed words against category and subcategory names ("healthy food"
  → Organic and Health Foods, "dals" → Pulses and Legumes). The online listing and the assistant's `list_category` use
  it, so a section query lists the section.
- Free-text search keeps a relevance floor: results scoring under half of the best hit (and under a small absolute
  floor) are dropped, so the tail of a page is not noise.

## Audit tool (`infra/scripts/audit_catalog.py --store <id> [--fix]`)
Reports, for every product, the storage, use and block the rules give against what the catalog file and the store
hold, plus names that contradict their category (a chair in groceries). `--fix` rewrites the catalog file's aisle,
bay, shelf and side, the store's product storage and use, every location, the floor plan with labels, and the upload
files. Deterministic and re-runnable.

## Tests
`tests/test_taxonomy.py`: the brief's table (milk, curd, cheese, fresh meat, frozen chicken, ice cream, frozen
vegetables, biscuits, rice, broom, shoes, nightwear), department placement, the pet category, section detection for
"healthy food" and "dals", and the search floor.
