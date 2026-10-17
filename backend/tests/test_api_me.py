import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store
from app.main import app
from app.services import cart, catalog, checkout, conversation, db, sessions

client = TestClient(app)


def phone_bearer(monkeypatch, uid="cust-1", phone="+919999900001"):
    from app.services import auth
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": uid, "phone_number": phone, "firebase": {"sign_in_provider": "phone"}})
    return {"Authorization": "Bearer t"}


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    p = Product.from_row(store_id=store_id, sku="milk", name="Toned Milk", price=28, mrp=28, threshold=500, category="Dairy")
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=20).model_dump())
    catalog.invalidate(store_id)
    return store_id


def test_link_session_creates_customer_and_marks_orders(shop, monkeypatch):
    h = phone_bearer(monkeypatch)
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    res = client.post(f"/sessions/{s['session_id']}/link", headers=h)
    assert res.status_code == 200 and res.json()["customer_id"] == "cust-1"
    prof = client.get(f"/me/profile?store_id={shop}", headers=h).json()
    assert prof["phone_last4"] == "0001" and prof["visits"] == 0 and prof["consent_at"]
    sess = sessions.get(s["session_id"])
    cart.add(shop, sess.cart_id, f"{shop}-milk", 2, via="chat")
    o = checkout.confirm(checkout.intent(sess).order_id, payment_id="p", signature="mock")
    assert o.customer_id == "cust-1"
    prof = client.get(f"/me/profile?store_id={shop}", headers=h).json()
    assert prof["visits"] == 1 and prof["spend"] == 56
    orders = client.get(f"/me/orders?store_id={shop}", headers=h).json()
    assert len(orders) == 1 and orders[0]["order_id"] == o.order_id
    s2 = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s2['session_id']}/link", headers=h)
    sess2 = sessions.get(s2["session_id"])
    cart.add(shop, sess2.cart_id, f"{shop}-milk", 1, via="chat")
    checkout.confirm(checkout.intent(sess2).order_id, payment_id="p2", signature="mock")
    prof = client.get(f"/me/profile?store_id={shop}", headers=h).json()
    assert prof["visits"] == 2 and prof["usual_items"] == [f"{shop}-milk"]
    from app.agent import prompts
    assert "Toned Milk" in prompts.customer_block(prompts.customer_state(sess2))


def test_profile_patch_and_assistant_block(shop, monkeypatch):
    h = phone_bearer(monkeypatch)
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s['session_id']}/link", headers=h)
    res = client.patch("/me/profile", json={"store_id": shop, "name": "Priya", "language": "ta", "dietary": ["veg"], "favourite_categories": ["Dairy"], "substitution": "same_brand"}, headers=h)
    assert res.status_code == 200 and res.json()["name"] == "Priya" and res.json()["dietary"] == ["veg"]
    assert client.patch("/me/profile", json={"store_id": shop, "dietary": ["x" * 40]}, headers=h).status_code == 422
    from app.agent import prompts
    block = prompts.customer_block(prompts.customer_state(sessions.get(s["session_id"])))
    assert "Priya" in block and "veg" in block and "same brand" in block.lower()
    assert prompts.customer_block({}) == ""


def test_guest_session_has_no_customer(shop):
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    from app.agent import prompts
    assert prompts.customer_state(sessions.get(s["session_id"])) == {}
    assert client.get(f"/me/profile?store_id={shop}").status_code == 401


def test_link_requires_phone_token(shop, monkeypatch):
    from app.services import auth
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": "g-1", "email": "x@example.com", "email_verified": True})
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    assert client.post(f"/sessions/{s['session_id']}/link", headers={"Authorization": "Bearer t"}).status_code == 403


def test_export_and_delete(shop, monkeypatch):
    h = phone_bearer(monkeypatch, uid="cust-del", phone="+919999900002")
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s['session_id']}/link", headers=h)
    sess = sessions.get(s["session_id"])
    conversation.add_turn(sess, "user", "hello")
    cart.add(shop, sess.cart_id, f"{shop}-milk", 1, via="chat")
    o = checkout.confirm(checkout.intent(sess).order_id, payment_id="p", signature="mock")
    exp = client.get("/me/export", headers=h).json()
    assert exp["profiles"][0]["store_id"] == shop and exp["orders"][0]["order_id"] == o.order_id and exp["turns"][0]["text"] == "hello"
    assert client.delete("/me", headers=h).status_code == 200
    assert client.get(f"/me/profile?store_id={shop}", headers=h).status_code == 404
    assert checkout.get(o.order_id).customer_id is None
    assert conversation.recent(sess) == []
    assert sessions.get(s["session_id"]).customer_id is None
    s3 = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s3['session_id']}/link", headers=h)      # a fresh record, nothing resurrected
    assert client.get(f"/me/profile?store_id={shop}", headers=h).json()["visits"] == 0


def test_owner_customers_listing(shop, monkeypatch):
    h = phone_bearer(monkeypatch, uid="cust-list", phone="+919999900003")
    s = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s['session_id']}/link", headers=h)
    client.patch("/me/profile", json={"store_id": shop, "name": "Arun"}, headers=h)
    rows = client.get(f"/owner/{shop}/customers", headers={"X-Test-Uid": "owner-1"}).json()
    assert any(r["name"] == "Arun" and r["phone_last4"] == "0003" for r in rows)
    assert client.get(f"/owner/{shop}/customers", headers={"X-Test-Uid": "stranger"}).status_code == 403


def test_signed_in_shopper_reopens_old_receipts(shop, monkeypatch):
    h = phone_bearer(monkeypatch, uid="cust-rcpt", phone="+919999900004")
    s1 = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    client.post(f"/sessions/{s1['session_id']}/link", headers=h)
    sess1 = sessions.get(s1["session_id"])
    cart.add(shop, sess1.cart_id, f"{shop}-milk", 1, via="chat")
    o = checkout.confirm(checkout.intent(sess1).order_id, payment_id="p", signature="mock")
    s2 = client.post("/sessions", json={"store_id": shop, "mode": "online"}).json()
    assert client.get(f"/orders/{o.order_id}", headers={"X-Session-Id": s2["session_id"]}).status_code == 404   # guest visit
    client.post(f"/sessions/{s2['session_id']}/link", headers=h)
    assert client.get(f"/orders/{o.order_id}", headers={"X-Session-Id": s2["session_id"]}).status_code == 200   # same person
