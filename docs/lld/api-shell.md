# LLD: API shell (`backend/app/main.py`, `backend/app/config.py`)

**Responsibility.** Start the FastAPI app, load settings, mount routers, expose a health check.

**Inputs / outputs.**
- In: environment variables (see `backend/.env.example`).
- Out: HTTP app on port 8080; `GET /healthz` → `{"ok": true, "env": "<env>"}`.

**Functions.**
- `config.Settings` — pydantic settings; one field per env var, defaults for dev.
- `main.app` — FastAPI instance with CORS; routers from later phases are included here with `app.include_router(...)`.
- `main.healthz()` — liveness check used by Cloud Run and the uptime monitor.

**Dependencies.** fastapi, pydantic-settings. No cloud calls at import time.

**Not in scope.** Auth, DB clients, agent setup. Those live in their own modules and are imported by routers, not by `main.py`.
