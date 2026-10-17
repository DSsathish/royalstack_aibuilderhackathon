"""Self-service: register a shop, set it up, manage staff and payment keys."""

import re
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path
from google.cloud import firestore
from pydantic import BaseModel, Field

from app.api.agent import limit_sessions
from app.domain.models import Aisle, Brand, Payments, Store, now
from app.services import catalog, db, payments
from app.services.auth import STORE_ID, current_uid, require_owner, verified_email

router = APIRouter(tags=["register"])
PUBLIC_STORE_EXCLUDE = {"kiosk_pin", "audit_rate", "owner_emails", "staff_emails"}


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug if len(slug) >= 3 else slug + "-shop"


def floor_map(aisles: list[str]) -> list[Aisle]:
    """Aisles laid out left to right across the standard 1000x600 floor."""
    n = max(1, len(aisles))
    width = min(90, int(820 / n) - 20)
    return [Aisle(aisle=a, x=80 + i * (width + 20 if n > 1 else 0) + (0 if n > 1 else 0), y=80, w=width, h=420) for i, a in enumerate(aisles)]


class RegisterIn(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    city: str = Field(default="", max_length=60)
    languages: list[str] = Field(default=["en"], max_length=5)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")


@router.post("/owner/register", dependencies=[Depends(limit_sessions)])
def register(body: RegisterIn, uid: str = Depends(current_uid)):
    email = verified_email(uid)
    base = slugify(body.name)
    client = db.client()

    @firestore.transactional
    def create(tx: firestore.Transaction) -> Store:
        for i in range(1, 50):
            sid = base if i == 1 else f"{base}-{i}"
            if not client.collection("stores").document(sid).get(transaction=tx).exists:
                break
        else:
            raise HTTPException(409, "could not allocate a store id")
        store = Store(store_id=sid, name=body.name.strip(), city=body.city.strip(), languages=body.languages or ["en"], currency=body.currency,
                      kiosk_pin=f"{secrets.randbelow(10**6):06d}", owner_emails=[email],
                      floor_map=floor_map(["A1", "A2", "A3", "A4"]), brand=Brand(greeting=f"Welcome to {body.name.strip()}!"))
        tx.set(client.collection("stores").document(sid), store.model_dump())
        return store

    store = create(client.transaction())
    user_ref = db.users().document(uid)
    user_ref.set({"email": email}, merge=True)
    user_ref.update({"stores": firestore.ArrayUnion([store.store_id]), f"roles.{store.store_id}": "owner"})
    db.audit(store.store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "store_registered", "created_at": now(), "payload": {"name": store.name}})
    return {"store": store.model_dump(exclude={"kiosk_pin"}), "kiosk_pin": store.kiosk_pin}


class StorePatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=60)
    city: str | None = Field(default=None, max_length=60)
    tagline: str | None = Field(default=None, max_length=80)
    greeting: str | None = Field(default=None, max_length=160)
    accent: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    languages: list[str] | None = Field(default=None, max_length=5)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    aisles: list[str] | None = Field(default=None, min_length=1, max_length=12)


@router.patch("/owner/{store_id}/store", response_model=Store, response_model_exclude=PUBLIC_STORE_EXCLUDE)
def patch_store(body: StorePatch, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    ref = db.store_ref(store_id)
    cur = ref.get().to_dict()
    changes = {}
    for k in ("name", "city", "languages", "currency"):
        if getattr(body, k) is not None:
            changes[k] = getattr(body, k)
    brand = dict(cur.get("brand") or {})
    for k in ("tagline", "greeting", "accent"):
        if getattr(body, k) is not None:
            brand[k] = getattr(body, k)
    changes["brand"] = Brand(**brand).model_dump()
    if body.aisles:
        names = [re.sub(r"[^A-Za-z0-9 ]+", "", a).strip()[:16] or f"A{i + 1}" for i, a in enumerate(body.aisles)]
        changes["floor_map"] = [a.model_dump() for a in floor_map(names)]
    ref.update(changes)
    catalog.invalidate(store_id)
    return ref.get().to_dict()


@router.get("/owner/{store_id}/team")
def team(store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    doc = db.store_ref(store_id).get().to_dict() or {}
    return {"owner_emails": doc.get("owner_emails", []), "staff_emails": doc.get("staff_emails", [])}


class StaffIn(BaseModel):
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/owner/{store_id}/staff")
def add_staff(body: StaffIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    db.store_ref(store_id).update({"staff_emails": firestore.ArrayUnion([body.email.lower()])})
    return {"staff_emails": db.store_ref(store_id).get().to_dict().get("staff_emails", [])}


@router.delete("/owner/{store_id}/staff/{email}")
def remove_staff(store_id: str = STORE_ID, email: str = Path(max_length=120), uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    db.store_ref(store_id).update({"staff_emails": firestore.ArrayRemove([email.lower()])})
    return {"staff_emails": db.store_ref(store_id).get().to_dict().get("staff_emails", [])}


class PaymentsIn(BaseModel):
    key_id: str = Field(default="", max_length=64, pattern=r"^[A-Za-z0-9_]*$")
    key_secret: str = Field(default="", max_length=128)


@router.patch("/owner/{store_id}/payments")
def patch_payments(body: PaymentsIn, store_id: str = STORE_ID, uid: str = Depends(current_uid)):
    require_owner(store_id, uid)
    if body.key_id and body.key_secret:
        payments.store_secret(store_id, body.key_secret)
        cfg = Payments(provider="razorpay", key_id=body.key_id)
    else:
        cfg = Payments()
    db.store_ref(store_id).update({"payments": cfg.model_dump()})
    db.audit(store_id).document(uuid.uuid4().hex).set({"actor": uid, "action": "payments_updated", "created_at": now(), "payload": {"provider": cfg.provider}})
    return cfg.model_dump()
