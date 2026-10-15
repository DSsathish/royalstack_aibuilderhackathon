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

**Owner.** Google sign-in. Live sales, inventory with BigQuery ML forecasts and days of cover, reorder drafts with a Gemini-written rationale waiting for approval, "asked but not carried" signals captured from conversations, exit-loss view with controls, CSV import with column mapping, and the owner assistant by text or live voice.

## Google Cloud services

Cloud Run (API and websocket bridge), Firebase Hosting (static PWA), Firebase Auth (owner sign-in), Firestore (operational data), BigQuery and BigQuery ML `ARIMA_PLUS` (sales history and forecasts), Vertex AI Gemini (`gemini-3.5-flash`, `gemini-live-2.5-flash`, `gemini-embedding-001`), Google ADK (agent runtime), Cloud Scheduler (nightly forecast), Secret Manager, Cloud Build, Artifact Registry.

## Codebase

```
backend/                 Python 3.12, FastAPI, Google ADK, google-genai
  app/main.py            app, routers, startup warm-up
  app/config.py          settings from env; refuses the default signing key outside dev/test
  app/domain/models.py   all Firestore models
  app/services/          db paths, inventory (transactions), catalog (keyword + embeddings), cart, checkout,
                         qr (signed tokens), sessions, verification (7 layers), vision, forecast, reorder,
                         insights, auth, gemini
  app/agent/             tools.py (plain functions, mode-gated), prompts.py, agent.py (ADK, SSE),
                         live.py (Gemini Live websocket bridge)
  app/api/               catalog, shop, agent (chat, audio, live), exit (kiosk), owner, owner_import
  app/jobs/forecast.py   sales sync -> ARIMA_PLUS -> forecasts in Firestore
  app/connectors/        csv_connector (column mapping, caps, idempotent upsert)
  tests/                 171 unit tests (Firestore emulator) + live tests gated by LIVE_GEMINI=1
frontend/                Next.js 16 static export, TypeScript, Tailwind
  app/enter, shop, checkout, receipt, exit, kiosk, owner
  components/            Chat (text, voice loop, live voice), Scanner, Cart, StoreMap, TotalBar, Avatar, RevenueChart
  lib/                   api.ts, sse.ts, voice.ts, live.ts, store.ts, firebase.ts, owner.ts
  public/pcm-worklet.js  microphone -> 16 kHz PCM for live voice
infra/seed/              demo store generator (170 products, 90 days of sales), seed script
docs/                    hld.md, security.md, lld/ (one per module group), plan/ (phased plan)
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

## For judges

- Owner dashboard: sign in with a Google account listed on the demo store (ask the team), or read the API at `/docs`.
- Kiosk PIN for `demo-grocery` is `1234`. Payments are sandbox only.
- The model never invents stock, prices or locations: every product fact in a reply comes from a tool call, and the UI renders cards, map highlights and cart state only from tool results.
