from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api import online
from app.connectors import csv_connector as csvc
from app.domain.models import CartItem, Offer, Order, Store, now
from app.main import app
from app.services import catalog, db

client = TestClient(app)


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Online Mart", city="Chennai").model_dump())
    rows = [csvc.Row(line=i, sku=f"S{i}", name=n, price=p, on_hand=10, category=c, aisle="A1") for i, (n, p, c) in enumerate([
        ("Aashirvaad Atta 5 kg", 265, "Grocery"), ("Aavin Milk 500 ml", 28, "Dairy"), ("Amul Butter 100 g", 60, "Dairy"),
        ("Tata Salt 1 kg", 28, "Grocery"), ("Lays Chips", 20, "Snacks")], start=1)]
    csvc.upsert(store_id, rows, high_value_threshold=500)
    catalog.invalidate(store_id)
    online._popularity.clear()
    return store_id


def _order(store_id, items, days_ago=1, status="paid"):
    o = Order(order_id=f"o-{len(items)}-{days_ago}-{items[0][0]}", store_id=store_id, session_id="s", cart_id="c", channel="store",
              items=[CartItem(product_id=f"{store_id}-{sku.lower()}", name=sku, qty=q, unit_price=10, mrp=10) for sku, q in items],
              subtotal=10, savings=0, total=10, status=status, created_at=now() - timedelta(days=days_ago))
    db.orders().document(o.order_id).set(o.model_dump())


def test_home_ranks_by_real_purchases_and_lists_categories_and_deals(shop):
    _order(shop, [("S2", 5), ("S1", 1)]); _order(shop, [("S2", 4)], days_ago=3); _order(shop, [("S5", 9)], days_ago=40)   # too old
    _order(shop, [("S3", 7)], status="cancelled")
    db.offers(shop).document("d1").set(Offer(offer_id="d1", store_id=shop, name="10% off dairy", kind="category", category="Dairy", percent_off=10).model_dump())
    home = client.get(f"/stores/{shop}/home").json()
    assert [p["name"] for p in home["trending"]] == ["Aavin Milk 500 ml", "Aashirvaad Atta 5 kg"]
    assert home["trending"][0]["bought_30d"] == 9 and "embedding" not in home["trending"][0]
    assert {c["name"]: c["count"] for c in home["categories"]} == {"Grocery": 2, "Dairy": 2, "Snacks": 1}
    assert home["deals"][0]["name"] == "10% off dairy" and [p["name"] for p in home["deals"][0]["products"]][0] == "Aavin Milk 500 ml"
    assert home["segment"] == "guest" and len(home["recommended"]) == 3                       # the rest of the catalog, best sellers first
    assert {"store_id": shop, "name": "Online Mart", "city": "Chennai", "tagline": ""} in client.get("/stores").json()


def test_listing_filters_by_category_and_searches(shop):
    _order(shop, [("S3", 2)])
    page = client.get(f"/stores/{shop}/products", params={"category": "dairy"}).json()
    assert [p["name"] for p in page["products"]] == ["Amul Butter 100 g", "Aavin Milk 500 ml"] and page["total"] == 2 and page["more"] is False
    assert client.get(f"/stores/{shop}/products", params={"limit": 2}).json()["more"] is True
    found = client.get(f"/stores/{shop}/products", params={"q": "atta"}).json()["products"]
    assert found and found[0]["name"] == "Aashirvaad Atta 5 kg" and "bought_30d" in found[0]


def test_facts_need_a_session_and_use_the_guarded_lookup(shop, monkeypatch):
    pid = f"{shop}-s1"
    assert client.get(f"/stores/{shop}/products/{pid}/facts").status_code == 401
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    monkeypatch.setattr(online.facts, "lookup", lambda store, sid, q, p, lang: {"ok": True, "summary": f"{p.name}: {q} ({lang})", "sources": [], "note": "n"})
    res = client.get(f"/stores/{shop}/products/{pid}/facts", params={"language": "ta"}, headers={"X-Session-Id": s["session_id"]})
    assert res.status_code == 200 and res.json()["summary"].startswith("Aashirvaad Atta 5 kg: ingredients") and res.json()["summary"].endswith("(ta)")


def test_cart_stepper_sets_reduces_removes_and_cannot_add_in_store(shop):
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    h = {"X-Session-Id": s["session_id"]}
    pid = f"{shop}-s4"
    client.post(f"/carts/{s['cart_id']}/items", json={"product_id": pid, "qty": 1, "via": "chat"}, headers=h)
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 3}, headers=h).json()["items"][0]["qty"] == 3
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 2}, headers=h).json()["items"][0]["qty"] == 2
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 0}, headers=h).json()["items"] == []
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 1}, headers=h).status_code == 404
    db.sessions().document(s["session_id"]).update({"mode": "instore"})
    client.post(f"/carts/{s['cart_id']}/items", json={"product_id": pid, "qty": 2, "via": "scan"}, headers=h)
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 5}, headers=h).status_code == 409
    assert client.patch(f"/carts/{s['cart_id']}/items/{pid}", json={"qty": 1}, headers=h).json()["items"][0]["qty"] == 1
