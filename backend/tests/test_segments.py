from datetime import timedelta

from app.domain.models import Customer, Store, now
from app.services import db, segments


def c(**kw):
    return Customer(**{"uid": "u", "store_id": "s", **kw})


def test_classify_rules():
    assert segments.classify(c(visits=0)) == "new"
    assert segments.classify(c(visits=1)) == "new"
    assert segments.classify(c(visits=2)) == "regular"
    assert segments.classify(c(visits=5, spend=5000)) == "vip"
    assert segments.classify(c(visits=5, spend=4999)) == "regular"
    assert segments.classify(c(visits=2, last_seen=now() - timedelta(days=46))) == "at_risk"
    assert segments.classify(c(visits=1, last_seen=now() - timedelta(days=100))) == "new"


def test_refresh_rewrites_segments(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.customers(store_id).document("a").set(c(uid="a", store_id=store_id, visits=3, last_seen=now() - timedelta(days=60)).model_dump())
    db.customers(store_id).document("b").set(c(uid="b", store_id=store_id, visits=1).model_dump())
    assert segments.refresh(store_id) == {"at_risk": 1, "new": 1}
    assert db.customers(store_id).document("a").get().to_dict()["segment"] == "at_risk"
