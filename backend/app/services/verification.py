"""Layered exit verification. Deterministic layers decide; vision adjusts; flags go to staff."""

import hashlib
import random
import uuid
from datetime import timedelta

from google.cloud.firestore_v1 import FieldFilter

from app.domain.models import Layers, Verification, now
from app.services import catalog, checkout, db, qr, vision


def random_audit(store_id: str) -> bool:
    rate = db.store_ref(store_id).get().to_dict().get("audit_rate", 0.1)
    return random.random() < rate


def verify_exit(store_id: str, receipt_token: str, *, image: tuple[bytes, str] | None,
                counted_items: int | None, kiosk_id: str) -> Verification:
    v = Verification(verification_id=uuid.uuid4().hex, store_id=store_id, kiosk_id=kiosk_id, verdict="clear")
    flags, spots = [], []
    store = db.store_ref(store_id).get().to_dict() or {}

    # 1. receipt token
    payload = qr.verify(receipt_token)
    order = None
    if payload and payload.get("kind") == "receipt" and payload.get("store_id") == store_id:
        v.layers.receipt_ok = True
        v.order_id = payload["order_id"]
        order = checkout.get(v.order_id)
    else:
        flags.append("invalid receipt")

    # 2. order state
    if order and order.status == "paid":
        v.layers.order_ok = True
    elif order and order.status in ("verified", "flagged"):
        flags.append("receipt already used at the exit")
    elif order:
        flags.append("order not paid")

    if order:
        qty = sum(i.qty for i in order.items)
        # 3. item count
        if counted_items is not None:
            tolerance = 1 if qty <= 10 else max(1, round(qty * 0.1))
            v.layers.count_ok = abs(counted_items - qty) <= tolerance
            if not v.layers.count_ok:
                flags.append(f"item count mismatch: receipt {qty}, counted {counted_items}")
        # 4. self-checkout limit
        v.layers.limit_ok = len(order.items) <= store.get("self_checkout_item_limit", 15)
        if not v.layers.limit_ok:
            flags.append("over self-checkout item limit")
        # 5. high-value items
        for item in order.items:
            p = catalog.get_product(store_id, item.product_id)
            if p and p.is_high_value:
                v.layers.high_value.append(item.product_id)
                spots.append(f"show {item.name} to staff")
        # 6. random audit
        if random_audit(store_id):
            v.layers.random_audit = True
            spots.append("random audit")
        # 7. vision
        if image:
            v.image_hash = hashlib.sha256(image[0]).hexdigest()
            v.vision = vision.check_bag(image[0], image[1], [f"{i.name} x{i.qty}" for i in order.items])
            if not v.vision.skipped:
                if v.vision.unexpected_items:
                    flags.append("items not on receipt: " + ", ".join(v.vision.unexpected_items))
                elif v.vision.confidence < 0.5:
                    flags.append("bag does not match receipt (low confidence)")

    v.reasons = flags + spots
    v.verdict = "flag" if flags else "spot_check" if spots else "clear"
    db.verifications().document(v.verification_id).set(v.model_dump())
    if order and v.layers.order_ok:
        db.orders().document(order.order_id).update({
            "status": "flagged" if v.verdict == "flag" else "verified", "exited_at": now()})
    return v


def get(store_id: str, verification_id: str) -> Verification | None:
    doc = db.verifications().document(verification_id).get()
    if not doc.exists or doc.to_dict()["store_id"] != store_id:
        return None
    return Verification(**doc.to_dict())


def review(store_id: str, verification_id: str, *, outcome: str, by: str, note: str) -> Verification:
    v = get(store_id, verification_id)
    if not v:
        raise ValueError("verification not found")
    v.review_outcome, v.reviewed_by, v.review_note = outcome, by, note[:500]
    db.verifications().document(v.verification_id).set(v.model_dump())
    if v.order_id and v.layers.order_ok:
        db.orders().document(v.order_id).update({"status": "flagged" if outcome == "issue_confirmed" else "verified"})
    return v


def recent(store_id: str, days: int) -> list[Verification]:
    since = now() - timedelta(days=days)
    docs = (db.verifications().where(filter=FieldFilter("store_id", "==", store_id))
            .where(filter=FieldFilter("created_at", ">=", since)).stream())
    return sorted((Verification(**d.to_dict()) for d in docs), key=lambda x: x.created_at, reverse=True)


def summary(store_id: str, days: int) -> dict:
    items = recent(store_id, days)
    total = len(items)
    counts = {k: sum(1 for i in items if i.verdict == k) for k in ("clear", "spot_check", "flag")}
    confirmed = sum(1 for i in items if i.review_outcome == "issue_confirmed")
    return {"total": total, **counts, "issue_confirmed": confirmed,
            "flag_rate": round(counts["flag"] / total, 3) if total else 0.0,
            "audit_rate": round(sum(1 for i in items if i.layers.random_audit) / total, 3) if total else 0.0}
