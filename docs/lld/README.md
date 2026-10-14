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
