"""Signed-in shoppers: per-store customer records, order history, export and deletion."""

import uuid
from collections import Counter

from google.api_core.exceptions import NotFound
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from app.domain.models import Customer, Order, Session, now
from app.services import conversation, db, segments

PROFILE_FIELDS = ("name", "language", "dietary", "favourite_categories", "usual_items", "substitution")


def unlink(s: Session) -> None:
    """Sign out on this device: later purchases in the visit are anonymous again."""
    db.sessions().document(s.session_id).update({"customer_id": None})


def link(s: Session, uid: str, phone: str) -> Customer:
    """Attach a signed-in shopper to a session; create the store's customer record on first visit."""
    ref = db.customers(s.store_id).document(uid)
    doc = ref.get()
    if doc.exists:
        c = Customer(**doc.to_dict())
        ref.update({"last_seen": now()})
    else:
        c = Customer(uid=uid, store_id=s.store_id, phone_last4=phone[-4:])
        ref.set(c.model_dump())
    db.people().document(uid).set({"stores": firestore.ArrayUnion([s.store_id]), "updated_at": now()}, merge=True)
    db.sessions().document(s.session_id).update({"customer_id": uid})
    return c


def get(store_id: str, uid: str) -> Customer | None:
    doc = db.customers(store_id).document(uid).get()
    return Customer(**doc.to_dict()) if doc.exists else None


def patch(store_id: str, uid: str, fields: dict) -> Customer | None:
    ref = db.customers(store_id).document(uid)
    if not ref.get().exists:
        return None
    ref.update({k: v for k, v in fields.items() if k in PROFILE_FIELDS and v is not None})
    return Customer(**ref.get().to_dict())


def record_order(o: Order) -> None:
    """Called once per paid order: visits, spend, last seen and the refreshed usual-items list."""
    if not o.customer_id:
        return
    c = get(o.store_id, o.customer_id)
    if not c:
        return      # account deleted after the session was linked; the sale stays anonymous
    after = c.model_copy(update={"visits": c.visits + 1, "spend": c.spend + o.total, "last_seen": now()})
    try:
        db.customers(o.store_id).document(o.customer_id).update({
            "visits": firestore.Increment(1), "spend": firestore.Increment(o.total), "last_seen": now(),
            "usual_items": _usual_items(o.store_id, o.customer_id), "segment": segments.classify(after)})
    except NotFound:
        pass


def segment_of(store_id: str, uid: str | None) -> str:
    """The shopper's stored segment; guests and unknown ids are "guest"."""
    if not uid:
        return "guest"
    c = get(store_id, uid)
    return c.segment if c else "guest"


def _usual_items(store_id: str, uid: str) -> list[str]:
    """Products bought in at least two of the last 20 orders, most frequent first."""
    counts: Counter[str] = Counter()
    for o in orders_for(store_id, uid, limit=20):
        counts.update({i.product_id for i in o.items})
    return [pid for pid, n in counts.most_common(10) if n >= 2]


def orders_for(store_id: str, uid: str, limit: int = 50) -> list[Order]:
    docs = db.orders().where(filter=FieldFilter("customer_id", "==", uid)).stream()
    orders = [Order(**d.to_dict()) for d in docs if d.to_dict().get("store_id") == store_id and d.to_dict().get("status") in ("paid", "verified", "flagged")]
    return sorted(orders, key=lambda o: o.created_at, reverse=True)[:limit]


def stores_for(uid: str) -> list[str]:
    doc = db.people().document(uid).get()
    return doc.to_dict().get("stores", []) if doc.exists else []


def export(uid: str) -> dict:
    profiles = [c.model_dump() for sid in stores_for(uid) if (c := get(sid, uid))]
    orders = [Order(**d.to_dict()).model_dump() for d in db.orders().where(filter=FieldFilter("customer_id", "==", uid)).stream()]
    turns = [d.to_dict() | {"store_id": sid} for sid in stores_for(uid)
             for d in conversation.turns_ref(conversation.shopper_key(uid, sid)).order_by("at").stream()]
    return {"uid": uid, "profiles": profiles, "orders": orders, "turns": turns}


def delete(uid: str) -> dict:
    """Remove the person: profiles, conversation turns and the index. Orders and sessions are anonymised, not deleted."""
    stores = stores_for(uid)
    to_delete = [db.people().document(uid)]
    for sid in stores:
        cust = db.customers(sid).document(uid)
        to_delete += [d.reference for d in cust.collection("ledger").stream()]       # subcollections do not go with the parent
        to_delete += [d.reference for d in conversation.turns_ref(conversation.shopper_key(uid, sid)).stream()]
        to_delete.append(cust)
        db.audit(sid).document(uuid.uuid4().hex).set({"actor": uid, "action": "customer_deleted", "created_at": now(), "payload": {}})
    by_uid = FieldFilter("customer_id", "==", uid)
    orders = [d.reference for d in db.orders().where(filter=by_uid).stream()]
    open_sessions = [d.reference for d in db.sessions().where(filter=by_uid).stream()]
    db.batched(orders + open_sessions, lambda b, ref: b.update(ref, {"customer_id": None}))
    db.batched(to_delete, lambda b, ref: b.delete(ref))
    return {"deleted": True, "stores": stores, "orders_anonymised": len(orders)}
