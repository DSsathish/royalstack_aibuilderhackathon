# Connector agent (18 Oct)

Problem: a shop that already runs billing software, keeps stock in a spreadsheet or has its own database should not
retype anything. The owner asked for one agent that takes whatever the shop has, understands it, and keeps the
inventory in step with it. Decisions taken with the owner: four kinds of source (files exported from billing software,
Google Sheets, billing/POS APIs, a read-only database), and preview-then-confirm before anything is written.

## Flow
1. **Inspect**: the owner gives a source (uploads a file, pastes a Sheet link, an API URL with an optional auth header,
   or a database connection string and table). The agent reads up to 20,000 rows, extracts the columns and five sample
   rows, and asks the normalizer (Gemini, heuristic fallback, `app/connectors/normalizer.py`) for a mapping from the
   source's columns to the catalog contract (`sku, name, price, on_hand` plus optional `barcode, brand, category, ...`).
2. **Preview**: the mapped rows are validated by the same row checks as the CSV import and compared with the catalog:
   how many products would be added, updated (name or price change), restocked (on-hand change), left unchanged, and
   which rows fail and why. Nothing is written.
3. **Confirm and apply**: the owner edits the mapping if needed and confirms. The rows are upserted through the existing
   importer (`csv_connector.upsert`, catalog version bumped), and the run is audited.
4. **Keep in step**: a Sheet, API or database source can be saved as a connector with the confirmed mapping and an
   interval. The 15-minute sync job (`/jobs/sync`) runs due connectors, applies with the saved mapping, records the
   result on the connector and in the audit trail. A file source is one-off by nature.

## Module `app/services/connectors.py`
- `Connector` (stored at `stores/{id}/connectors/{cid}`): kind, label, url, table, mapping, every_min, enabled,
  last_run_at, last_result, created_by. Secrets never go to Firestore: the API auth header and the database connection
  string live in Secret Manager as `conn-{store}-{cid}` (auth) and `conn-{store}-{cid}-dsn`.
- Readers (`read_*`), each returning `(columns, records)`: file (CSV with BOM tolerance, XLSX first sheet via openpyxl,
  JSON array or `{items|products|rows: [...]}`, PDF through Gemini table extraction); sheet (any Google Sheets link
  turned into its CSV export URL; the sheet must be shared "anyone with the link"); api (GET, JSON or CSV body, optional
  `Authorization` header); db (SQLAlchemy, `postgresql://` or `mysql://` only, `SELECT * FROM <table> LIMIT 20000`
  inside a read-only transaction, table names validated against the database's own list).
- `inspect(...)`, `preview(store_id, columns, records, mapping)`, `apply(store_id, records, mapping, actor, label)`,
  `save/list_/remove`, `run(store_id, connector)`, `run_due()` for the scheduler.

## Guardrails
- URLs must be https and resolve to public addresses (no loopback, private, link-local or metadata ranges); redirects are
  followed by hand and re-checked at every hop. Database hosts get the same address check.
- Database access is read-only: only `SELECT` on a table the database itself lists, with a row cap, inside a read-only
  transaction; the connection string is validated for scheme and stored only in Secret Manager.
- Files: 10 MB and 20,000 rows at most, by content type and extension (`.csv .xlsx .json .pdf`); PDFs go to Gemini only
  for table extraction, with the same row cap.
- Mapping values are checked against the canonical field list and the source's real columns before any row is read.
- Every inspect, apply and scheduled run is audited with counts, never with row contents.
- The owner agent's chat tools can inspect a Sheet or API link and report the preview, but apply only with
  `confirm=True`, like every other acting owner tool; files and database credentials go through the Connectors page.

## API (`app/api/owner_connectors.py`, owner-only)
`POST /owner/{id}/connectors/inspect` (multipart: kind, file | url, auth, dsn, table, optional mapping) ->
`{columns, samples, mapping, proposal_notes, preview, row_count}`.
`POST /owner/{id}/connectors/apply` (same inputs + mapping, label, save, every_min) -> `{result, connector?}`.
`POST /owner/{id}/connectors/discover` (dsn) -> `{tables}`. `GET /owner/{id}/connectors`, `POST .../{cid}/run`,
`DELETE .../{cid}`.

## UI
Owner > Connectors: pick the source kind, provide it, "Analyse". The agent's mapping shows as editable selects over the
source's columns, with the preview counts and the first failing rows. "Apply" writes; "Keep in step every N minutes"
saves the connector. Saved connectors list their last run and offer "Run now" and "Remove". The owner assistant
(text or voice) can do the Sheet and API cases by conversation: "connect my stock sheet <link>".

## Tests
`tests/test_connectors.py`: readers (CSV, XLSX, JSON, Sheet URL rewriting, API JSON, SQLite through the db reader with
the scheme guard), preview counts against a seeded catalog, apply + audit, saved connector run and `run_due`, URL and
address guards, row and size caps. The normalizer's model call is mocked; the heuristic path is exercised for real.

## Not done
No per-system adapters yet (Zoho, Tally, Shopify): any system that exports a file, publishes a sheet, or serves a
JSON/CSV endpoint works through the generic readers; a named adapter is a thin reader on top of this flow. PDFs with
multiple tables keep only the rows Gemini extracts.
