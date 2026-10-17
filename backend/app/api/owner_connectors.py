"""Owner-only connector agent endpoints: inspect a source, apply it, keep it in step. Design: docs/lld/connector-agent.md."""

import json
import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.connectors import csv_connector as csvc
from app.domain.models import now
from app.services import connectors, db
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(prefix="/owner", tags=["owner"])


def _audit(store_id: str, actor: str, action: str, payload: dict) -> None:
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": actor, "action": action, "created_at": now(), "payload": payload})


async def _source(kind: str, file: UploadFile | None, url: str, auth: str, dsn: str, table: str) -> dict:
    if kind not in connectors.KINDS:
        raise HTTPException(400, "kind must be file, sheet, api or db")
    if kind == "file":
        if not file:
            raise HTTPException(400, "a file is required")
        data = await file.read(connectors.MAX_BYTES + 1)
        return {"data": data, "filename": file.filename or ""}
    if kind in ("sheet", "api"):
        if not url:
            raise HTTPException(400, "a link is required")
        return {"url": url, "auth": auth} if kind == "api" else {"url": url}
    if not dsn or not table:
        raise HTTPException(400, "a connection string and a table are required")
    return {"dsn": dsn, "table": table}


def _mapping(raw: str, required: bool) -> dict | None:
    if not raw:
        if required:
            raise HTTPException(400, "a mapping is required")
        return None
    try:
        m = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "mapping must be JSON")
    if not isinstance(m, dict):
        raise HTTPException(400, "mapping must be an object")
    return m


@router.post("/{store_id}/connectors/inspect")
async def inspect(store_id: str = STORE_ID, kind: str = Form(...), file: UploadFile | None = File(default=None),
                  url: str = Form(default=""), auth: str = Form(default=""), dsn: str = Form(default=""), table: str = Form(default=""),
                  mapping: str = Form(default=""), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    source = await _source(kind, file, url, auth, dsn, table)
    try:
        out = connectors.inspect(store_id, kind, mapping=_mapping(mapping, required=False), **source)
    except (connectors.SourceError, csvc.ImportError_) as exc:
        raise HTTPException(400, str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"could not fetch the source: {exc}")
    _audit(store_id, uid, "connector_inspect", {"kind": kind, "rows": out["row_count"], "mapped": len(out["mapping"]), "problem": out["problem"]})
    return out


@router.post("/{store_id}/connectors/apply")
async def apply(store_id: str = STORE_ID, kind: str = Form(...), file: UploadFile | None = File(default=None),
                url: str = Form(default=""), auth: str = Form(default=""), dsn: str = Form(default=""), table: str = Form(default=""),
                mapping: str = Form(...), label: str = Form(default=""), save: bool = Form(default=False), every_min: int = Form(default=15),
                uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    source = await _source(kind, file, url, auth, dsn, table)
    m = _mapping(mapping, required=True)
    try:
        result = connectors.apply(store_id, kind, mapping=m, actor=uid, label=label or kind, **source)
        saved = None
        if save and kind in connectors.KEEPABLE:
            saved = connectors.save(store_id, kind, label=label, mapping={k: v for k, v in m.items() if v}, actor=uid, url=source.get("url", ""), table=source.get("table", ""), every_min=every_min,
                                    auth=source.get("auth", ""), dsn=source.get("dsn", ""))
    except (connectors.SourceError, csvc.ImportError_) as exc:
        raise HTTPException(400, str(exc))
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"could not fetch the source: {exc}")
    return {"result": result, "connector": saved.model_dump() if saved else None}


class DsnIn(BaseModel):
    dsn: str


@router.post("/{store_id}/connectors/discover")
def discover(body: DsnIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    try:
        return {"tables": connectors.discover(body.dsn)}
    except connectors.SourceError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"could not connect: {str(exc)[:160]}")


@router.get("/{store_id}/connectors")
def list_connectors(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return {"connectors": [c.model_dump() for c in connectors.list_(store_id)]}


@router.post("/{store_id}/connectors/{cid}/run")
def run_now(cid: str, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    c = connectors.get(store_id, cid)
    if not c:
        raise HTTPException(404, "connector not found")
    return connectors.run(store_id, c, actor=uid)


@router.delete("/{store_id}/connectors/{cid}")
def delete(cid: str, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    if not connectors.remove(store_id, cid, uid):
        raise HTTPException(404, "connector not found")
    return {"ok": True}
