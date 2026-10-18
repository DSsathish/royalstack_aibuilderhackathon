"""Shopper endpoints: in-store entry, cart, checkout, orders, and the owner's QR sheet."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Path

from app.api.agent import limit_sessions
from pydantic import BaseModel, Field

from app.config import settings
from app.domain.models import Order, Session
from app.services import cart as cart_svc
from app.services import checkout, customers, db, offers, points, qr, sessions
from app.services.auth import STORE_ID, current_uid, require_owner, require_recent_phone

router = APIRouter(tags=["shop"])
HEX_ID = r"^[a-f0-9]{32}$"


# --- sessions ---------------------------------------------------------------

class EnterIn(BaseModel):
    store_id: str = Field(pattern=r"^[a-z0-9-]{3,40}$")
    token: str = Field(max_length=512)
    aisle: str | None = Field(default=None, max_length=8)


@router.post("/sessions/instore", response_model=Session, dependencies=[Depends(limit_sessions)])
def enter_store(body: EnterIn):
    payload = qr.verify(body.token)
    if not payload or payload.get("kind") != "entrance" or payload.get("store_id") != body.store_id:
        raise HTTPException(401, "invalid entrance code")
    if not db.store_ref(body.store_id).get().exists:
        raise HTTPException(404, "store not found")
    s = sessions.create(body.store_id, "instore")
    if body.aisle:
        db.sessions().document(s.session_id).update({"aisle_hint": body.aisle})
        s.aisle_hint = body.aisle
    return s


class SessionPatch(BaseModel):
    aisle_hint: str | None = Field(default=None, max_length=8)


@router.patch("/sessions/{session_id}", response_model=Session)
def patch_session(session_id: str = Path(pattern=HEX_ID), body: SessionPatch = ...):
    s = _session_or_404(session_id)
    db.sessions().document(s.session_id).update({"aisle_hint": body.aisle_hint})
    s.aisle_hint = body.aisle_hint
    return s


def _session_or_404(session_id: str) -> Session:
    s = sessions.get(session_id)
    if not s:
        raise HTTPException(404, "session not found or expired")
    return s


def session_header(x_session_id: str | None = Header(default=None)) -> Session:
    if not x_session_id:
        raise HTTPException(401, "X-Session-Id header required")
    if not re.fullmatch(HEX_ID, x_session_id):
        raise HTTPException(422, "malformed X-Session-Id")
    return _session_or_404(x_session_id)


# --- cart -------------------------------------------------------------------

class CartItemIn(BaseModel):
    product_id: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    qty: int = Field(ge=1, le=50)
    via: Literal["scan", "vision", "chat"] = "scan"


def _cart_view(c, s: Session) -> dict:
    segment = customers.segment_of(s.store_id, s.customer_id)
    p = cart_svc.pricing(s.store_id, c, segment)
    return {**c.model_dump(), "count": sum(i.qty for i in c.items), **p.model_dump(), "segment": segment,
            "points_balance": points.balance(s.store_id, s.customer_id) if s.customer_id else None}


def _own_cart(cart_id: str, s: Session) -> None:
    if s.cart_id != cart_id:
        raise HTTPException(403, "cart does not belong to this session")


@router.get("/carts/{cart_id}")
def get_cart(cart_id: str = Path(pattern=HEX_ID), s: Session = Depends(session_header)):
    _own_cart(cart_id, s)
    return _cart_view(cart_svc.get(s.store_id, cart_id), s)


@router.post("/carts/{cart_id}/items")
def add_item(body: CartItemIn, cart_id: str = Path(pattern=HEX_ID), s: Session = Depends(session_header)):
    _own_cart(cart_id, s)
    if s.mode == "instore" and body.via == "chat":
        raise HTTPException(409, "scan_required")       # in store, only a scan or a confirmed photo adds an item
    res = cart_svc.add(s.store_id, cart_id, body.product_id, body.qty, via=body.via, mode=s.mode)
    if isinstance(res, str):
        raise HTTPException(409, res)
    return _cart_view(res, s)


class QtyIn(BaseModel):
    qty: int = Field(ge=0, le=99)


@router.patch("/carts/{cart_id}/items/{product_id}")
def set_item_qty(body: QtyIn, cart_id: str = Path(pattern=HEX_ID), product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$"), s: Session = Depends(session_header)):
    """The cart's quantity stepper: zero removes the line. In store the stepper only reduces, since adding needs a scan."""
    _own_cart(cart_id, s)
    line = next((i for i in cart_svc.get(s.store_id, cart_id).items if i.product_id == product_id), None)
    if line is None:
        raise HTTPException(404, "not in the cart")
    if s.mode == "instore" and body.qty > line.qty:
        raise HTTPException(409, "scan_required")
    cart = cart_svc.remove(s.store_id, cart_id, product_id)
    if body.qty > 0:
        res = cart_svc.add(s.store_id, cart_id, product_id, body.qty, via=line.via, mode=s.mode)
        if isinstance(res, str):
            raise HTTPException(409, res)
        cart = res
    return _cart_view(cart, s)


