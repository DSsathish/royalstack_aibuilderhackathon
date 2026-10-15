# Architecture: key sequences

See `hld.md` for components and trust boundaries, `security.md` for controls, `lld/` for module designs.

## In-store visit

```mermaid
sequenceDiagram
  participant P as Phone (PWA)
  participant A as retail-api (Cloud Run)
  participant F as Firestore
  participant G as Gemini (Vertex AI)
  P->>A: POST /sessions/instore {store_id, signed token}
  A->>A: verify HMAC token
  A->>F: create session + cart id
  A-->>P: session
  P->>A: WS /agent/live (16 kHz PCM up)
  A->>G: Live session (system prompt, tool declarations)
  G-->>A: tool_call search_products("atta")
  A->>F: catalog + inventory + location
  A-->>P: action show_products
  A->>G: tool response
  G-->>A: tool_call navigate_to
  A-->>P: action highlight_map
  G-->>A: speech (24 kHz PCM)
  A-->>P: audio frames + transcript
```

## Scan, pay, exit

```mermaid
sequenceDiagram
  participant P as Phone
  participant A as retail-api
  participant F as Firestore
  participant K as Exit kiosk
  participant G as Gemini vision
  P->>A: POST /carts/{id}/items (barcode lookup done)
  A->>F: transaction: reserve stock
  P->>A: POST /checkout/intent -> amount from server cart
  P->>A: POST /checkout/confirm (signature)
  A->>F: commit reservations, order paid, receipt token (30 min)
  A-->>P: receipt + exit QR
  K->>A: POST /exit/{store}/verify (PIN, receipt token, bag photo)
  A->>F: transaction: claim order paid -> verified (single use)
  A->>A: layers: receipt, order, count, limit, high value, random audit
  A->>G: bag photo vs receipt lines (12 s cap, skipped on failure)
  A->>F: verification record (hash only, no image)
  A-->>K: verdict clear / spot_check / flag + reasons
```

## Nightly forecast and reorder

```mermaid
sequenceDiagram
  participant S as Cloud Scheduler
  participant A as retail-api
  participant B as BigQuery / BigQuery ML
  participant F as Firestore
  participant O as Owner dashboard
  participant G as Gemini Flash
  S->>A: POST /jobs/forecast?store_id (X-Job-Key)
  A->>F: paid orders since last sync
  A->>B: load into retail.sales; rebuild daily_product_sales
  A->>B: CREATE MODEL ARIMA_PLUS (per store); ML.FORECAST 14 days
  A->>F: forecasts/{product_id}
  O->>A: POST /owner/{store}/reorders/draft
  A->>F: inventory + forecasts -> candidates by supplier (manual point as floor)
  A->>G: one JSON call per supplier: reasons for urgent lines + summary
  A->>F: po_drafts (status draft)
  O->>A: approve / reject
  A->>F: status, supplier email text, audit entry
```
