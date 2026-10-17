"""Cart -> paid order. Sandbox payments only (mock, or Razorpay test mode when keys are set)."""

import hashlib
import hmac
import uuid

import httpx

from app.config import settings
from app.domain.models import Order, Session, now
from app.services import cart as cart_svc
from app.services import customers, db, inventory, payments, qr, sync
from app.services import points as points_svc


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


def intent(s: Session, points: int = 0) -> Order:
    if s.mode not in ("instore", "online"):
        raise CheckoutError("this session mode cannot check out")
    c = cart_svc.get(s.store_id, s.cart_id)
    if not c.items or c.status != "open":
        raise CheckoutError("cart is empty")
    if s.mode == "instore":
        limit = db.store_ref(s.store_id).get().to_dict().get("self_checkout_item_limit", 15)
        if len(c.items) > limit:
            raise CheckoutError(f"self-checkout limit is {limit} items")
    _release_held_points(c.cart_id)
    if points:
        if not s.customer_id:
            raise CheckoutError("sign in to use points")
        if points < points_svc.MIN_REDEEM:
            raise CheckoutError(f"redeem at least {points_svc.MIN_REDEEM} points")
        if points > points_svc.balance(s.store_id, s.customer_id):
            raise CheckoutError("not enough points")
    p = cart_svc.pricing(s.store_id, c, customers.segment_of(s.store_id, s.customer_id), points)
    provider, key_id, key_secret = _keys(s.store_id)
    o = Order(order_id=uuid.uuid4().hex, store_id=s.store_id, session_id=s.session_id, cart_id=c.cart_id,
              channel="store" if s.mode == "instore" else "online", items=c.items,
              subtotal=p.subtotal, savings=p.savings, discounts=p.discounts, discount_total=p.discount_total,
              points_redeemed=p.points_redeemed, points_value=p.points_value, total=p.total,
              payment_provider="mock" if p.total <= 0 else provider, customer_id=s.customer_id)
    if p.points_redeemed:
        try:
            points_svc.redeem(s.store_id, s.customer_id, p.points_redeemed, o.order_id)     # held until paid or released
        except ValueError as exc:
            raise CheckoutError(str(exc))
    if o.payment_provider == "razorpay":
        o.payment_ref = _razorpay_order(o, key_id, key_secret)
    db.orders().document(o.order_id).set(o.model_dump())
    return o


def _claim(order_id: str, payment_id: str):
    """Flip pending -> paid inside a transaction. Returns paid_at for the winner, None when it was no longer pending."""
    from google.cloud import firestore
    ref = db.orders().document(order_id)

    @firestore.transactional
    def run(tx):
        snap = ref.get(transaction=tx)
        if not snap.exists or snap.to_dict().get("status") != "pending":
            return None
        t = now()
        tx.update(ref, {"status": "paid", "payment_id": payment_id, "paid_at": t})
        return t

    return run(db.client().transaction())


def _release_held_points(cart_id: str) -> None:
    """A retry on the same cart cancels earlier pending orders that hold points and gives the points back."""
    from google.cloud.firestore_v1 import FieldFilter
    for d in db.orders().where(filter=FieldFilter("cart_id", "==", cart_id)).stream():
        o = d.to_dict()
        if o.get("status") == "pending" and o.get("points_redeemed", 0) > 0 and o.get("customer_id"):
            points_svc.release(o["store_id"], o["customer_id"], o["order_id"])
            d.reference.update({"status": "cancelled"})


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
    if o.status == "cancelled":
        raise CheckoutError("order was cancelled, start checkout again")
    if o.status != "pending":
        return o  # already paid: idempotent
    if o.payment_provider == "mock":
        ok = signature == "mock" and (settings.env != "prod" or o.total <= 0)    # free orders (all points) settle anywhere
    else:
        ok = razorpay_signature_ok(o.payment_ref, payment_id, signature, _keys(o.store_id)[2])
    if not ok:
        raise CheckoutError("payment signature invalid")
    if cart_svc.get(o.store_id, o.cart_id).status != "open":
        raise CheckoutError("cart already checked out")
    paid_at = _claim(o.order_id, payment_id)
    if paid_at is None:
        return get(order_id) or o        # a concurrent confirm won; its side effects happen exactly once

    for item in o.items:
        inventory.commit(o.store_id, item.product_id, item.qty)
    db.carts().document(o.cart_id).update({"status": "checked_out"})
    o.status, o.payment_id, o.paid_at = "paid", payment_id, paid_at
    o.receipt_token = qr.receipt_token(o.order_id, o.store_id, sum(i.qty for i in o.items))
    if o.customer_id:
        o.points_earned = points_svc.earn(o.store_id, o.customer_id, o.total, o.order_id)
    db.orders().document(o.order_id).set(o.model_dump())
    customers.record_order(o)
    sync.notify_sale_async(o)
    return o
