import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store, Supplier
from app.main import app
from app.services import catalog, db, forecast, reorder

client = TestClient(app)
H = {"X-Test-Uid": "owner-1"}


@pytest.fixture
def shop(store_id, monkeypatch):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", owner_emails=["boss@example.com"]).model_dump())
    db.users().document("owner-1").set({"stores": [store_id]})
    db.suppliers(store_id).document("sup-a").set(Supplier(supplier_id="sup-a", store_id=store_id, name="Metro").model_dump())
    for sku, price, qty in (("milk", 28, 2), ("salt", 20, 50)):
        p = Product.from_row(store_id=store_id, sku=sku, name=sku.title(), price=price, mrp=price, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=qty, reorder_point=5, supplier_id="sup-a").model_dump())
    forecast.put(store_id, f"{store_id}-milk", daily=[8] * 14, avg_daily=8, std_daily=0.5)
    catalog.invalidate(store_id)
    monkeypatch.setattr(reorder, "explain", lambda *a, **k: ("Summary.", {}))
    from app.services import insights
    monkeypatch.setattr(insights, "daily_revenue_history", lambda *a, **k: [])
    return store_id


def test_all_owner_endpoints_require_auth(shop):
    for path in ("overview", "inventory", "reorders", "signals", "loss"):
        assert client.get(f"/owner/{shop}/{path}").status_code == 401, path
    assert client.get(f"/owner/{shop}/overview", headers={"X-Test-Uid": "stranger"}).status_code == 403


def test_me_lists_stores(shop):
    assert client.get("/owner/me", headers=H).json()["stores"] == [shop]


def test_owner_by_email_is_bootstrapped(shop, monkeypatch):
    from app.services import auth
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": "new-uid", "email": "boss@example.com"})
    res = client.get(f"/owner/{shop}/overview", headers={"Authorization": "Bearer t"})
    assert res.status_code == 200
    assert shop in db.users().document("new-uid").get().to_dict()["stores"]
    assert shop in client.get("/owner/me", headers={"Authorization": "Bearer t"}).json()["stores"]


def test_overview_and_inventory(shop):
    ov = client.get(f"/owner/{shop}/overview", headers=H).json()
    assert ov["low_stock"] == 1 and ov["today"]["orders"] == 0 and len(ov["series"]) == 1
    inv = client.get(f"/owner/{shop}/inventory", headers=H).json()
    assert inv[0]["product_id"] == f"{shop}-milk" and inv[0]["status"] == "low" and inv[0]["days_of_cover"] == 0.2


def test_patch_inventory_and_quick_count(shop):
    res = client.patch(f"/owner/{shop}/inventory/{shop}-salt", json={"reorder_point": 12, "reorder_qty": 40}, headers=H)
    assert res.status_code == 200 and res.json()["reorder_point"] == 12
    assert client.post(f"/owner/{shop}/counts", json={"product_id": f"{shop}-salt", "counted": 47}, headers=H).status_code == 200
    loss = client.get(f"/owner/{shop}/loss", headers=H).json()
    assert loss["shrink"][0]["difference"] == -3 and "summary" in loss and loss["settings"]["kiosk_pin"] == "1234"


def test_reorder_flow(shop):
    drafts = client.post(f"/owner/{shop}/reorders/draft", headers=H).json()
    assert len(drafts) == 1 and drafts[0]["lines"][0]["product_id"] == f"{shop}-milk"
    po = drafts[0]["po_id"]
    res = client.post(f"/owner/{shop}/reorders/{po}/approve", json={"qty": {f"{shop}-milk": 120}}, headers=H)
    assert res.status_code == 200 and res.json()["status"] == "approved" and "120" in res.json()["email_text"]
    assert client.post(f"/owner/{shop}/reorders/{po}/reject", json={"reason": "x"}, headers=H).status_code == 409
    assert client.get(f"/owner/{shop}/reorders", headers=H).json()[0]["status"] == "approved"


def test_settings_patch(shop):
    res = client.patch(f"/owner/{shop}/settings", json={"self_checkout_item_limit": 8, "audit_rate": 0.25, "kiosk_pin": "4321"}, headers=H)
    assert res.status_code == 200
    assert db.store_ref(shop).get().to_dict()["self_checkout_item_limit"] == 8
    assert client.patch(f"/owner/{shop}/settings", json={"audit_rate": 5}, headers=H).status_code == 422


def test_signals_endpoint(shop):
    assert client.get(f"/owner/{shop}/signals?days=30", headers=H).json()["not_carried"] == []


def test_forecast_job_requires_key(shop, monkeypatch):
    from app.jobs import forecast as job
    monkeypatch.setattr(job, "run", lambda store_id: {"products": 2, "method": "mocked"})
    assert client.post(f"/jobs/forecast?store_id={shop}").status_code == 401
    res = client.post(f"/jobs/forecast?store_id={shop}", headers={"X-Job-Key": "test-job-key"})
    assert res.status_code == 200 and res.json()["method"] == "mocked"


def test_owner_session_endpoint(shop):
    res = client.post(f"/owner/{shop}/session", headers=H)
    assert res.status_code == 200 and res.json()["mode"] == "owner" and res.json()["user_id"] == "owner-1"
    assert client.post(f"/owner/{shop}/session").status_code == 401
