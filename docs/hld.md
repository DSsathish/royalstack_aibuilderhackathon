# High-Level Design

One AI commerce agent and one inventory truth across the physical store, the online store, and the owner's back office, on top of the software the retailer already uses.

## 1. Components

```mermaid
flowchart LR
  subgraph Clients
    S[Shopper PWA<br/>in-store / online]
    W[Widget on retailer site]
    O[Owner dashboard]
    K[Exit kiosk]
    WA[WhatsApp via Twilio]
  end

  subgraph CloudRun[Cloud Run: retail-api]
    API[FastAPI routers]
    AG[ADK agent + tools]
    SVC[Services: catalog, inventory,<br/>cart, checkout, verification, forecast]
    CON[Connectors: CSV, Sheets, Shopify]
  end

  subgraph Data
    FS[(Firestore<br/>operational state)]
    BQ[(BigQuery<br/>sales history, forecasts)]
  end

  subgraph Google AI
    GF[Gemini Flash<br/>chat, vision, audio, embeddings]
    GP[Gemini Pro<br/>reorder reasoning]
  end

  JOBS[Cloud Scheduler → Cloud Run jobs<br/>sync, forecast, alerts]

  S & W & O & K --> API
  WA --> API
  API --> AG --> SVC
  API --> SVC
  SVC --> FS
  SVC --> BQ
  AG --> GF
  SVC --> GP
  CON --> FS
  JOBS --> CON
  JOBS --> SVC
```

| Component | Runs on | Owns |
|---|---|---|
| Shopper PWA | Firebase Hosting | QR session, chat, scan, cart, checkout, map |
| Widget | Firebase Hosting (`widget.js`) | Same chat on any retailer website |
| Owner dashboard | Firebase Hosting (`/owner`) | Inventory, reorders, signals, loss, connectors |
| Exit kiosk | Firebase Hosting (`/kiosk`) | Receipt scan, bag photo, verdict |
| retail-api | Cloud Run | All business logic, the only writer to Firestore and BigQuery |
| Jobs | Cloud Run jobs via Scheduler | Connector sync, forecast, alerts |
| Firestore | Google Cloud | Catalog, inventory, sessions, carts, orders, verifications, drafts, audit |
| BigQuery | Google Cloud | Sales history, daily aggregates, ARIMA_PLUS forecasts |
| Gemini | AI Studio key now, Vertex AI when billing is linked | All generative and multimodal calls |

## 2. Core data flows

**Shopper chat turn.** Client → `POST /agent/chat` → ADK agent picks tools → tools read Firestore → agent reply streamed as SSE `token` and `action` events → UI renders cards, map, cart from `action` events only.

**Scan and checkout.** Barcode → `GET /products/by-barcode` → `add_to_cart` reserves stock in a Firestore transaction → `POST /checkout/intent` → sandbox payment → `POST /checkout/confirm` verifies signature, commits reservations, writes order, appends sale to BigQuery, returns signed receipt token.

**Exit verification.** Kiosk → `POST /exit/verify` with receipt token and optional bag photo → deterministic layers → Gemini vision confidence → verdict stored, image discarded.

**Owner reorder.** Scheduled job trains ARIMA_PLUS in BigQuery → forecasts written to Firestore → low-stock items grouped by supplier → Gemini Pro writes rationale → draft waits in approval inbox → owner approves → supplier email, audit log.

**Connector sync.** Scheduler → `POST /jobs/sync` → connector pulls rows → mapped with the store's column mapping → upsert products and inventory.

## 3. Trust boundaries and security

```
Internet ──► Firebase Hosting (static) ──► retail-api on Cloud Run ──► Firestore / BigQuery / Gemini
                                            ▲
                       Cloud Scheduler ─────┘ (OIDC token, jobs only)
```

| Boundary | Control |
|---|---|
| Client → API | HTTPS only. CORS restricted to the hosting origin and localhost. |
| Shopper identity | Firebase Auth anonymous session. ID token sent as `Authorization: Bearer`. Session documents keyed by a server-generated id; a client can only act on its own session. |
| In-store entry | Entrance QR carries an HMAC token signed with `QR_SESSION_SIGNING_KEY`. Sessions expire after 4 hours. Self-checkout only in `instore` mode. |
| Owner endpoints | Firebase ID token verified server-side; `users/{uid}.stores` must contain the `store_id`. No owner data is readable from the client SDK. |
| Jobs endpoints | Accept only Cloud Scheduler OIDC tokens for the runtime service account. |
| Firestore | Security rules deny all client reads and writes except the shopper's own session, cart, and orders. Everything else goes through the API. |
| Secrets | Secret Manager mounted as env vars on Cloud Run. Locally in `.env`, git-ignored. Never in code or logs. |
| Payments | Razorpay test mode only. Webhook and checkout signatures verified with HMAC before any order is written. |
| Receipts | Receipt token is a signed JWT, 30 minute expiry, single use (marked used inside the verdict transaction). |
| WhatsApp | Twilio request signature verified. |
| Uploads | Images limited to 5 MB, content type checked, bag photos processed in memory and discarded. Product photos stored only if the shopper confirms. |
| Input validation | Every request body is a pydantic model. `store_id` and ids match `^[a-z0-9-]{3,40}$`. CSV imports capped at 5 MB and 10 000 rows, headers whitelisted. |
| Agent | Tools are gated by mode. Tool results are the only source of truth for stock, price, location. Max 6 tool calls per turn. Rate limit per session on `/agent/chat`. |
| Audit | Every agent write, approval, verification, and import appends to `stores/{store_id}/audit`. |
| Privacy | No bag images stored. Verification keeps verdict, confidence, and image hash. Retention job deletes verifications older than 90 days. |
| Supply chain | Python and npm dependencies pinned. CI runs tests and build on every push. |

## 4. Multi-tenancy

Every document carries or is nested under `store_id`. The API resolves `store_id` from the session (shopper) or from the owner's membership (owner), never from a free query parameter on write paths. A second store can be onboarded by CSV with its own column mapping; nothing else changes.

## 5. Environments

| | Dev (laptop) | Demo (Cloud) |
|---|---|---|
| API | uvicorn on :8080 | Cloud Run `retail-api`, min 1 instance during judging |
| Frontend | next dev on :3000 | Firebase Hosting |
| Firestore | emulator for tests, real DB for manual runs | real DB |
| Gemini | AI Studio key | AI Studio key, Vertex AI once billing is linked |
| Secrets | `.env` | Secret Manager |

## 6. Non-goals for the hackathon

Indoor positioning or AR navigation, live payments, Shopify write-back, 3D avatar (stretch), email digests, multi-region.
