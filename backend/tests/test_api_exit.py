import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store, VisionResult
from app.main import app
from app.services import cart, catalog, checkout, db, sessions, vision

client = TestClient(app)


@pytest.fixture
def shop(store_id, monkeypatch):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", kiosk_pin="9876", audit_rate=0).model_dump())
    db.users().document("owner-1").set({"stores": [store_id]})
    p = Product.from_row(store_id=store_id, sku="salt", name="Salt", price=20, mrp=20, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=9).model_dump())
    catalog.invalidate(store_id)
    monkeypatch.setattr(vision, "check_bag", lambda *a, **k: VisionResult(confidence=0.95, skipped=False))
    return store_id


def paid(shop):
    s = sessions.create(shop, "instore")
    cart.add(shop, s.cart_id, f"{shop}-salt", 2, via="scan", mode="instore")
    return checkout.confirm(checkout.intent(s).order_id, payment_id="p", signature="mock")


def test_verify_requires_pin(shop):
    o = paid(shop)
    assert client.post(f"/exit/{shop}/verify", data={"receipt_token": o.receipt_token, "kiosk_id": "k1"}).status_code == 401
    assert client.post(f"/exit/{shop}/verify", data={"receipt_token": o.receipt_token, "kiosk_id": "k1"},
                       headers={"X-Kiosk-Pin": "0000"}).status_code == 401


def test_verify_accepts_full_exit_url_and_returns_summary(shop):
    o = paid(shop)
    url = f"https://app.example/exit/?r={o.receipt_token}"
    res = client.post(f"/exit/{shop}/verify", data={"receipt_token": url, "kiosk_id": "k1", "counted_items": "2"},
                      headers={"X-Kiosk-Pin": "9876"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["verdict"] == "clear" and body["order_summary"]["total"] == 40
    assert body["order_summary"]["items"][0]["name"] == "Salt"


def test_verify_with_bag_image(shop):
    o = paid(shop)
    res = client.post(f"/exit/{shop}/verify", data={"receipt_token": o.receipt_token, "kiosk_id": "k1"},
                      files={"image": ("bag.jpg", b"\xff\xd8jpeg", "image/jpeg")}, headers={"X-Kiosk-Pin": "9876"})
    assert res.status_code == 200 and res.json()["vision"]["confidence"] == 0.95
    assert res.json()["image_hash"]


def test_review_endpoint(shop):
    o = paid(shop)
    v = client.post(f"/exit/{shop}/verify", data={"receipt_token": o.receipt_token, "kiosk_id": "k1", "counted_items": "7"},
                    headers={"X-Kiosk-Pin": "9876"}).json()
    assert v["verdict"] == "flag"
    res = client.post(f"/exit/{shop}/review/{v['verification_id']}", json={"outcome": "cleared", "note": "miscount"},
                      headers={"X-Kiosk-Pin": "9876"})
    assert res.status_code == 200 and res.json()["review_outcome"] == "cleared"
    assert checkout.get(o.order_id).status == "verified"


def test_owner_listing(shop):
    o = paid(shop)
    client.post(f"/exit/{shop}/verify", data={"receipt_token": o.receipt_token, "kiosk_id": "k1"}, headers={"X-Kiosk-Pin": "9876"})
    res = client.get(f"/owner/{shop}/verifications?days=7", headers={"X-Test-Uid": "owner-1"})
    assert res.status_code == 200
    assert res.json()["summary"]["total"] == 1 and res.json()["items"][0]["verdict"] == "clear"
    assert client.get(f"/owner/{shop}/verifications").status_code == 401


def test_pin_lockout_after_repeated_failures(shop):
    from app.api import exit as exit_api
    exit_api._pin_failures.clear()
    for _ in range(exit_api.MAX_PIN_FAILURES):
        client.post(f"/exit/{shop}/verify", data={"receipt_token": "x", "kiosk_id": "k"}, headers={"X-Kiosk-Pin": "0000"})
    res = client.post(f"/exit/{shop}/verify", data={"receipt_token": "x", "kiosk_id": "k"}, headers={"X-Kiosk-Pin": "9876"})
    assert res.status_code == 429
    exit_api._pin_failures.clear()
