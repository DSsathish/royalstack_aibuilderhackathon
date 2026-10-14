"""Shopper and owner sessions. Phase 3 adds the signed QR entry path."""

import uuid
from datetime import timedelta

from app.domain.models import Mode, Session, now
from app.services import db

TTL = timedelta(hours=4)


def create(store_id: str, mode: Mode, user_id: str | None = None) -> Session:
    s = Session(session_id=uuid.uuid4().hex, store_id=store_id, mode=mode, user_id=user_id,
                cart_id=uuid.uuid4().hex, expires_at=now() + TTL)
    db.sessions().document(s.session_id).set(s.model_dump())
    return s


def get(session_id: str) -> Session | None:
    doc = db.sessions().document(session_id).get()
    if not doc.exists:
        return None
    s = Session(**doc.to_dict())
    return s if s.expires_at > now() else None
