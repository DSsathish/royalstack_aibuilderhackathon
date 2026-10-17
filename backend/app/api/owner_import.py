"""Owner-only connector endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import csv
import io

from app.connectors import csv_connector as csvc
from app.connectors import normalizer
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
    catalog.bump(store_id)
    db.audit(store_id).document(uuid.uuid4().hex).set({
        "actor": uid, "action": "import_csv", "created_at": now(),
        "payload": {"created": result.created, "updated": result.updated, "errors": len(errors)},
    })
    return result


@router.post("/{store_id}/import/propose")
async def propose_mapping(store_id: str = STORE_ID, file: UploadFile = File(...), uid: str = Depends(current_uid)):
    """Read the header and a few rows, ask the normalizer for a mapping the owner can confirm or edit."""
    require_owner(store_id, uid)
    data = await file.read(csvc.MAX_BYTES + 1)
    if len(data) > csvc.MAX_BYTES:
        raise HTTPException(413, "file larger than 5 MB")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
        header = reader.fieldnames or []
        samples = [row for _, row in zip(range(5), reader)]
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(400, f"file is not valid UTF-8 CSV: {exc}")
    if not header:
        raise HTTPException(400, "empty file")
    proposal = normalizer.propose(header, samples)
    db.audit(store_id).document(uuid.uuid4().hex).set({
        "actor": uid, "action": "import_proposed", "created_at": now(),
        "payload": {"source": proposal.source, "confidence": proposal.confidence, "mapped": len(proposal.mapping)}})
    return {"proposal": proposal.model_dump(), "header": header, "samples": samples}