@router.delete("/carts/{cart_id}/items/{product_id}")
def remove_item(cart_id: str = Path(pattern=HEX_ID), product_id: str = Path(pattern=r"^[a-z0-9-]{3,80}$"), s: Session = Depends(session_header)):
    _own_cart(cart_id, s)
    return _cart_view(cart_svc.remove(s.store_id, cart_id, product_id), s)


# --- checkout and orders ----------------------------------------------------

@router.get("/stores/{store_id}/offers")
def store_offers(store_id: str = STORE_ID, x_session_id: str | None = Header(default=None)):
    """Offers for this shopper: store-wide ones, plus segment offers when the session is linked to a signed-in shopper."""
    segment = "guest"
    if x_session_id and re.fullmatch(HEX_ID, x_session_id):
        s = sessions.get(x_session_id)
        if s and s.store_id == store_id:
            segment = customers.segment_of(store_id, s.customer_id)
    return [offers.public(store_id, o) for o in offers.applicable(store_id, segment)]


class IntentIn(BaseModel):
    session_id: str = Field(pattern=HEX_ID)
    points: int = Field(default=0, ge=0, le=100_000)


@router.post("/checkout/intent")
def checkout_intent(body: IntentIn, authorization: str | None = Header(default=None), x_test_uid: str | None = Header(default=None)):
    s = _session_or_404(body.session_id)
    if body.points:                                   # spending points needs a fresh phone verification by the linked shopper
        uid = current_uid(authorization, x_test_uid)
        require_recent_phone(uid)
        if uid != s.customer_id:
            raise HTTPException(403, "points belong to a different shopper")
    try:
        o = checkout.intent(s, points=body.points)
    except checkout.CheckoutError as exc:
        raise HTTPException(409, str(exc))
    out = {"order_id": o.order_id, "amount": o.total, "currency": "INR", "provider": o.payment_provider,
           "discount_total": o.discount_total, "points_redeemed": o.points_redeemed}
    if o.payment_provider == "razorpay":
        out |= {"razorpay_key_id": settings.razorpay_key_id, "razorpay_order_id": o.payment_ref}
    return out


class ConfirmIn(BaseModel):
    order_id: str = Field(pattern=HEX_ID)
    payment_id: str = Field(max_length=128)
    signature: str = Field(max_length=256)
    session_id: str = Field(pattern=HEX_ID)


@router.post("/checkout/confirm", response_model=Order)
def checkout_confirm(body: ConfirmIn):
    s = _session_or_404(body.session_id)
    o = checkout.get(body.order_id)
    if not o:
        raise HTTPException(404, "order not found")
    if o.session_id != s.session_id:
        raise HTTPException(403, "order does not belong to this session")
    try:
        return checkout.confirm(o.order_id, payment_id=body.payment_id, signature=body.signature)
    except checkout.CheckoutError as exc:
        raise HTTPException(402, str(exc))


@router.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str = Path(pattern=HEX_ID), s: Session = Depends(session_header)):
    o = checkout.get(order_id)
    mine = o and (o.session_id == s.session_id or (s.customer_id is not None and o.customer_id == s.customer_id))
    if not mine:
        raise HTTPException(404, "order not found")      # the visit that paid, or a later visit by the same signed-in shopper
    return o


# --- owner: printable QR sheet ----------------------------------------------

@router.get("/owner/{store_id}/qr")
def owner_qr(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    store = db.store_ref(store_id).get()
    if not store.exists:
        raise HTTPException(404, "store not found")
    base = f"{settings.app_base_url}/enter/?store={store_id}&t={qr.entrance_token(store_id)}"
    aisles = [a["aisle"] for a in store.to_dict().get("floor_map", [])]
    return {"entrance_url": base, "aisles": [{"aisle": a, "url": f"{base}&aisle={a}"} for a in aisles]}
