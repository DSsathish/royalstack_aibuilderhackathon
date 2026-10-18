"""Owner-only import endpoints: the inventory field schema and Excel template, a checked template upload, a mapped CSV
import and an AI-proposed mapping. Design: docs/lld/inventory-intake.md and docs/lld/connector-agent.md."""

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.config import settings
from app.connectors import csv_connector as csvc
from app.connectors import normalizer, schema
from app.domain.models import now
from app.services import catalog, connectors, db
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


MAX_ERRORS_SHOWN = 50


@router.get("/{store_id}/inventory/schema")
def inventory_schema(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return {"fields": schema.fields(), "sheet_template_url": settings.inventory_sheet_template_url}


@router.get("/{store_id}/inventory/template.xlsx")
def inventory_template(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return Response(schema.template_xlsx(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="inventory-template.xlsx"'})


@router.post("/{store_id}/inventory/upload")
async def upload_inventory(store_id: str = STORE_ID, file: UploadFile = File(...), apply: bool = Form(default=False),
                           allow_updates: bool = Form(default=False), uid: str = Depends(current_uid)):
    """Check a filled template (.xlsx or .csv) and, with apply, write it. Nothing is written when a required column is
    missing; rows with errors are skipped and reported with their line numbers."""
    require_owner(store_id, uid)
    name = file.filename or ""
    if not name.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(400, "upload an .xlsx or .csv file")
    data = await file.read(connectors.MAX_BYTES + 1)
    if len(data) > connectors.MAX_BYTES:
        raise HTTPException(413, f"file larger than {connectors.MAX_BYTES // (1024 * 1024)} MB")
    try:
        columns, records = connectors.read_file(data, name)
    except connectors.SourceError as exc:
        raise HTTPException(400, str(exc))
    check = schema.check_headers(columns)
    out = {"ok": not check["missing_required"], "columns": columns, "missing_required": check["missing_required"],
           "unknown": check["unknown"], "row_count": len(records), "errors": [], "error_count": 0, "duplicates": [], "preview": None, "result": None}
    if check["missing_required"]:
        return out
    rows, errors = csvc.rows_from_records(records, check["mapping"])
    seen: dict[str, int] = {}
    unique = []
    for r in rows:
        key = csvc.slug(r.sku)                     # the same identity the catalog uses for the product id
        if key in seen:
            out["duplicates"].append({"line": r.line, "sku": r.sku, "first_line": seen[key]})
            continue
        seen[key] = r.line
        unique.append(r)
    out["errors"] = [e.model_dump() for e in errors[:MAX_ERRORS_SHOWN]]
    out["error_count"] = len(errors)
    out["preview"] = connectors.preview(store_id, unique, errors)
    if apply:
        store = db.store_ref(store_id).get().to_dict() or {}
        result = csvc.upsert(store_id, unique, high_value_threshold=store.get("high_value_threshold", 500), skip_existing=not allow_updates)
        catalog.bump(store_id)
        summary = {"created": result.created, "updated": result.updated, "skipped": result.skipped, "errors": len(errors), "duplicates": len(out["duplicates"]), "file": name[:80]}
        db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "inventory_upload", "created_at": now(), "payload": summary})
        out["result"] = summary
    return out
