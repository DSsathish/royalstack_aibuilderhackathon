"""Firestore client and collection paths. No other module spells a path."""

from functools import lru_cache

from google.cloud import firestore

from app.config import settings


@lru_cache(maxsize=1)
def client() -> firestore.Client:
    # Honours FIRESTORE_EMULATOR_HOST automatically.
    return firestore.Client(project=settings.google_cloud_project)


def store_ref(store_id: str) -> firestore.DocumentReference:
    return client().collection("stores").document(store_id)


def products(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("products")


def locations(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("locations")


def inventory(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("inventory")


def suppliers(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("suppliers")


def demand_signals(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("demand_signals")


def audit(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("audit")


def users() -> firestore.CollectionReference:
    return client().collection("users")


def sessions() -> firestore.CollectionReference:
    return client().collection("sessions")


def carts() -> firestore.CollectionReference:
    return client().collection("carts")


def orders() -> firestore.CollectionReference:
    return client().collection("orders")


def verifications() -> firestore.CollectionReference:
    return client().collection("verifications")


def forecasts(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("forecasts")


def po_drafts(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("po_drafts")


def counts(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("counts")


def batched(refs: list, op, size: int = 400) -> None:
    """Firestore batches hold 500 writes; apply op(batch, ref) in chunks."""
    for i in range(0, len(refs), size):
        batch = client().batch()
        for ref in refs[i:i + size]:
            op(batch, ref)
        batch.commit()


def customers(store_id: str) -> firestore.CollectionReference:
    """Per-store customer records: stores/{store_id}/customers/{uid}."""
    return store_ref(store_id).collection("customers")


def people() -> firestore.CollectionReference:
    """One doc per signed-in shopper listing the stores they linked: people/{uid}."""
    return client().collection("people")


def offers(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("offers")


def sync_log(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("sync_log")


def sync_outbox(store_id: str) -> firestore.CollectionReference:
    return store_ref(store_id).collection("sync_outbox")


def sync_events(store_id: str) -> firestore.CollectionReference:
    """Processed inbound event ids, for idempotency."""
    return store_ref(store_id).collection("sync_events")
