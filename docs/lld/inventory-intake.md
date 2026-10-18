# Inventory intake (18 Oct)

Three ways to put inventory in from the Inventory tab, all on one field table.

## Single source of truth: `app/connectors/schema.py`
The field table is built from the importer's own contract (`csv_connector.REQUIRED` + `OPTIONAL`, the `Row` model's
types, the normalizer's field meanings) plus an example per field. Everything else reads it:
- `GET /owner/{id}/inventory/schema` gives the frontend the fields (name, required, kind, description, example) and
  the Google Sheets template link.
- `GET /owner/{id}/inventory/template.xlsx` builds the Excel template with openpyxl at request time: an "Inventory"
  sheet whose header row is the exact column names (required ones highlighted, each header with a note), frozen and
  sized, a dropdown on `status` and `side`, and a "Guide" sheet listing every field with its type, meaning and example.
  No example row on the data sheet, so a filled template never imports a sample product by accident.
- The Google Sheet is the same template uploaded to Drive; its link is configuration (`INVENTORY_SHEET_TEMPLATE_URL`).
  The button is shown only when the link is set and opens the sheet's copy page so each owner gets their own copy.
- The manual form takes its labels, required marks, placeholders and number rules from the same table.

## Upload: `POST /owner/{id}/inventory/upload` (all three routes live in `api/owner_import.py`, beside the mapped CSV import)
`.xlsx` or `.csv`, read by the connector readers (10 MB, 20,000 rows). Headers are matched to the field names exactly
(case, spaces and underscores forgiven). The check runs before anything is written and answers with:
missing required columns, unknown columns (ignored), row errors with line numbers and the reason (the importer's own
type checks: price must be a number, on_hand a whole number, status one of the allowed values), duplicate SKUs inside
the file, keyed by the same slug that forms the product id (the first row wins, later ones are reported), and a preview of adds, updates and restocks against the catalog.
`apply=true` writes. By default rows whose SKU already exists are skipped and counted, so a re-upload cannot overwrite
by accident; `allow_updates=true` lets them update. Every upload is audited with counts.

## Manual add: the existing `POST /owner/{id}/products`
The form posts one product. The endpoint now accepts a product without a barcode when a SKU is given (one of the two
is required), and the extra fields the form offers (subcategory, unit, reorder point and quantity, pack size). Cold
products still default to the chiller or freezer block.

## UI (Inventory tab)
Toolbar: Download template, Google Sheets template (when configured), Upload inventory, Add inventory, Add by scan.
Upload opens a panel: pick the file, "Check file" shows the column check, the first errors with line numbers, duplicate
SKUs and the preview counts; "Import" writes, with a checkbox to allow updating existing products. Add inventory opens a
modal with the fields from the schema, required fields marked, inline validation, and the list refreshes on save.

## Tests
`tests/test_inventory_intake.py`: the schema lists every importer field with required flags; the template round-trips
(generate, fill two rows with openpyxl, upload, preview, apply); header check reports missing and unknown columns;
type errors and duplicate SKUs carry line numbers; skip-existing versus allow-updates; owner-only access; the manual
endpoint accepts a SKU without a barcode and rejects neither-nor.

## Google Sheets configuration (one-time, by the owner of the Google account that will host the template)
1. Download the template from the Inventory tab (or `GET /owner/{id}/inventory/template.xlsx`).
2. In Google Drive, upload it and open it with Google Sheets (File > Save as Google Sheets). Keep the "Inventory" and "Guide" sheets.
3. Share > General access: "Anyone with the link", Viewer.
4. Take the sheet's id from its address and set `INVENTORY_SHEET_TEMPLATE_URL=https://docs.google.com/spreadsheets/d/<id>/copy`.
   The `/copy` address makes Google offer each owner their own copy; the original stays read-only.
5. Redeploy the API with that variable (Cloud Run: `--update-env-vars INVENTORY_SHEET_TEMPLATE_URL=...`). The button appears on the next load.
Owners fill their copy, File > Download > .xlsx (or .csv), and upload it from the Inventory tab.
