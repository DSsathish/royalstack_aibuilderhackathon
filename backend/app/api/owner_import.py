"""Owner-only connector endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from app.connectors import csv_connector as csvc
from app.domain.models import now
from app.services import catalog, db
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(prefix="/owner", tags=["owner"])


@router.post("/{store_id}/import/csv", response_model=csvc.ImportResult)
async def import_csv(store_id: str = STORE_ID, file: UploadFile = None, mapping: str = Form(...),
                     uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get()
    if not store.exists:
        raise HTTPException(404, "store not found")
    try:
        rows, errors = csvc.parse(await file.read(), json.loads(mapping))
    except (csvc.ImportError_, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(400, str(exc))

    result = csvc.upsert(store_id, rows, high_value_threshold=store.to_dict()["high_value_threshold"])
    result.errors = errors
    catalog.invalidate(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({
        "actor": uid, "action": "import_csv", "created_at": now(),
        "payload": {"created": result.created, "updated": result.updated, "errors": len(errors)},
    })
    return result
