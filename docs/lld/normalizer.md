# LLD: Universal normalizer agent and real dataset import

Any store's product file, in any column layout, becomes our canonical schema. The model reads only the header and a few sample rows and proposes a mapping; the owner confirms once; the existing connector applies the mapping deterministically to the bulk data. The model never touches the bulk rows, so imports stay fast, cheap, and auditable.

---

## `app/connectors/normalizer.py`

**Responsibility.** Propose a column mapping and explain it.

**Function.** `propose(header: list[str], samples: list[dict]) -> Proposal`

- `Proposal(mapping: dict[canonical_field, source_header], notes: list[str], questions: list[str], confidence: float, source: "model" | "heuristic")`
- Canonical fields are `csv_connector.REQUIRED + OPTIONAL`.
- Model path: Gemini Flash, JSON mode (no strict schema, see phase 6 findings), prompt lists the canonical fields with one-line meanings, the header, and up to 5 sample rows. The model returns `mapping`, `notes` (for example "Rate is in rupees including GST", "Qty on hand carries a 'pcs' suffix"), and `questions` for ambiguous columns (for example "Is 'MRP' the selling price or the printed price?").
- Validation: every mapped header must exist in the file; every canonical key must be known; required fields missing from the mapping become questions. Invalid entries are dropped, never guessed.
- Heuristic fallback when the model is unavailable or returns garbage: exact and synonym header matching (`sku`: item code, code, product id, article; `name`: item name, description, product; `price`: rate, selling price, mrp; `on_hand`: qty, quantity, stock, on hand; `barcode`: ean, upc, bar code; `category`: dept, department, group; `aisle`: location, shelf).

**Number cleaning (deterministic, in `csv_connector._num`).** Strip currency symbols, thousands separators, and unit suffixes before parsing: `"₹ 1,250.00"` → 1250, `"12 pcs"` → 12, `"3.5 kg"` → 3.5. Negative and non-finite values still reject the row. This is what makes "transformation notes" unnecessary as code: the connector already tolerates the common messiness.

## `app/api/owner_import.py`

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/owner/{store_id}/import/propose` | multipart `file` (same caps as import) | `{proposal, header, samples}` |

The owner confirms or edits the mapping in the Connectors tab, then calls the existing `POST /owner/{store_id}/import/csv` with it. Audit entry `import_proposed` records the proposal source and confidence.

## Frontend Connectors tab

Choose file → "Analyse with AI" → the proposed mapping fills the mapping fields, with the model's notes and questions shown above them and the confidence badge → owner edits if needed → "Import". Manual mapping still works without the analysis step.

## Real dataset import (`infra/seed/import_dataset.py`)

```
python infra/seed/import_dataset.py --file <csv> --store kaggle-grocery [--sales <csv>] [--owner-email ...]
```

- Runs the normalizer on the file, prints the proposal, applies it with the connector into a new store.
- Synthesises what public datasets lack: EAN-13 barcodes from a hash of the SKU, aisles by category round-robin over the demo floor map, one supplier per category, reorder defaults from stock. The import leaves them blank only when no category exists.
- Optional sales file: `product_id, day, qty` or `date, product, quantity` (also normalised) loaded into BigQuery for the forecast job; without it the job falls back to flat forecasts, and the dashboard still works.
- Kaggle download: `kaggle datasets download -d <slug> -p infra/seed/data` needs `~/.kaggle/kaggle.json`; a manual download dropped into `infra/seed/data/` works the same.

## Tests

- `test_normalizer.py`: model mocked → proposal validated (bad headers dropped, missing required → question); heuristic fallback maps a messy header; `_num` cleaning cases.
- `test_api_owner_import.py`: propose endpoint 401/200 with the model mocked, audit entry.
- Live: `test_normalizer_live.py` under `LIVE_GEMINI=1` with a messy real-world header.

## Rulings

- The model maps columns; the code transforms values. No per-row model calls, ever.
- Unmapped or ambiguous columns become questions, never guesses.
- The dataset store is separate (`kaggle-grocery`) so the curated demo store stays intact for the video.
