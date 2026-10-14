import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import catalog, db, qr

client = TestClient(app)


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id]})
    for sku, price, qty in (("salt", 20, 5), ("rice", 300, 1)):
        p = Product.from_row(store_id=store_id, sku=sku, name=sku, price=price, mrp=price + 5, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(
            Inventory(product_id=p.product_id, store_id=store_id, on_hand=qty).model_dump())
    catalog.invalidate(store_id)
    return store_id


def enter(shop, aisle=None):
    body = {"store_id": shop, "token": qr.entrance_token(shop)}
    if aisle:
        body["aisle"] = aisle
    return client.post("/sessions/instore", json=body).json()


def test_entrance_token_creates_instore_session(shop):
    s = enter(shop, aisle="A3")
    assert s["mode"] == "instore" and s["aisle_hint"] == "A3" and s["cart_id"]


def test_bad_entrance_token_401(shop):
    assert client.post("/sessions/instore", json={"store_id": shop, "token": "x.y"}).status_code == 401


def test_token_for_other_store_401(shop):
    res = client.post("/sessions/instore", json={"store_id": shop, "token": qr.entrance_token("other-store")})
    assert res.status_code == 401


def test_patch_aisle_hint(shop):
    s = enter(shop)
    res = client.patch(f"/sessions/{s['session_id']}", json={"aisle_hint": "A5"})
    assert res.status_code == 200 and res.json()["aisle_hint"] == "A5"


def test_cart_add_get_remove_with_session_header(shop):
    s = enter(shop)
    h = {"X-Session-Id": s["session_id"]}
    res = client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-salt", "qty": 2, "via": "scan"}, headers=h)
    assert res.status_code == 200
    assert res.json()["count"] == 2 and res.json()["total"] == 40
    assert client.get(f"/carts/{s['cart_id']}", headers=h).json()["items"][0]["name"] == "salt"
    res = client.delete(f"/carts/{s['cart_id']}/items/{shop}-salt", headers=h)
    assert res.json()["count"] == 0


def test_cart_out_of_stock_is_409(shop):
    s = enter(shop)
    res = client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-rice", "qty": 2, "via": "scan"},
                      headers={"X-Session-Id": s["session_id"]})
    assert res.status_code == 409 and res.json()["detail"] == "out_of_stock"


def test_cart_requires_owning_session(shop):
    s1, s2 = enter(shop), enter(shop)
    assert client.get(f"/carts/{s1['cart_id']}").status_code == 401
    assert client.get(f"/carts/{s1['cart_id']}", headers={"X-Session-Id": s2["session_id"]}).status_code == 403


def test_checkout_flow_mock(shop):
    s = enter(shop)
    h = {"X-Session-Id": s["session_id"]}
    client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-salt", "qty": 1, "via": "scan"}, headers=h)
    res = client.post("/checkout/intent", json={"session_id": s["session_id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "mock" and body["amount"] == 20
    res = client.post("/checkout/confirm", json={"order_id": body["order_id"], "payment_id": "mock_pay",
                                                 "signature": "mock", "session_id": s["session_id"]})
    assert res.status_code == 200
    order = res.json()
    assert order["status"] == "paid" and order["receipt_token"]
    assert client.get(f"/orders/{order['order_id']}", headers=h).json()["total"] == 20
    assert client.get(f"/orders/{order['order_id']}").status_code == 401


def test_checkout_intent_empty_cart_409(shop):
    s = enter(shop)
    res = client.post("/checkout/intent", json={"session_id": s["session_id"]})
    assert res.status_code == 409


def test_confirm_wrong_session_403(shop):
    s, other = enter(shop), enter(shop)
    client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-salt", "qty": 1, "via": "scan"},
                headers={"X-Session-Id": s["session_id"]})
    oid = client.post("/checkout/intent", json={"session_id": s["session_id"]}).json()["order_id"]
    res = client.post("/checkout/confirm", json={"order_id": oid, "payment_id": "p", "signature": "mock",
                                                 "session_id": other["session_id"]})
    assert res.status_code == 403


def test_owner_qr_urls(shop):
    db.store_ref(shop).update({"floor_map": [{"aisle": "A1", "x": 0, "y": 0, "w": 1, "h": 1}]})
    res = client.get(f"/owner/{shop}/qr", headers={"X-Test-Uid": "owner-1"})
    assert res.status_code == 200
    body = res.json()
    assert f"/s/{shop}?t=" in body["entrance_url"]
    assert body["aisles"][0]["aisle"] == "A1" and "&aisle=A1" in body["aisles"][0]["url"]
    assert client.get(f"/owner/{shop}/qr").status_code == 401


def test_malformed_ids_are_4xx_not_500(shop):
    assert client.post("/sessions/instore", json={"store_id": shop, "token": "x.é"}).status_code == 401
    assert client.get(f"/carts/abc", headers={"X-Session-Id": "a/b"}).status_code == 422
    assert client.post("/checkout/intent", json={"session_id": "a/b"}).status_code == 422
    assert client.post("/checkout/confirm", json={"order_id": "a/b", "payment_id": "p", "signature": "mock", "session_id": "0" * 32}).status_code == 422
    assert client.get("/orders/a%2Fb", headers={"X-Session-Id": "0" * 32}).status_code in (404, 422)
