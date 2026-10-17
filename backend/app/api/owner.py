"""Owner dashboard endpoints and the scheduled jobs trigger."""

import hmac
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.models import Offer, Segment, now
from app.services import db, insights, reorder, sessions, verification
from app.services.auth import STORE_ID, current_uid, require_owner, require_staff, roles_for

router = APIRouter(tags=["owner"])
PID = Path(pattern=r"^[a-z0-9-]{3,80}$")


def _audit(store_id: str, actor: str, action: str, payload: dict) -> None:
    import uuid
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": actor, "action": action, "created_at": now(), "payload": payload})


@router.get("/owner/me")
def me(uid: str = Depends(current_uid)):
    roles = roles_for(uid)
    return {"uid": uid, "stores": sorted(roles), "roles": roles}


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
    require_staff(store_id, uid)          # staff count shelves from this list; edits stay owner-only
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
    require_staff(store_id, uid)
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


@router.get("/owner/{store_id}/customers")
def customers_list(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    """Signed-in customers only; guests appear as counts in the overview."""
    require_owner(store_id, uid)
    from google.cloud import firestore
    rows = [d.to_dict() for d in db.customers(store_id).order_by("spend", direction=firestore.Query.DESCENDING).limit(500).stream()]
    keep = ("uid", "phone_last4", "name", "language", "dietary", "favourite_categories", "visits", "spend", "points", "segment", "last_seen", "created_at")
    return [{k: r.get(k) for k in keep} for r in rows]


class PointsAdjust(BaseModel):
    delta: int = Field(ge=-100_000, le=100_000)
    reason: str = Field(min_length=1, max_length=120)


@router.post("/owner/{store_id}/customers/{uid}/points")
def adjust_points(body: PointsAdjust, store_id: str = STORE_ID, uid: str = Path(max_length=128), owner_uid: str = Depends(current_uid)):
    require_owner(store_id, owner_uid)
    from app.services import points
    try:
        balance = points.adjust(store_id, uid, body.delta, body.reason, by=owner_uid)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    _audit(store_id, owner_uid, "points_adjusted", {"customer": uid, "delta": body.delta, "reason": body.reason})
    return {"uid": uid, "points": balance}


# --- offers -----------------------------------------------------------------

class OfferIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: Literal["product", "category", "cart"]
    product_id: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=40)
    min_total: float = Field(default=0, ge=0, le=1_000_000)
    percent_off: float = Field(default=0, ge=0, le=90)
    amount_off: float = Field(default=0, ge=0, le=1_000_000)
    segment: Segment = "all"
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class OfferPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    kind: Literal["product", "category", "cart"] | None = None
    product_id: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=40)
    min_total: float | None = Field(default=None, ge=0, le=1_000_000)
    percent_off: float | None = Field(default=None, ge=0, le=90)
    amount_off: float | None = Field(default=None, ge=0, le=1_000_000)
    segment: Segment | None = None
    active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@router.get("/owner/{store_id}/offers")
def list_offers(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    from app.services import offers
    return [o.model_dump() | {"detail": offers.describe(store_id, o)} for o in offers.list_all(store_id)]


@router.post("/owner/{store_id}/offers")
def create_offer(body: OfferIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    from app.services import offers
    try:
        o = offers.create(store_id, Offer(offer_id="", store_id=store_id, created_by=uid, **body.model_dump()))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    _audit(store_id, uid, "offer_created", {"offer_id": o.offer_id, "name": o.name, "kind": o.kind})
    return o.model_dump() | {"detail": offers.describe(store_id, o)}


@router.patch("/owner/{store_id}/offers/{offer_id}")
def patch_offer(body: OfferPatch, store_id: str = STORE_ID, offer_id: str = Path(pattern=r"^[a-f0-9]{32}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    from app.services import offers
    try:
        o = offers.update(store_id, offer_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if not o:
        raise HTTPException(404, "offer not found")
    _audit(store_id, uid, "offer_changed", {"offer_id": offer_id, "fields": sorted(body.model_dump(exclude_unset=True))})
    return o.model_dump() | {"detail": offers.describe(store_id, o)}


@router.delete("/owner/{store_id}/offers/{offer_id}")
def delete_offer(store_id: str = STORE_ID, offer_id: str = Path(pattern=r"^[a-f0-9]{32}$"), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    from app.services import offers
    if not offers.delete(store_id, offer_id):
        raise HTTPException(404, "offer not found")
    _audit(store_id, uid, "offer_deleted", {"offer_id": offer_id})
    return {"deleted": True}


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


def _job_key(x_job_key: str | None) -> None:
    if not settings.job_key or not x_job_key or not hmac.compare_digest(x_job_key, settings.job_key):
        raise HTTPException(401, "job key required")


@router.post("/jobs/forecast")
def forecast_job(store_id: str | None = Query(default=None, pattern=r"^[a-z0-9-]{3,40}$"), x_job_key: str | None = Header(default=None)):
    """One store when given, otherwise every store (the nightly schedule)."""
    _job_key(x_job_key)
    from app.jobs import forecast as job
    if store_id:
        return job.run(store_id)
    return {"stores": [job.run(d.id) for d in db.client().collection("stores").select([]).stream()]}


@router.post("/jobs/customers")
def customers_job(x_job_key: str | None = Header(default=None)):
    _job_key(x_job_key)
    from app.jobs import customers as job
    return job.run()
