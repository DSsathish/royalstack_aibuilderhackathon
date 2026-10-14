from datetime import timedelta

from app.domain.models import now
from app.services import db, sessions


def test_create_and_get(store_id):
    s = sessions.create(store_id, "instore")
    got = sessions.get(s.session_id)
    assert got.store_id == store_id and got.mode == "instore"
    assert got.cart_id and got.expires_at > now()


def test_get_missing_is_none():
    assert sessions.get("nope") is None


def test_expired_session_is_none(store_id):
    s = sessions.create(store_id, "online")
    db.client().collection("sessions").document(s.session_id).update({"expires_at": now() - timedelta(minutes=1)})
    assert sessions.get(s.session_id) is None
