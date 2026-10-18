import pytest
from fastapi.testclient import TestClient

from app.domain.models import Store
from app.main import app
from app.services import barcode, db

client = TestClient(app)
H = {"X-Test-Uid": "owner-1"}


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    return store_id


def test_lookup_hit_is_cached(shop, monkeypatch):
    calls = []
    def fake_fetch(code):
        calls.append(code)
        return {"found": True, "name": "Aashirvaad Atta 5kg", "brand": "ITC", "category": "Staples", "image_url": "https://img/x.jpg"}
    monkeypatch.setattr(barcode, "_fetch_open_food_facts", fake_fetch)
    a = client.get(f"/owner/{shop}/lookup/8901725012345", headers=H).json()
    b = client.get(f"/owner/{shop}/lookup/8901725012345", headers=H).json()
    assert a["found"] and a["name"] == "Aashirvaad Atta 5kg" and b == a and calls == ["8901725012345"]


def test_lookup_miss(shop, monkeypatch):
    monkeypatch.setattr(barcode, "_fetch_open_food_facts", lambda code: {"found": False})
    assert client.get(f"/owner/{shop}/lookup/8900000000999", headers=H).json()["found"] is False
    assert client.get(f"/owner/{shop}/lookup/abc", headers=H).status_code == 422
    assert client.get(f"/owner/{shop}/lookup/8900000000999").status_code == 401


def test_create_and_update_product(shop):
    body = {"barcode": "8901725012345", "name": "Aashirvaad Atta 5kg", "brand": "ITC", "category": "Staples", "price": 265, "mrp": 280, "on_hand": 12, "aisle": "A1"}
    res = client.post(f"/owner/{shop}/products", json=body, headers=H)
    assert res.status_code == 200, res.text
    pid = res.json()["product_id"]
    assert pid == f"{shop}-8901725012345" and res.json()["available"] == 12 and res.json()["location"]["aisle"] == "A1"
    res = client.post(f"/owner/{shop}/products", json={**body, "price": 270, "on_hand": 40}, headers=H)
    assert res.json()["price"] == 270 and res.json()["available"] == 40
    assert client.post(f"/owner/{shop}/products", json={**body, "price": -1}, headers=H).status_code == 422
    assert client.get(f"/stores/{shop}/products/by-barcode/8901725012345").json()["name"] == "Aashirvaad Atta 5kg"


def test_owner_moves_a_product_to_an_aisle(shop):
    h = {"X-Test-Uid": "owner-1"}
    owned = shop
    created = client.post(f"/owner/{owned}/products", json={"barcode": "8901234567890", "name": "Rice 5kg", "price": 400, "on_hand": 5}, headers=h).json()
    pid = created["product_id"]
    client.patch(f"/owner/{owned}/store", json={"aisles": ["Rice", "Oil"]}, headers=h)      # the fixture store has no map yet
    aisle = db.store_ref(owned).get().to_dict()["floor_map"][0]["aisle"]
    res = client.patch(f"/owner/{owned}/products/{pid}/location", json={"aisle": aisle, "bay": 3, "side": "right"}, headers=h)
    assert res.status_code == 200, res.text
    assert client.get(f"/stores/{owned}/products/{pid}").json()["location"]["bay"] == 3
    assert client.patch(f"/owner/{owned}/products/{pid}/location", json={"aisle": "Nowhere"}, headers=h).status_code == 422
    assert client.patch(f"/owner/{owned}/products/{pid}/location", json={"aisle": aisle}, headers={"X-Test-Uid": "stranger"}).status_code == 403
    assert any(e.to_dict()["action"] == "product_moved" for e in db.audit(owned).stream())


def test_add_by_scan_places_cold_products_in_the_chiller(shop):
    h = {"X-Test-Uid": "owner-1"}
    client.patch(f"/owner/{shop}/store", json={"floor_map": [{"aisle": "A1", "x": 80, "y": 80, "w": 90, "h": 420}, {"aisle": "Chiller", "x": 880, "y": 80, "w": 90, "h": 200, "kind": "chiller"}]}, headers=h)
    milk = client.post(f"/owner/{shop}/products", json={"barcode": "8901234567891", "name": "Toned Milk 500ml", "category": "Dairy", "price": 28, "on_hand": 10}, headers=h).json()
    assert milk["location"]["aisle"] == "Chiller" and milk["storage"] == "chilled"
    rice = client.post(f"/owner/{shop}/products", json={"barcode": "8901234567892", "name": "Ponni Rice 5kg", "price": 400, "on_hand": 5}, headers=h).json()
    assert rice.get("location") is None and rice["storage"] == "ambient"


def test_owner_edits_every_record_from_the_drawer(shop):
    from app.domain.models import Aisle
    db.store_ref(shop).update({"floor_map": [Aisle(aisle="A1", x=80, y=80, w=90, h=420).model_dump(), Aisle(aisle="A2", x=230, y=80, w=90, h=420).model_dump()]})
    db.users().document("staff-7").set({"stores": [shop], "roles": {shop: "staff"}})
    created = client.post(f"/owner/{shop}/products", json={"barcode": "8901234567890", "name": "Edit Me", "price": 50, "on_hand": 5}, headers=H)
    assert created.status_code == 200, created.text
    pid = created.json()["product_id"]
    body = {"name": "Edited Name", "brand": "Brand X", "price": 60, "mrp": 70, "barcode": "8901234567891", "on_hand": 12, "reorder_point": 4,
            "aisle": "A2", "bay": 3, "side": "right", "status": "seasonal", "tags": ["one", " two ", ""], "pack_size": "1 kg", "gst_rate": 5}
    res = client.patch(f"/owner/{shop}/products/{pid}", json=body, headers=H)
    assert res.status_code == 200, res.text
    detail = client.get(f"/owner/{shop}/products/{pid}", headers={"X-Test-Uid": "staff-7"}).json()      # staff may read
    p, stock = detail["product"], detail["stock"]
    assert p["name"] == "Edited Name" and p["brand"] == "Brand X" and p["price"] == 60 and p["mrp"] == 70 and p["barcode"] == "8901234567891"
    assert p["status"] == "seasonal" and p["tags"] == ["one", "two"] and p["pack_size"] == "1 kg" and p["gst_rate"] == 5
    assert p["location"]["aisle"] == "A2" and p["location"]["bay"] == 3 and p["location"]["side"] == "right" and p["location"]["shelf"] == 1
    assert stock["on_hand"] == 12 and stock["reorder_point"] == 4
    row = next(r for r in client.get(f"/owner/{shop}/inventory", headers=H).json() if r["product_id"] == pid)
    assert row["barcode"] == "8901234567891" and row["price"] == 60 and row["bay"] == 3 and row["pack_size"] == "1 kg" and row["on_hand"] == 12
    assert client.patch(f"/owner/{shop}/products/{pid}", json={"price": 61}, headers={"X-Test-Uid": "staff-7"}).status_code == 403
    assert client.patch(f"/owner/{shop}/products/{pid}", json={"barcode": "12"}, headers=H).status_code == 422
    assert client.patch(f"/owner/{shop}/products/{pid}", json={"mrp": 10}, headers=H).status_code == 422
    assert client.patch(f"/owner/{shop}/products/{pid}", json={"aisle": "Z9"}, headers=H).status_code == 422
    assert client.patch(f"/owner/{shop}/products/{pid}", json={}, headers=H).status_code == 422
    assert any(a.to_dict()["action"] == "product_edited" for a in db.audit(shop).stream())
