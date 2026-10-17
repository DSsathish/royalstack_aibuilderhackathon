"""Cart -> paid order. Sandbox payments only (mock, or Razorpay test mode when keys are set)."""

import hashlib
import hmac
import uuid

import httpx

from app.config import settings
from app.domain.models import Order, Session, now
from app.services import cart as cart_svc
from app.services import db, inventory, payments, qr


class CheckoutError(ValueError):
    pass


def _keys(store_id: str) -> tuple[str, str, str]:
    """(provider, key_id, key_secret) for a store: its own Razorpay keys, else the global ones, else mock."""
    cfg = (db.store_ref(store_id).get().to_dict() or {}).get("payments") or {}
    if cfg.get("provider") == "razorpay" and cfg.get("key_id"):
        secret = payments.secret_for(store_id)
        if secret:
            return "razorpay", cfg["key_id"], secret
    if settings.razorpay_key_id and settings.razorpay_key_secret:
        return "razorpay", settings.razorpay_key_id, settings.razorpay_key_secret
    return "mock", "", ""


def get(order_id: str) -> Order | None:
    doc = db.orders().document(order_id).get()
    return Order(**doc.to_dict()) if doc.exists else None


def intent(s: Session) -> Order:
    if s.mode not in ("instore", "online"):
        raise CheckoutError("this session mode cannot check out")
    c = cart_svc.get(s.store_id, s.cart_id)
    if not c.items or c.status != "open":
        raise CheckoutError("cart is empty")
    if s.mode == "instore":
        limit = db.store_ref(s.store_id).get().to_dict().get("self_checkout_item_limit", 15)
        if len(c.items) > limit:
            raise CheckoutError(f"self-checkout limit is {limit} items")
    subtotal, savings, total = cart_svc.totals(c)
    provider, key_id, key_secret = _keys(s.store_id)
    o = Order(order_id=uuid.uuid4().hex, store_id=s.store_id, session_id=s.session_id, cart_id=c.cart_id,
              channel="store" if s.mode == "instore" else "online", items=c.items,
              subtotal=subtotal, savings=savings, total=total, payment_provider=provider)
    if o.payment_provider == "razorpay":
        o.payment_ref = _razorpay_order(o, key_id, key_secret)
    db.orders().document(o.order_id).set(o.model_dump())
    return o


def _razorpay_order(o: Order, key_id: str, key_secret: str) -> str:
    res = httpx.post("https://api.razorpay.com/v1/orders",
                     auth=(key_id, key_secret),
                     json={"amount": int(round(o.total * 100)), "currency": "INR", "receipt": o.order_id},
                     timeout=10)
    res.raise_for_status()
    return res.json()["id"]


def razorpay_signature_ok(order_ref: str, payment_id: str, signature: str, key_secret: str | None = None) -> bool:
    secret = key_secret if key_secret is not None else settings.razorpay_key_secret
    expected = hmac.new(secret.encode(), f"{order_ref}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def confirm(order_id: str, *, payment_id: str, signature: str) -> Order:
    o = get(order_id)
    if not o:
        raise CheckoutError("order not found")
    if o.status != "pending":
        return o  # already paid: idempotent
    if o.payment_provider == "mock":
        ok = signature == "mock" and settings.env != "prod"
    else:
        ok = razorpay_signature_ok(o.payment_ref, payment_id, signature, _keys(o.store_id)[2])
    if not ok:
        raise CheckoutError("payment signature invalid")
    if cart_svc.get(o.store_id, o.cart_id).status != "open":
        raise CheckoutError("cart already checked out")

    for item in o.items:
        inventory.commit(o.store_id, item.product_id, item.qty)
    db.carts().document(o.cart_id).update({"status": "checked_out"})
    o.status, o.payment_id, o.paid_at = "paid", payment_id, now()
    o.receipt_token = qr.receipt_token(o.order_id, o.store_id, sum(i.qty for i in o.items))
    db.orders().document(o.order_id).set(o.model_dump())
    return o
