from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.connectors import normalizer
from app.domain.models import Store
from app.main import app
from app.services import catalog, connectors, db

client = TestClient(app)
OWNER = {"X-Test-Uid": "owner-1"}
CSV = b"Item Code,Item Name,Rate,Closing Stock\nmilk,Toned Milk,30,12\n"
MAPPING = '{"sku": "Item Code", "name": "Item Name", "price": "Rate", "on_hand": "Closing Stock", "brand": ""}'


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(connectors, "public_host", lambda host: None)
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(connectors.secrets, "put", lambda name, value: None)
    monkeypatch.setattr(connectors.secrets, "get", lambda name: "")
    monkeypatch.setattr(connectors, "fetch", lambda url, headers=None, hops=5: SimpleNamespace(content=CSV, headers={"content-type": "text/csv"}))


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    catalog.invalidate(store_id)
    return store_id


def test_file_inspect_then_apply(shop):
    assert client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "file"}, files={"file": ("s.csv", CSV, "text/csv")},
                       headers={"X-Test-Uid": "stranger"}).status_code == 403
    res = client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "file"}, files={"file": ("s.csv", CSV, "text/csv")}, headers=OWNER)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mapping"]["sku"] == "Item Code" and body["preview"]["adds"] == 1
    res = client.post(f"/owner/{shop}/connectors/apply", data={"kind": "file", "mapping": MAPPING, "label": "stock.csv"},
                      files={"file": ("s.csv", CSV, "text/csv")}, headers=OWNER)
    assert res.status_code == 200, res.text
    assert res.json()["result"]["created"] == 1 and res.json()["connector"] is None
    assert catalog.get_by_sku(shop, "milk").name == "Toned Milk"


def test_bad_inputs_are_400(shop):
    assert client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "zip"}, headers=OWNER).status_code == 400
    assert client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "sheet"}, headers=OWNER).status_code == 400
    assert client.post(f"/owner/{shop}/connectors/inspect", data={"kind": "sheet", "url": "https://example.com/not-a-sheet"}, headers=OWNER).status_code == 400
    assert client.post(f"/owner/{shop}/connectors/apply", data={"kind": "file", "mapping": "nope"}, files={"file": ("s.csv", CSV, "text/csv")}, headers=OWNER).status_code == 400
    assert client.post(f"/owner/{shop}/connectors/discover", json={"dsn": "mongodb://x/y"}, headers=OWNER).status_code == 400


def test_api_source_saved_listed_run_and_removed(shop):
    res = client.post(f"/owner/{shop}/connectors/apply", data={"kind": "api", "url": "https://pos.example.com/x.csv", "auth": "Bearer t",
                      "mapping": MAPPING, "label": "POS", "save": "true", "every_min": "30"}, headers=OWNER)
    assert res.status_code == 200, res.text
    c = res.json()["connector"]
    assert c["kind"] == "api" and c["every_min"] == 30 and "auth" not in c and "Bearer" not in res.text
    listed = client.get(f"/owner/{shop}/connectors", headers=OWNER).json()["connectors"]
    assert [x["label"] for x in listed] == ["POS"]
    run = client.post(f"/owner/{shop}/connectors/{c['connector_id']}/run", headers=OWNER).json()
    assert run["ok"] and run["updated"] == 1
    assert client.delete(f"/owner/{shop}/connectors/{c['connector_id']}", headers=OWNER).json() == {"ok": True}
    assert client.delete(f"/owner/{shop}/connectors/{c['connector_id']}", headers=OWNER).status_code == 404
