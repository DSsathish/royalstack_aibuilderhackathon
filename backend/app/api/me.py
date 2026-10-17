"""Signed-in shopper: link a session, profile, history, export, delete."""

from app.domain import languages
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.services import customers, points, sessions
from app.services.auth import current_uid, require_phone

router = APIRouter(tags=["me"])
HEX = r"^[a-f0-9]{32}$"


@router.post("/sessions/{session_id}/link")
def link(session_id: str = Path(pattern=HEX), uid: str = Depends(current_uid)):
    phone = require_phone(uid)
    s = sessions.get(session_id)
    if not s or s.mode == "owner":
        raise HTTPException(404, "session not found")
    c = customers.link(s, uid, phone)
    return {"customer_id": uid, "store_id": s.store_id, "name": c.name, "visits": c.visits}


@router.delete("/sessions/{session_id}/link")
def unlink(session_id: str = Path(pattern=HEX)):
    """Sign out on this device. The session id is the credential, as for the cart."""
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "session not found")
    customers.unlink(s)
    return {"customer_id": None}


@router.get("/me/profile")
def profile(store_id: str = Query(pattern=r"^[a-z0-9-]{3,40}$"), uid: str = Depends(current_uid)):
    require_phone(uid)
    c = customers.get(store_id, uid)
    if not c:
        raise HTTPException(404, "no profile for this store")
    return c.model_dump()


class ProfilePatch(BaseModel):
    store_id: str = Field(pattern=r"^[a-z0-9-]{3,40}$")
    name: str | None = Field(default=None, max_length=60)
    language: str | None = Field(default=None, pattern=languages.CODE_PATTERN)
    dietary: list[str] | None = Field(default=None, max_length=8)
    favourite_categories: list[str] | None = Field(default=None, max_length=12)
    substitution: str | None = Field(default=None, pattern=r"^(ask|same_brand|any)$")


@router.patch("/me/profile")
def patch_profile(body: ProfilePatch, uid: str = Depends(current_uid)):
    require_phone(uid)
    fields = body.model_dump(exclude={"store_id"})
    for key in ("dietary", "favourite_categories"):
        if fields.get(key) is not None:
            if any(len(x) > 32 for x in fields[key]):
                raise HTTPException(422, f"{key} entries must be 32 characters or fewer")
            fields[key] = [x.strip()[:32] for x in fields[key] if x.strip()]
    c = customers.patch(body.store_id, uid, fields)
    if not c:
        raise HTTPException(404, "no profile for this store")
    return c.model_dump()


@router.get("/me/orders")
def my_orders(store_id: str = Query(pattern=r"^[a-z0-9-]{3,40}$"), uid: str = Depends(current_uid)):
    require_phone(uid)
    return [o.model_dump() for o in customers.orders_for(store_id, uid)]


@router.get("/me/export")
def export(uid: str = Depends(current_uid)):
    require_phone(uid)
    return customers.export(uid)


@router.delete("/me")
def delete_me(uid: str = Depends(current_uid)):
    require_phone(uid)
    return customers.delete(uid)


@router.get("/me/points")
def my_points(store_id: str = Query(pattern=r"^[a-z0-9-]{3,40}$"), uid: str = Depends(current_uid)):
    require_phone(uid)
    if not customers.get(store_id, uid):
        raise HTTPException(404, "no profile for this store")
    return {"balance": points.balance(store_id, uid), "min_redeem": points.MIN_REDEEM, "entries": points.ledger(store_id, uid)}
