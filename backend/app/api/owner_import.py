"""Owner-only connector endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.connectors import csv_connector as csvc
from app.domain.models import now
from app.services import catalog, db
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(prefix="/owner", tags=["owner"])


@router.post("/{store_id}/import/csv", response_model=csvc.ImportResult)
async def import_csv(store_id: str = STORE_ID, file: UploadFile = File(...), mapping: str = Form(...),
                     uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get()
    if not store.exists:
        raise HTTPException(404, "store not found")
    try:
        mapping_obj = json.loads(mapping)
        if not isinstance(mapping_obj, dict):
            raise csvc.ImportError_("mapping must be a JSON object")
        rows, errors = csvc.parse(await file.read(), mapping_obj)
    except (csvc.ImportError_, json.JSONDecodeError) as exc:
        raise HTTPException(400, str(exc))

    result = csvc.upsert(store_id, rows, high_value_threshold=store.to_dict()["high_value_threshold"])
    result.errors = errors
    catalog.invalidate(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({
        "actor": uid, "action": "import_csv", "created_at": now(),
        "payload": {"created": result.created, "updated": result.updated, "errors": len(errors)},
    })
    return result
