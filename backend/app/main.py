"""FastAPI entry point. Routers are added here as phases land."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import agent, catalog, exit, owner, owner_import, shop
from app.config import settings

app = FastAPI(title="Retail Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

log = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON on unexpected errors so CORS headers still apply and the client sees a real message."""
    ref = uuid.uuid4().hex[:8]
    log.exception("unhandled error %s on %s %s: %s", ref, request.method, request.url.path, exc)
    # this handler runs outside the CORS middleware, so add the header for allowed origins ourselves
    origin = request.headers.get("origin", "")
    headers = {"Access-Control-Allow-Origin": origin} if origin in settings.cors_origins else {}
    return JSONResponse({"detail": f"internal error (ref {ref})"}, status_code=500, headers=headers)


app.include_router(catalog.router)
app.include_router(owner_import.router)
app.include_router(agent.router)
app.include_router(shop.router)
app.include_router(exit.router)
app.include_router(owner.router)


@app.on_event("startup")
def warm_up() -> None:
    """Pay the cold Gemini client/auth cost once at boot, off the request path."""
    import threading

    from app.services import gemini

    def go():
        try:
            gemini.embed_texts(["warm up"], for_query=True)
        except Exception:
            pass

    if gemini.configured() and settings.env != "test":
        threading.Thread(target=go, daemon=True).start()


@app.get("/health")  # /healthz is intercepted by Google front ends on Cloud Run
def healthz() -> dict:
    return {"ok": True, "env": settings.env}
