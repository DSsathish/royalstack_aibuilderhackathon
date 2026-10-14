import json

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Store
from app.main import app
from app.services import db

client = TestClient(app)
CSV = b"sku,name,price,on_hand\nA1,Salt 1kg,20,10\n"
MAPPING = json.dumps({"sku": "sku", "name": "name", "price": "price", "on_hand": "on_hand"})


@pytest.fixture
def owned(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Owned").model_dump())
    db.users().document("owner-1").set({"stores": [store_id]})
    return store_id


def post_csv(store_id, headers):
    return client.post(f"/owner/{store_id}/import/csv", headers=headers,
                       files={"file": ("p.csv", CSV, "text/csv")}, data={"mapping": MAPPING})


def test_requires_auth(owned):
    assert post_csv(owned, {}).status_code == 401


def test_rejects_non_member(owned):
    assert post_csv(owned, {"X-Test-Uid": "someone-else"}).status_code == 403


def test_owner_can_import(owned):
    res = post_csv(owned, {"X-Test-Uid": "owner-1"})
    assert res.status_code == 200, res.text
    assert res.json()["created"] == 1
    assert db.products(owned).document(f"{owned}-a1").get().exists


def test_bad_mapping_is_400(owned):
    res = client.post(f"/owner/{owned}/import/csv", headers={"X-Test-Uid": "owner-1"},
                      files={"file": ("p.csv", CSV, "text/csv")}, data={"mapping": json.dumps({"sku": "sku"})})
    assert res.status_code == 400


def test_import_writes_audit(owned):
    post_csv(owned, {"X-Test-Uid": "owner-1"})
    entries = [d.to_dict() for d in db.audit(owned).stream()]
    assert any(e["action"] == "import_csv" and e["actor"] == "owner-1" for e in entries)


def test_mapping_must_be_object(owned):
    res = client.post(f"/owner/{owned}/import/csv", headers={"X-Test-Uid": "owner-1"},
                      files={"file": ("p.csv", CSV, "text/csv")}, data={"mapping": "[1,2]"})
    assert res.status_code == 400


def test_missing_file_is_422(owned):
    res = client.post(f"/owner/{owned}/import/csv", headers={"X-Test-Uid": "owner-1"}, data={"mapping": MAPPING})
    assert res.status_code == 422


def test_bearer_token_uid_comes_from_sub(owned, monkeypatch):
    from app.services import auth
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": "owner-1"})
    res = post_csv(owned, {"Authorization": "Bearer fake"})
    assert res.status_code == 200, res.text
