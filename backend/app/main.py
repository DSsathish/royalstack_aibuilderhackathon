"""FastAPI entry point. Routers are added here as phases land."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, catalog, exit, owner_import, shop
from app.config import settings

app = FastAPI(title="Retail Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(owner_import.router)
app.include_router(agent.router)
app.include_router(shop.router)
app.include_router(exit.router)


@app.get("/health")  # /healthz is intercepted by Google front ends on Cloud Run
def healthz() -> dict:
    return {"ok": True, "env": settings.env}
