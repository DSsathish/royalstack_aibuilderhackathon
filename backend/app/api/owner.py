"""Owner dashboard endpoints and the scheduled jobs trigger."""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.models import now
from app.services import db, insights, reorder, sessions, verification
from app.services.auth import STORE_ID, current_uid, owned_stores, require_owner

router = APIRouter(tags=["owner"])
PID = Path(pattern=r"^[a-z0-9-]{3,80}$")


@router.get("/owner/me")
def me(uid: str = Depends(current_uid)):
    return {"uid": uid, "stores": owned_stores(uid)}


@router.post("/owner/{store_id}/session")
def owner_session(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    """An owner-mode agent session for the dashboard chat; the only way to get one outside dev."""
    require_owner(store_id, uid)
    return sessions.create(store_id, "owner", user_id=uid).model_dump()


@router.get("/owner/{store_id}/overview")
def overview(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return insights.overview(store_id)


@router.get("/owner/{store_id}/inventory")
def inventory(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return insights.inventory(store_id)


class InventoryPatch(BaseModel):
    reorder_point: int | None = Field(default=None, ge=0, le=100000)
    reorder_qty: int | None = Field(default=None, ge=0, le=100000)


@router.patch("/owner/{store_id}/inventory/{product_id}")
def patch_inventory(body: InventoryPatch, store_id: str = STORE_ID, product_id: str = PID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    ref = db.inventory(store_id).document(product_id)
    if not ref.get().exists:
        raise HTTPException(404, "product not found")
    ref.update({k: v for k, v in body.model_dump().items() if v is not None})
    return ref.get().to_dict()


class CountIn(BaseModel):
    product_id: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    counted: int = Field(ge=0, le=100000)


@router.post("/owner/{store_id}/counts")
def quick_count(body: CountIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    insights.record_count(store_id, body.product_id, counted=body.counted, by=uid)
    return {"ok": True}


@router.get("/owner/{store_id}/reorders")
def reorders(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return [d.model_dump() for d in reorder.list_drafts(store_id)]


@router.post("/owner/{store_id}/reorders/draft")
def make_drafts(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return [d.model_dump() for d in reorder.draft(store_id, created_by=uid)]


class ApproveIn(BaseModel):
    qty: dict[str, int] = {}


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/owner/{store_id}/reorders/{po_id}/approve")
def approve(body: ApproveIn, store_id: str = STORE_ID, po_id: str = Path(pattern=r"^[a-f0-9]{32}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    try:
        return reorder.approve(store_id, po_id, by=uid, qty_override=body.qty).model_dump()
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post("/owner/{store_id}/reorders/{po_id}/reject")
def reject(body: RejectIn, store_id: str = STORE_ID, po_id: str = Path(pattern=r"^[a-f0-9]{32}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    try:
        return reorder.reject(store_id, po_id, by=uid, reason=body.reason).model_dump()
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.get("/owner/{store_id}/signals")
def signals(store_id: str = STORE_ID, days: int = Query(default=7, ge=1, le=90), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return insights.signals(store_id, days)


SETTINGS_KEYS = ("self_checkout_item_limit", "high_value_threshold", "audit_rate", "kiosk_pin")


@router.get("/owner/{store_id}/loss")
def loss(store_id: str = STORE_ID, days: int = Query(default=7, ge=1, le=90), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get().to_dict()
    return {"summary": verification.summary(store_id, days), "shrink": insights.shrink(store_id),
            "recent": [v.model_dump() for v in verification.recent(store_id, days)[:50]],
            "settings": {k: store.get(k) for k in SETTINGS_KEYS}}


class SettingsPatch(BaseModel):
    self_checkout_item_limit: int | None = Field(default=None, ge=1, le=100)
    high_value_threshold: float | None = Field(default=None, ge=0)
    audit_rate: float | None = Field(default=None, ge=0, le=1)
    kiosk_pin: str | None = Field(default=None, min_length=4, max_length=12, pattern=r"^[0-9]+$")


@router.patch("/owner/{store_id}/settings")
def patch_settings(body: SettingsPatch, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    changes = {k: v for k, v in body.model_dump().items() if v is not None}
    db.store_ref(store_id).update(changes)
    db.audit(store_id).document(now().strftime("%Y%m%d%H%M%S%f")).set({"actor": uid, "action": "settings", "created_at": now(), "payload": changes})
    return changes


@router.post("/jobs/forecast")
def forecast_job(store_id: str = Query(pattern=r"^[a-z0-9-]{3,40}$"), x_job_key: str | None = Header(default=None)):
    if not settings.job_key or not x_job_key or not hmac.compare_digest(x_job_key, settings.job_key):
        raise HTTPException(401, "job key required")
    from app.jobs import forecast as job
    return job.run(store_id)
