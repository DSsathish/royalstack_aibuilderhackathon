"""Reward points: an append-only ledger per customer and a balance kept in step inside transactions.

Credits (earn, adjust, release) carry `remaining` and an expiry; debits (redeem, negative adjust, expire)
consume the oldest unexpired credits first. Nothing sets a balance directly."""

import uuid
from datetime import timedelta

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.domain.models import now
from app.services import db

EARN_PER_RUPEES = 100      # one point per 100 rupees paid
MIN_REDEEM = 50            # one point is worth one rupee
EXPIRY_DAYS = 365
STALE_HOURS = 24           # a pending order older than this gives its points back


def ledger_ref(store_id: str, uid: str):
    return db.customers(store_id).document(uid).collection("ledger")


def balance(store_id: str, uid: str) -> int:
    doc = db.customers(store_id).document(uid).get()
    return int(doc.to_dict().get("points", 0)) if doc.exists else 0


def ledger(store_id: str, uid: str, limit: int = 50) -> list[dict]:
    docs = ledger_ref(store_id, uid).order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
    return [d.to_dict() for d in docs]


def _entry(kind: str, delta: int, *, reason: str = "", order_id: str = "", by: str = "", credit: bool = False) -> dict:
    return {"entry_id": uuid.uuid4().hex, "kind": kind, "delta": delta, "remaining": delta if credit else 0,
            "reason": reason, "order_id": order_id, "by": by,
            "expires_at": now() + timedelta(days=EXPIRY_DAYS) if credit else None, "created_at": now()}


def _credits(tx, cust) -> list:
    """Unexpired credits with points left, oldest first. Read inside the transaction."""
    t = now()
    snaps = [s for s in tx.get(cust.collection("ledger").where(filter=FieldFilter("remaining", ">", 0)))
             if not s.get("expires_at") or s.get("expires_at") > t]
    return sorted(snaps, key=lambda s: s.get("created_at"))


def _consume(tx, credits: list, pts: int) -> None:
    left = pts
    for s in credits:
        if left <= 0:
            break
        take = min(left, int(s.get("remaining")))
        tx.update(s.reference, {"remaining": int(s.get("remaining")) - take})
        left -= take


def _move(store_id: str, uid: str, delta: int, entry: dict) -> int:
    """Apply one ledger entry transactionally. Returns the new balance; ValueError if it would go below zero."""
    cust = db.customers(store_id).document(uid)

    @firestore.transactional
    def run(tx) -> int:
        snap = cust.get(transaction=tx)
        if not snap.exists:
            raise ValueError("no points account for this shopper")
        credits = _credits(tx, cust)
        available = sum(int(s.get("remaining")) for s in credits)
        if delta < 0:
            if available + delta < 0:
                raise ValueError("not enough points")
            _consume(tx, credits, -delta)
        tx.set(cust.collection("ledger").document(entry["entry_id"]), entry)
        tx.update(cust, {"points": available + delta})      # absolute: self-heals if expiry has not run yet
        return available + delta

    return run(db.client().transaction())


def earn(store_id: str, uid: str, amount_paid: float, order_id: str) -> int:
    pts = int(amount_paid // EARN_PER_RUPEES)
    if pts <= 0:
        return 0
    try:
        _move(store_id, uid, pts, _entry("earn", pts, order_id=order_id, credit=True))
    except ValueError:
        return 0          # account deleted after linking
    return pts


def redeem(store_id: str, uid: str, pts: int, order_id: str) -> None:
    if pts < MIN_REDEEM:
        raise ValueError(f"redeem at least {MIN_REDEEM} points")
    _move(store_id, uid, -pts, _entry("redeem", -pts, order_id=order_id))


def release(store_id: str, uid: str, order_id: str) -> int:
    """Give back the points an unpaid order holds. Safe to call twice."""
    entries = [d.to_dict() for d in ledger_ref(store_id, uid).where(filter=FieldFilter("order_id", "==", order_id)).stream()]
    held = next((-e["delta"] for e in entries if e["kind"] == "redeem"), 0)
    if not held or any(e["kind"] == "release" for e in entries):
        return 0
    _move(store_id, uid, held, _entry("release", held, order_id=order_id, credit=True))
    return held


def adjust(store_id: str, uid: str, delta: int, reason: str, *, by: str) -> int:
    """Owner correction, up or down, never below zero. Returns the new balance."""
    if delta == 0 or not reason.strip():
        raise ValueError("a non-zero delta and a reason are required")
    return _move(store_id, uid, delta, _entry("adjust", delta, reason=reason.strip(), by=by, credit=delta > 0))


def expire(store_id: str) -> int:
    """Nightly: zero out credits past their expiry and lower balances. Returns points expired."""
    total, t = 0, now()
    for cdoc in db.customers(store_id).stream():
        cust = cdoc.reference
        expired = [s for s in cust.collection("ledger").where(filter=FieldFilter("remaining", ">", 0)).stream()
                   if s.get("expires_at") and s.get("expires_at") < t]
        if not expired:
            continue
        pts = sum(int(s.get("remaining")) for s in expired)
        batch = db.client().batch()
        for s in expired:
            batch.update(s.reference, {"remaining": 0})
        e = _entry("expire", -pts)
        batch.set(cust.collection("ledger").document(e["entry_id"]), e)
        batch.update(cust, {"points": firestore.Increment(-pts)})
        batch.commit()
        total += pts
    return total


def release_stale(store_id: str) -> int:
    """Nightly: pending orders older than STALE_HOURS that hold points are cancelled and refunded."""
    cutoff, n = now() - timedelta(hours=STALE_HOURS), 0
    for d in db.orders().where(filter=FieldFilter("store_id", "==", store_id)).stream():
        o = d.to_dict()
        if o.get("status") == "pending" and o.get("points_redeemed", 0) > 0 and o.get("customer_id") and o["created_at"] < cutoff:
            release(store_id, o["customer_id"], o["order_id"])
            d.reference.update({"status": "cancelled"})
            n += 1
    return n
