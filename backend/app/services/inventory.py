"""Transactional stock changes. The only writer of on_hand and reserved."""

from google.cloud import firestore

from app.services import db


def available(store_id: str, product_id: str) -> int:
    doc = db.inventory(store_id).document(product_id).get()
    if not doc.exists:
        return 0
    d = doc.to_dict()
    return max(0, d["on_hand"] - d.get("reserved", 0))


def reserve(store_id: str, product_id: str, qty: int) -> bool:
    ref = db.inventory(store_id).document(product_id)

    @firestore.transactional
    def run(tx: firestore.Transaction) -> bool:
        snap = ref.get(transaction=tx)
        if not snap.exists:
            return False
        d = snap.to_dict()
        if d["on_hand"] - d.get("reserved", 0) < qty:
            return False
        tx.update(ref, {"reserved": d.get("reserved", 0) + qty})
        return True

    return run(db.client().transaction())


def release(store_id: str, product_id: str, qty: int) -> None:
    ref = db.inventory(store_id).document(product_id)

    @firestore.transactional
    def run(tx: firestore.Transaction) -> None:
        snap = ref.get(transaction=tx)
        if snap.exists:
            tx.update(ref, {"reserved": max(0, snap.to_dict().get("reserved", 0) - qty)})

    run(db.client().transaction())


def commit(store_id: str, product_id: str, qty: int) -> None:
    ref = db.inventory(store_id).document(product_id)

    @firestore.transactional
    def run(tx: firestore.Transaction) -> None:
        snap = ref.get(transaction=tx)
        if snap.exists:
            d = snap.to_dict()
            tx.update(ref, {
                "on_hand": max(0, d["on_hand"] - qty),
                "reserved": max(0, d.get("reserved", 0) - qty),
            })

    run(db.client().transaction())
