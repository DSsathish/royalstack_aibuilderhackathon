# Implementation Plan: Overview

AI Builder Cup 2026 (Google Cloud JAPAC, run by Hack2skill)
Theme 2: Retail & Commerce — Intelligent Customer and Business Experiences

## One-line pitch

One AI commerce agent and one inventory truth across the physical store, the online store, and the owner's back office, built on top of the software the retailer already uses.

## Positioning

- No competitor combines in-store QR agent, shelf navigation, self-checkout with layered exit verification, online agent, and owner inventory intelligence on one engine.
- Big retailers (Walmart, Sam's Club, Amazon) do pieces of this with expensive hardware. We deliver the full loop to small and mid-size retailers with a phone and a QR code.
- The chat assistant is the interface. Inventory truth plus layered fraud control is the product. Shelf navigation is the surprise.

## Hard constraints (from the hackathon)

| Item | Requirement |
|---|---|
| Submission deadline | 18 Oct 2026 |
| Gen AI models | Google only: Gemini / Gemma, or Google agentic platforms (ADK, Agent Platform, AI Studio) |
| Deployment | Cloud Run and/or Firebase. Other clouds make the entry ineligible |
| Deliverables | Live deployed link, demo video < 3 min, public GitHub repo, PDF deck |
| Team | 2 to 4 members, 21+, working professionals in JAPAC, no students |
| Freshness | Project must be built inside the hackathon window |
| Language | All code, docs, deck in English |

## Judging weights and what we do about each

| Criterion | Weight | How we score it |
|---|---|---|
| Technical Merit & Gen AI Implementation | 40% | ADK agent with real tools, multimodal (vision, voice), grounding on live inventory, BigQuery ML + Gemini reasoning, layered verification |
| Problem Alignment & Impact | 25% | Shrink and stockout figures in the deck, physical + digital + owner in one system, regional onboarding via CSV/Sheets/WhatsApp |
| Innovation & Creativity | 25% | Conversation-derived demand signals, shelf navigation, vision-assisted exit check for small retailers |
| User Experience & Solution Design | 10% | PWA with no install, running receipt, voice in Tamil/Hindi/English, clean owner inbox |

## Phases

| Phase | File | Goal | Target date |
|---|---|---|---|
| 0 | [01-phase-0-setup.md](01-phase-0-setup.md) | Google Cloud project, repo, CI, local environment | 14 Oct evening |
| 1 | [02-phase-1-data-foundation.md](02-phase-1-data-foundation.md) | Canonical schema, Firestore + BigQuery, seed store, CSV/Sheets connector | 15 Oct |
| 2 | [03-phase-2-agent-core.md](03-phase-2-agent-core.md) | ADK agent, tools, context modes, Gemini models | 15 Oct |
| 3 | [04-phase-3-instore-shopper.md](04-phase-3-instore-shopper.md) | QR session, PWA chat, voice, navigation, scan, cart, checkout | 16 Oct |
| 4 | [05-phase-4-exit-verification.md](05-phase-4-exit-verification.md) | Layered exit verification, kiosk, vision bag check, audits | 16 to 17 Oct |
| 5 | [06-phase-5-digital-commerce.md](06-phase-5-digital-commerce.md) | Online storefront mode, embeddable widget, WhatsApp | 17 Oct |
| 6 | [07-phase-6-owner-inventory.md](07-phase-6-owner-inventory.md) | Owner dashboard, forecasting, reorder approvals, alerts, loss dashboard | 17 Oct |
| 7 | [08-phase-7-hardening-submission.md](08-phase-7-hardening-submission.md) | Security, tests, monitoring, demo, video, deck, submission | 18 Oct |

Phases 1 and 2 can run in parallel. Phases 3, 5, 6 can run in parallel once phase 2 exposes the agent API. Phase 4 depends on phase 3 checkout.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) PWA on Firebase Hosting. Shopper app, widget, owner dashboard, exit kiosk |
| Backend | Python 3.12, FastAPI, Google ADK, on Cloud Run |
| Agent models | Gemini Flash (chat, extraction, vision), Gemini Pro (reorder planning, anomaly reasoning). Use the latest stable IDs listed in AI Studio on build day |
| Operational data | Firestore (native mode) |
| Analytics / forecasting | BigQuery + BigQuery ML (ARIMA_PLUS) |
| Jobs | Cloud Scheduler + Pub/Sub + Cloud Run jobs |
| Auth | Firebase Auth (anonymous, phone, Google) |
| Secrets | Secret Manager |
| Payments | Razorpay test mode (sandbox only) |
| WhatsApp | Twilio WhatsApp sandbox |
| CI/CD | GitHub Actions to Cloud Run and Firebase Hosting |

## Repository layout

```
aibuildercup-retail/
  README.md
  docs/
    plan/            this plan
    architecture.md  diagram + data flow (phase 7)
    demo-script.md   (phase 7)
  backend/
    app/
      main.py            FastAPI entry
      config.py
      agent/             ADK agent, tools, prompts
      connectors/        csv, sheets, shopify
      domain/            schema models (pydantic)
      services/          inventory, cart, checkout, verification, forecast
      api/               routers
    tests/
    Dockerfile
    pyproject.toml
  frontend/
    app/
      (shopper)/         in-store + online PWA
      widget/            embeddable script build
      owner/             dashboard
      kiosk/             exit verification screen
    public/
    next.config.js
  infra/
    scripts/             gcloud setup scripts
    seed/                demo store data (CSV)
  .github/workflows/
```

## Decisions already taken

- Own web store rather than a Shopify dev store. Shopify connector is stretch.
- Grocery demo store, one physical location, one online store.
- Browser extension dropped in favor of embeddable widget.
- 3D avatar is a day 4 stretch; 2D animated avatar with voice in core.
- CSV and Google Sheets connectors first, Shopify second.
- Exit verification is layered. Gemini vision is a confidence signal, never the sole gate.
- Bag photos are processed and discarded; only verdict, confidence, hash stored.
- No live money. Razorpay test mode only.

## Open items (fill in on day 1)

- Team members and roles: to be filled for the deck
- Google Cloud project ID: `royastacxk-aibuildercup` (project number 881917398995), region `asia-south1`
- Gemini API access: Vertex AI
- GitHub repo: https://github.com/DSsathish/royalstack_aibuilderhackathon
- Backend live: https://retail-api-881917398995.asia-south1.run.app (Cloud Run, asia-south1, service account retail-api, ENV=demo)
- Frontend: Firebase Hosting at https://royastacxk-aibuildercup.web.app once Firebase is added to the project
- Billing: linked 15 Oct. $20 budget with alerts at 50% and 90%. Vertex AI on the `global` endpoint: `gemini-3.5-flash` (chat), `gemini-3.1-pro-preview` (reasoning), `gemini-embedding-001`.

## Team role split (suggested for 3 people)

| Role | Owns |
|---|---|
| Backend / agent | Phases 1, 2, 4 (verification logic), 6 (forecast) |
| Frontend | Phases 3, 5, owner dashboard UI, kiosk UI |
| Product / infra | Phase 0, CI/CD, seed data, demo script, video, deck, submission |

With 2 people: person A = backend/agent/infra, person B = frontend/product/deck.
