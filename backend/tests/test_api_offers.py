import time

import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import catalog, customers, db, points, sessions

client = TestClient(app)
OWNER = {"X-Test-Uid": "owner-1"}


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    p = Product.from_row(store_id=store_id, sku="milk", name="Milk", price=50, mrp=50, threshold=500, category="Dairy")
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=20).model_dump())
    catalog.invalidate(store_id)
    return store_id


def test_owner_crud_and_audit(shop):
    body = {"name": "Dairy week", "kind": "category", "category": "Dairy", "percent_off": 10}
    assert client.post(f"/owner/{shop}/offers", json=body, headers={"X-Test-Uid": "stranger"}).status_code == 403
    res = client.post(f"/owner/{shop}/offers", json=body, headers=OWNER)
    assert res.status_code == 200, res.text
    oid = res.json()["offer_id"]
    assert client.post(f"/owner/{shop}/offers", json={**body, "percent_off": 95}, headers=OWNER).status_code == 422
    assert client.get(f"/owner/{shop}/offers", headers=OWNER).json()[0]["offer_id"] == oid
    assert client.patch(f"/owner/{shop}/offers/{oid}", json={"active": False}, headers=OWNER).json()["active"] is False
    assert client.get(f"/stores/{shop}/offers").json() == []
    client.patch(f"/owner/{shop}/offers/{oid}", json={"active": True}, headers=OWNER)
    assert [o["name"] for o in client.get(f"/stores/{shop}/offers").json()] == ["Dairy week"]
    assert client.delete(f"/owner/{shop}/offers/{oid}", headers=OWNER).status_code == 200
    assert client.get(f"/owner/{shop}/offers", headers=OWNER).json() == []
    actions = [d.to_dict()["action"] for d in db.audit(shop).stream()]
    assert actions.count("offer_created") == 1 and "offer_changed" in actions and "offer_deleted" in actions


def test_shopper_sees_segment_offers_and_cart_discounts(shop):
    client.post(f"/owner/{shop}/offers", json={"name": "Members", "kind": "cart", "amount_off": 5, "segment": "signed_in"}, headers=OWNER)
    client.post(f"/owner/{shop}/offers", json={"name": "Everyone", "kind": "product", "product_id": f"{shop}-milk", "amount_off": 2}, headers=OWNER)
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    h = {"X-Session-Id": s["session_id"]}
    assert {o["name"] for o in client.get(f"/stores/{shop}/offers", headers=h).json()} == {"Everyone"}
    customers.link(sessions.get(s["session_id"]), "cust-1", "+919999900001")
    assert {o["name"] for o in client.get(f"/stores/{shop}/offers", headers=h).json()} == {"Everyone", "Members"}
    view = client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-milk", "qty": 2, "via": "chat"}, headers=h).json()
    assert view["discount_total"] == 9 and view["total"] == 91 and view["points_balance"] == 0 and view["segment"] == "new"
    assert sorted(l["name"] for l in view["discounts"]) == ["Everyone", "Members"]


def test_get_offers_tool(shop):
    client.post(f"/owner/{shop}/offers", json={"name": "Everyone", "kind": "product", "product_id": f"{shop}-milk", "amount_off": 2}, headers=OWNER)
    from app.agent import tools

    class Ctx:
        state = {"store_id": shop, "session_id": "x", "cart_id": "c", "segment": "guest"}
    out = tools.get_offers(Ctx())
    assert out["ok"] and out["offers"][0]["name"] == "Everyone" and "Milk" in out["offers"][0]["detail"]
    assert "get_offers" in {t.__name__ for t in tools.TOOLS_BY_MODE["instore"]} and "get_offers" in {t.__name__ for t in tools.TOOLS_BY_MODE["online"]}


def test_redeem_requires_fresh_matching_phone_token(shop, monkeypatch):
    from app.services import auth
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    h = {"X-Session-Id": s["session_id"]}
    customers.link(sessions.get(s["session_id"]), "cust-2", "+919999900002")
    points.adjust(shop, "cust-2", 100, "welcome", by="owner-1")
    client.post(f"/carts/{s['cart_id']}/items", json={"product_id": f"{shop}-milk", "qty": 2, "via": "chat"}, headers=h)
    body = {"session_id": s["session_id"], "points": 60}
    assert client.post("/checkout/intent", json=body).status_code == 401                        # no token
    claims = {"sub": "cust-2", "phone_number": "+919999900002"}
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {**claims, "auth_time": int(time.time()) - 3600})
    assert client.post("/checkout/intent", json=body, headers={"Authorization": "Bearer t"}).status_code == 403   # stale sign-in
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {**claims, "auth_time": int(time.time())})
    res = client.post("/checkout/intent", json=body, headers={"Authorization": "Bearer t"})
    assert res.status_code == 200, res.text
    assert res.json()["amount"] == 40 and res.json()["points_redeemed"] == 60
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": "someone-else", "phone_number": "+919999900009", "auth_time": int(time.time())})
    assert client.post("/checkout/intent", json=body, headers={"Authorization": "Bearer t"}).status_code == 403   # must be the linked shopper
    assert client.post("/checkout/intent", json={"session_id": s["session_id"]}).status_code == 200              # no points: no token needed


def test_owner_points_adjust_and_me_points(shop, monkeypatch):
    from app.services import auth
    customers.link(sessions.create(shop, "online"), "cust-3", "+919999900003")
    res = client.post(f"/owner/{shop}/customers/cust-3/points", json={"delta": 25, "reason": "birthday"}, headers=OWNER)
    assert res.status_code == 200 and res.json()["points"] == 25
    assert client.post(f"/owner/{shop}/customers/cust-3/points", json={"delta": -30, "reason": "x"}, headers=OWNER).status_code == 409
    assert client.post(f"/owner/{shop}/customers/cust-3/points", json={"delta": 5, "reason": ""}, headers=OWNER).status_code == 422
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": "cust-3", "phone_number": "+919999900003"})
    body = client.get(f"/me/points?store_id={shop}", headers={"Authorization": "Bearer t"}).json()
    assert body["balance"] == 25 and body["entries"][0]["reason"] == "birthday"
    rows = client.get(f"/owner/{shop}/customers", headers=OWNER).json()
    assert rows[0]["points"] == 25 and rows[0]["segment"] == "new"
