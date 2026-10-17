# Royal Stack: one AI commerce agent, one inventory truth

AI Builder Cup 2026 (Google Cloud JAPAC), theme: Retail & Commerce. A store assistant that serves shoppers in the physical store and online, runs the owner's inventory, and sits on top of the software the retailer already has.

| | |
|---|---|
| Live app (shopper) | https://royastacxk-aibuildercup.web.app |
| Owner dashboard | https://royastacxk-aibuildercup.web.app/owner/ |
| Exit kiosk | https://royastacxk-aibuildercup.web.app/kiosk/ (store `demo-grocery`, PIN `1234`) |
| API | https://retail-api-881917398995.asia-south1.run.app (OpenAPI at `/docs`) |

Scan the entrance QR (see `docs/plan/00-overview.md` or the owner dashboard's Connectors tab) to start an in-store session on a phone.

## What it does

**Shopper, in the store.** Scan the entrance QR, no install. Talk to the assistant by voice (real-time speech-to-speech on Gemini Live, interruptible) or text, in English, Tamil or Hindi. Ask where things are and the floor map lights up. Scan barcodes or photograph a product, see a running receipt, pay in sandbox, get an exit QR.

**Exit.** A kiosk scans the receipt, takes a bag photo, and runs seven verification layers. Deterministic rules decide; Gemini vision only adjusts confidence and never blocks an exit. Photos are never stored.

**Shopper, online.** The same app and the same agent in online mode, sharing the same stock.

**Shopper identity, optional.** Phone OTP sign-in (Firebase) unlocks a profile the assistant uses (name, language, dietary limits, usual items learned from receipts, substitution preference), receipt history with "buy again", offers for their segment, reward points (one per ₹100, redeemed at checkout after a fresh code, twelve-month expiry, append-only ledger), and self-service export and delete. Guests lose nothing.

**Owner.** Google sign-in, self-service registration, staff roles. Live sales, inventory with BigQuery ML forecasts and days of cover, reorder drafts with a Gemini-written rationale waiting for approval, "asked but not carried" signals captured from conversations, customers with segments (new, regular, VIP, at risk), offers that apply themselves (product, category, bill threshold, segment-targeted, best wins), points adjustments with audit, exit-loss view with controls, add products by scanning a barcode (Open Food Facts lookup), CSV import with AI column mapping, and the owner assistant by text or live voice.

**Sync with the shop's own system.** Signed webhooks in (`/sync/{store}/inventory`, `/sync/{store}/products`, idempotent by event id), a bearer-protected pull, signed sale events out with retries, and a published CSV feed pulled every fifteen minutes. A catalog version counter makes every API instance reload within two seconds. See `infra/scripts/sync_example.py`.

## Google Cloud services

Cloud Run (API and websocket bridge), Firebase Hosting (static PWA), Firebase Auth (Google for owners and staff, phone OTP for shoppers), Firestore (operational data), BigQuery and BigQuery ML `ARIMA_PLUS` (sales history and forecasts), Vertex AI Gemini (`gemini-3.5-flash`, `gemini-live-2.5-flash`, `gemini-embedding-001`), Google ADK (agent runtime), Cloud Scheduler (nightly forecasts and customer jobs, sync every 15 minutes), Secret Manager (signing keys, per-store payment and sync secrets), Cloud Build, Artifact Registry.

## Codebase

```
backend/                 Python 3.12, FastAPI, Google ADK, google-genai
  app/main.py            app, routers, startup warm-up
  app/config.py          settings from env; refuses the default signing key outside dev/test
  app/domain/models.py   all Firestore models
  app/services/          db paths, inventory (transactions), catalog (keyword + embeddings, version-aware cache),
                         cart (pricing with offers and points), checkout, qr (signed tokens), sessions,
                         verification (7 layers), vision, forecast, reorder, insights, auth, gemini,
                         customers, segments, offers, points (ledger), sync (webhooks, outbox, feed), secrets,
                         barcode (Open Food Facts), conversation (memory)
  app/agent/             tools.py (plain functions, mode-gated), prompts.py, agent.py (ADK, SSE),
                         live.py (Gemini Live websocket bridge)
  app/api/               catalog, shop, agent (chat, audio, live), exit (kiosk), owner, owner_import, register,
                         products, me (shopper), sync (inbound), owner_sync
  app/jobs/              forecast.py (sales -> ARIMA_PLUS -> forecasts), customers.py (segments, points expiry)
  app/connectors/        csv_connector (column mapping, caps, idempotent upsert), normalizer (mapping agent)
  tests/                 271 unit tests (Firestore emulator) + live tests gated by LIVE_GEMINI=1
frontend/                Next.js 16 static export, TypeScript, Tailwind
  app/enter, shop, checkout, receipt, exit, kiosk, owner, me
  components/            Chat (text, voice loop, live voice), VoiceOrb, Scanner, BarcodeScan, PhoneSignIn, Cart,
                         StoreMap, TotalBar, RevenueChart
  lib/                   api.ts, sse.ts, voice.ts, live.ts, store.ts, firebase.ts, authed.ts, owner.ts, me.ts
  public/pcm-worklet.js  microphone -> 16 kHz PCM for live voice
infra/seed/              demo store generator (170 products, 90 days of sales), seed script
infra/scripts/           reset_demo.py, sync_example.py (how a billing system signs and pushes stock)
docs/                    hld.md, security.md, demo-script.md, submission-checklist.md, lld/ (one per module group), plan/
```

Design documents: `docs/hld.md` (components, flows, trust boundaries), `docs/security.md` (every control mapped to code and tests, plus known gaps), `docs/lld/` (low-level design per phase, written before the code, with the rulings made during implementation).

## Run locally

Prerequisites: Python 3.12+, Node 20+, Java (for the Firestore emulator), `gcloud` and `firebase` CLIs, a Google Cloud project with Vertex AI enabled and application-default credentials (`gcloud auth application-default login`).

```bash
# backend
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # set GOOGLE_CLOUD_PROJECT; Vertex AI is the default
.venv/bin/uvicorn app.main:app --port 8080

# frontend
cd frontend && npm ci && npm run dev    # NEXT_PUBLIC_API_URL defaults to http://localhost:8080

# demo data (Firestore + BigQuery) and forecasts
cd backend && .venv/bin/python ../infra/seed/seed.py --store demo-grocery --embed --owner-email you@example.com
.venv/bin/python -m app.jobs.forecast --store demo-grocery
```

Entrance link for local testing: `http://localhost:3000/enter/?store=demo-grocery&t=<token>` where the token comes from `python -c "from app.services import qr; print(qr.entrance_token('demo-grocery'))"` run in `backend/`.

## Tests

```bash
backend/scripts/test.sh                      # unit tests under the Firestore emulator
LIVE_GEMINI=1 backend/scripts/test.sh tests/test_agent_live.py tests/test_live_live.py -s   # real model calls
cd frontend && npx vitest run && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs all of the above except the live tests on every push.

## Deploy

```bash
# API (Cloud Run, asia-south1); secrets QR_SESSION_SIGNING_KEY and JOB_KEY live in Secret Manager
gcloud run deploy retail-api --source backend --region asia-south1 \
  --service-account retail-api@<project>.iam.gserviceaccount.com --allow-unauthenticated --timeout 3600 \
  --set-env-vars ENV=demo,GOOGLE_CLOUD_PROJECT=<project>,GEMINI_LOCATION=global,APP_BASE_URL=https://<site>.web.app \
  --set-secrets QR_SESSION_SIGNING_KEY=QR_SESSION_SIGNING_KEY:latest,JOB_KEY=JOB_KEY:latest

# frontend (Firebase Hosting)
cd frontend && npm run build && cd .. && firebase deploy --only hosting,firestore:rules,firestore:indexes
```

`ENV=demo` keeps sandbox payments enabled while refusing the development signing key. Use `ENV=prod` with Razorpay keys for real payments.

Scheduled jobs (Cloud Scheduler, all authenticated with `X-Job-Key`): `POST /jobs/forecast` nightly 20:30 IST for every store (BigQuery ML retrain), `POST /jobs/customers` nightly 21:15 IST (segments, points expiry, stale point holds), `POST /jobs/sync` every 15 minutes (CSV feeds and outbox retries).

## Environment variables

| Variable | Purpose |
|---|---|
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | project and region for Firestore and BigQuery |
| `GOOGLE_GENAI_USE_VERTEXAI`, `GEMINI_LOCATION` | Vertex AI on the `global` endpoint (default); set `false` plus `GEMINI_API_KEY` for AI Studio |
| `GEMINI_FLASH_MODEL`, `GEMINI_PRO_MODEL`, `GEMINI_LIVE_MODEL` | model ids |
| `QR_SESSION_SIGNING_KEY` | HMAC key for entrance and receipt tokens (secret) |
| `JOB_KEY` | shared secret for `/jobs/*` (secret) |
| `APP_BASE_URL`, `CORS_ORIGINS` | hosting origin |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | optional; mock payments when unset |

## Status

Everything described above is live and covered by the unit suite. Built and reviewed on 15 to 17 Oct 2026: phases 0 to 7 of the plan plus roadmap releases R1 (self-service shops), R3 (scan-first), R4 (shopper identity), R5 (customers, offers, points) and the R2 sync core.

Pending, in priority order (details in `docs/plan/09-roadmap-after-submission.md`):

- Shopify adapter on the existing sync contract (Admin GraphQL, `orders/create` and `inventory_levels/update` webhooks) and POS file drops from Cloud Storage.
- MCP server so any external shopping assistant can search, reserve and buy from a store.
- GST invoices, returns against a receipt, and the 90-day retention job for verification records and conversation turns.
- Phone sign-in for non-Indian numbers; logo upload for store branding; a retry button for dead outbox entries.

Known gaps kept on purpose are listed at the end of `docs/security.md` (cart add outside a transaction, owner membership not revoked on email removal, sync signatures not bound to the URL path, shared job key instead of Scheduler OIDC, no automatic refund for an order cancelled by a later checkout attempt).

## For judges

- Owner dashboard: sign in with a Google account listed on the demo store (ask the team), or register your own store with any Google account: the dashboard opens a registration form, and the Connectors tab imports a CSV or lets you add products by scanning a barcode.
- Shopper sign-in is optional. Test numbers `+91 99999 00001`, `00002`, `00003` with code `123456` work without an SMS (Firebase test numbers); real Indian numbers receive a real code.
- Kiosk PIN for `demo-grocery` is `1234`. Payments are sandbox only.
- Sync from a billing system: generate a secret in Connectors → Live sync, then run `python infra/scripts/sync_example.py --store demo-grocery --secret <secret> --sku <sku> --on-hand 2`; the assistant reflects the change within two seconds.
- The model never invents stock, prices or locations: every product fact in a reply comes from a tool call, and the UI renders cards, map highlights and cart state only from tool results.
- Demo walkthrough: `docs/demo-script.md`. Submission links: `docs/submission-checklist.md`.
