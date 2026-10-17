# Low-Level Design (LLD) notes

One short file per module or agent, written before the code. Each file answers five questions and nothing more:

1. **Responsibility** — one sentence, what this module owns.
2. **Inputs / outputs** — data in, data out, with types.
3. **Functions** — name, signature, one line each.
4. **Dependencies** — what it calls (Firestore, Gemini, other modules).
5. **Not in scope** — what it deliberately does not do.

Rules we follow in code:
- Plain functions over class hierarchies. One obvious way per concern.
- No abstraction until a second real caller exists.
- No config knobs for hypothetical needs.
- A module is one file until it exceeds ~300 lines.

| Module | LLD | Status |
|---|---|---|
| backend/app (API shell) | [api-shell.md](api-shell.md) | done |
| models, db, inventory, catalog, csv connector, auth, routers, seed | [phase-1-data.md](phase-1-data.md) | done |
| sessions, cart, agent tools, prompts, agent runtime, chat/audio API | [phase-2-agent.md](phase-2-agent.md) | done, live eval 8/8 on Vertex AI |
| qr tokens, checkout, shop API, shopper PWA | [phase-3-instore.md](phase-3-instore.md) | done |
| verification layers, vision bag check, exit API, kiosk | [phase-4-exit.md](phase-4-exit.md) | done |
| live speech-to-speech bridge, PCM worklet, live client (shopper and owner) | [live-voice.md](live-voice.md) | done |
| forecasts, reorder drafts, insights, owner API, forecast job, owner dashboard | [phase-6-owner.md](phase-6-owner.md) | done |
| universal normalizer (column mapping agent), dataset import | [normalizer.md](normalizer.md) | done; dataset import awaits a Kaggle file |
| conversation memory, voice tuning, reconnect, named voice | [voice-memory.md](voice-memory.md) | done |
| R1 self-service shops: registration, setup, roles, per-store payments | [r1-self-service.md](r1-self-service.md) | done |
| R3 scan-first cart, owner add-by-scan with barcode lookup | [r3-scan-first.md](r3-scan-first.md) | done |
| R4 optional shopper identity: phone OTP, profile, history, export and delete, customers for owners | [r4-identity.md](r4-identity.md) | done |
| R5 segments, owner-created offers applied automatically, reward points ledger, nightly customer job | [r5-customers-offers-points.md](r5-customers-offers-points.md) | done |
| R2 sync core: signed inbound webhooks, pull endpoint, outbound sale events with retries, scheduled CSV feed, cross-instance catalog version | [r2-sync.md](r2-sync.md) | done; Shopify adapter next |
| Owner agent: separate prompt and full-access tools, confirmation in code before any change, briefing and table rendering in the dashboard chat | [owner-agent.md](owner-agent.md) | done |
| Product classification (storage and use), floor blocks and floors, scan-to-cart, voice language | [classification-floors-scan.md](classification-floors-scan.md) | done |
- [product-facts.md](product-facts.md): grounded product facts tool with guardrails (18 Oct)
- [connector-agent.md](connector-agent.md): bring any external data in through one agent, preview then confirm (18 Oct)
- [shopper-ui.md](shopper-ui.md): shopper assistant screen with the floating voice pill (18 Oct)
