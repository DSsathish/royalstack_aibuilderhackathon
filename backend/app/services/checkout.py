"""Cart -> paid order. Sandbox payments only (mock, or Razorpay test mode when keys are set)."""

import hashlib
import hmac
import uuid

import httpx

from app.config import settings
from app.domain.models import Order, Session, now
from app.services import cart as cart_svc
from app.services import db, inventory, qr


class CheckoutError(ValueError):
    pass


def _provider() -> str:
    return "razorpay" if settings.razorpay_key_id and settings.razorpay_key_secret else "mock"


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
    o = Order(order_id=uuid.uuid4().hex, store_id=s.store_id, session_id=s.session_id, cart_id=c.cart_id,
              channel="store" if s.mode == "instore" else "online", items=c.items,
              subtotal=subtotal, savings=savings, total=total, payment_provider=_provider())
    if o.payment_provider == "razorpay":
        o.payment_ref = _razorpay_order(o)
    db.orders().document(o.order_id).set(o.model_dump())
    return o


def _razorpay_order(o: Order) -> str:
    res = httpx.post("https://api.razorpay.com/v1/orders",
                     auth=(settings.razorpay_key_id, settings.razorpay_key_secret),
                     json={"amount": int(round(o.total * 100)), "currency": "INR", "receipt": o.order_id},
                     timeout=10)
    res.raise_for_status()
    return res.json()["id"]


def razorpay_signature_ok(order_ref: str, payment_id: str, signature: str) -> bool:
    expected = hmac.new(settings.razorpay_key_secret.encode(), f"{order_ref}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
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
        ok = razorpay_signature_ok(o.payment_ref, payment_id, signature)
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
