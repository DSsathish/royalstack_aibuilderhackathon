"""Exit kiosk endpoints (PIN-protected) and the owner's verification listing."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel, Field

from app.api.agent import _read_upload
from app.services import checkout, db, verification
from app.services.auth import STORE_ID, current_uid, require_owner

router = APIRouter(tags=["exit"])
HEX_ID = r"^[a-f0-9]{32}$"


def kiosk_auth(store_id: str = STORE_ID, x_kiosk_pin: str | None = Header(default=None)) -> str:
    store = db.store_ref(store_id).get()
    if not store.exists:
        raise HTTPException(404, "store not found")
    if not x_kiosk_pin or x_kiosk_pin != store.to_dict().get("kiosk_pin"):
        raise HTTPException(401, "kiosk PIN required")
    return store_id


def _token_from(text: str) -> str:
    """Accepts a raw receipt token or the full exit URL printed in the QR."""
    m = re.search(r"[?&]r=([A-Za-z0-9_\-]+\.[a-f0-9]{64})", text)
    return m.group(1) if m else text.strip()


def _with_summary(v) -> dict:
    out = v.model_dump()
    o = checkout.get(v.order_id) if v.order_id else None
    out["order_summary"] = {
        "items": [{"name": i.name, "qty": i.qty} for i in o.items], "total": o.total,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None} if o else None
    return out


@router.post("/exit/{store_id}/verify")
async def verify(store_id: str = Depends(kiosk_auth), receipt_token: str = Form(max_length=1024),
                 kiosk_id: str = Form(default="kiosk", max_length=40), counted_items: int | None = Form(default=None, ge=0, le=500),
                 image: UploadFile | None = File(default=None)):
    img = await _read_upload(image, "image")
    v = verification.verify_exit(store_id, _token_from(receipt_token), image=img, counted_items=counted_items, kiosk_id=kiosk_id)
    return _with_summary(v)


class ReviewIn(BaseModel):
    outcome: Literal["cleared", "issue_confirmed"]
    note: str = Field(default="", max_length=500)
    by: str = Field(default="staff", max_length=40)


@router.post("/exit/{store_id}/review/{verification_id}")
def review(body: ReviewIn, store_id: str = Depends(kiosk_auth), verification_id: str = Path(pattern=HEX_ID)):
    try:
        return verification.review(store_id, verification_id, outcome=body.outcome, by=body.by, note=body.note).model_dump()
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@router.get("/owner/{store_id}/verifications")
def owner_verifications(store_id: str = STORE_ID, days: int = Query(default=7, ge=1, le=90), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    return {"summary": verification.summary(store_id, days),
            "items": [v.model_dump() for v in verification.recent(store_id, days)[:200]]}
