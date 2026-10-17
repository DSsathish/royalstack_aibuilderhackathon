"""Owner: live sync settings, secret rotation, manual pull, test event, sync log."""

import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud import firestore
from pydantic import BaseModel, Field

from app.connectors import csv_connector as csvc
from app.domain.models import Sync, now
from app.services import db, sync
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(prefix="/owner", tags=["owner"])


class SyncPatch(BaseModel):
    webhook_url: str | None = Field(default=None, max_length=500)
    feed_url: str | None = Field(default=None, max_length=1000)
    feed_mapping: dict[str, str] | None = None
    feed_every_min: int | None = Field(default=None, ge=5, le=1440)


def _https(url: str) -> str:
    if not url:
        return ""
    u = urlparse(url)
    if u.scheme == "https" or (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")):
        return url
    raise HTTPException(422, "URL must use https")


def _audit(store_id: str, uid: str, action: str, payload: dict) -> None:
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": action, "created_at": now(), "payload": payload})


def _view(request: Request, store_id: str) -> dict:
    doc = db.store_ref(store_id).get().to_dict() or {}
    base = str(request.base_url).rstrip("/")
    log = [d.to_dict() for d in db.sync_log(store_id).order_by("at", direction=firestore.Query.DESCENDING).limit(30).stream()]
    outbox = [d.to_dict() for d in db.sync_outbox(store_id).stream()]
    return {"settings": Sync(**(doc.get("sync") or {})).model_dump() | {"catalog_version": doc.get("catalog_version", 0)},
            "endpoints": {"inventory": f"{base}/sync/{store_id}/inventory", "products": f"{base}/sync/{store_id}/products", "pull": f"{base}/sync/{store_id}/inventory"},
            "log": log, "outbox": {"pending": sum(1 for e in outbox if not e.get("dead")), "dead": sum(1 for e in outbox if e.get("dead"))}}


@router.get("/{store_id}/sync")
def get_sync(request: Request, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return _view(request, store_id)


@router.patch("/{store_id}/sync")
def patch_sync(body: SyncPatch, request: Request, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    changes: dict = {}
    if body.webhook_url is not None:
        changes["sync.webhook_url"] = _https(body.webhook_url.strip())
    if body.feed_url is not None:
        changes["sync.feed_url"] = _https(body.feed_url.strip())
    if body.feed_mapping is not None:
        bad = [k for k in body.feed_mapping if k not in csvc.REQUIRED + csvc.OPTIONAL]
        if bad:
            raise HTTPException(422, f"unknown mapping fields: {bad}")
        changes["sync.feed_mapping"] = {k: v for k, v in body.feed_mapping.items() if v}
    if body.feed_every_min is not None:
        changes["sync.feed_every_min"] = body.feed_every_min
    if changes:
        db.store_ref(store_id).update(changes)
        _audit(store_id, uid, "sync_settings", {"fields": sorted(k.split(".", 1)[1] for k in changes)})
    return _view(request, store_id)


@router.post("/{store_id}/sync/secret")
def rotate_secret(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    value = sync.new_secret(store_id)
    _audit(store_id, uid, "sync_secret_rotated", {})
    return {"secret": value}


@router.post("/{store_id}/sync/pull")
def pull_now(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return sync.pull_feed(store_id)


@router.post("/{store_id}/sync/test")
def test_event(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return sync.send_test(store_id)
