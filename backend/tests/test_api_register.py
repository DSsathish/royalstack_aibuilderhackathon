import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import db

client = TestClient(app)


def bearer(monkeypatch, uid, email, verified=True):
    from app.services import auth
    monkeypatch.setattr(auth.id_token, "verify_firebase_token", lambda *a, **k: {"sub": uid, "email": email, "email_verified": verified})
    return {"Authorization": "Bearer t"}


def register(h, name="Sri Murugan Stores"):
    return client.post("/owner/register", json={"name": name, "city": "Chennai", "languages": ["en", "ta"], "currency": "INR"}, headers=h)


def test_register_creates_store_with_slug_pin_and_membership(monkeypatch):
    import uuid
    uid = "u-" + uuid.uuid4().hex[:8]
    h = bearer(monkeypatch, uid, f"{uid}@example.com")
    res = register(h, f"Sri Murugan Stores {uid[-4:]}")
    assert res.status_code == 200, res.text
    body = res.json()
    sid = body["store"]["store_id"]
    assert sid.startswith("sri-murugan-stores") and len(body["kiosk_pin"]) == 6 and body["kiosk_pin"].isdigit()
    assert body["store"]["owner_emails"] == [f"{uid}@example.com"] and len(body["store"]["floor_map"]) == 4
    me = client.get("/owner/me", headers=h).json()
    assert sid in me["stores"] and me["roles"][sid] == "owner"
    assert db.store_ref(sid).get().to_dict()["kiosk_pin"] == body["kiosk_pin"]


def test_duplicate_name_gets_a_suffix(monkeypatch):
    import uuid
    base = "Dup Shop " + uuid.uuid4().hex[:6]
    a = register(bearer(monkeypatch, "ua-" + base[-6:], "a@example.com"), base).json()["store"]["store_id"]
    b = register(bearer(monkeypatch, "ub-" + base[-6:], "b@example.com"), base).json()["store"]["store_id"]
    assert b == a + "-2"


def test_register_requires_verified_email(monkeypatch):
    assert register(bearer(monkeypatch, "u-nv", "nv@example.com", verified=False)).status_code == 403
    assert client.post("/owner/register", json={"name": "x" * 3}).status_code == 401
    assert register(bearer(monkeypatch, "u-bad", "bad@example.com"), name="ab").status_code == 422


@pytest.fixture
def shop(monkeypatch):
    import uuid
    uid = "owner-" + uuid.uuid4().hex[:8]
    h = bearer(monkeypatch, uid, f"{uid}@example.com")
    sid = register(h, "Patch Shop " + uid[-6:]).json()["store"]["store_id"]
    return sid, h, uid


def test_patch_store_brand_and_aisles(shop):
    sid, h, _ = shop
    res = client.patch(f"/owner/{sid}/store", json={"tagline": "Fresh every day", "greeting": "Vanakkam!", "accent": "#1e8e5a",
                                                     "aisles": ["Staples", "Dairy", "Snacks", "Household", "Fresh", "Pharmacy"]}, headers=h)
    assert res.status_code == 200, res.text
    s = res.json()
    assert s["brand"] == {"accent": "#1e8e5a", "tagline": "Fresh every day", "greeting": "Vanakkam!"}
    assert [a["aisle"] for a in s["floor_map"]] == ["Staples", "Dairy", "Snacks", "Household", "Fresh", "Pharmacy"]
    assert client.patch(f"/owner/{sid}/store", json={"accent": "green"}, headers=h).status_code == 422
    pub = client.get(f"/stores/{sid}").json()
    assert pub["brand"]["accent"] == "#1e8e5a" and "owner_emails" not in pub and "staff_emails" not in pub and "kiosk_pin" not in pub


def test_staff_role_access_matrix(shop, monkeypatch):
    sid, h, _ = shop
    assert client.post(f"/owner/{sid}/staff", json={"email": "Staff@Example.com"}, headers=h).status_code == 200
    sh = bearer(monkeypatch, "staff-1", "staff@example.com")
    me = client.get("/owner/me", headers=sh).json()
    assert me["roles"][sid] == "staff" and sid in me["stores"]
    assert client.post(f"/owner/{sid}/counts", json={"product_id": "nope-nope", "counted": 1}, headers=sh).status_code in (200, 404)
    assert client.get(f"/owner/{sid}/verifications", headers=sh).status_code == 200
    assert client.get(f"/owner/{sid}/overview", headers=sh).status_code == 403
    assert client.get(f"/owner/{sid}/reorders", headers=sh).status_code == 403
    assert client.patch(f"/owner/{sid}/settings", json={"audit_rate": 0.2}, headers=sh).status_code == 403
    assert client.post(f"/owner/{sid}/staff", json={"email": "x@example.com"}, headers=sh).status_code == 403
    h = bearer(monkeypatch, shop[2], f"{shop[2]}@example.com")      # back to the owner's token
    assert client.delete(f"/owner/{sid}/staff/staff@example.com", headers=h).status_code == 200


def test_payments_patch_stores_secret_and_switches_provider(shop, monkeypatch):
    from app.services import payments
    vault = {}
    monkeypatch.setattr(payments, "store_secret", lambda store_id, value: vault.__setitem__(store_id, value))
    monkeypatch.setattr(payments, "secret_for", lambda store_id: vault.get(store_id, ""))
    sid, h, _ = shop
    res = client.patch(f"/owner/{sid}/payments", json={"key_id": "rzp_test_abc", "key_secret": "s3cret"}, headers=h)
    assert res.status_code == 200 and res.json() == {"provider": "razorpay", "key_id": "rzp_test_abc"}
    assert vault[sid] == "s3cret"
    assert client.get(f"/stores/{sid}").json()["payments"] == {"provider": "razorpay", "key_id": "rzp_test_abc"}
    assert client.patch(f"/owner/{sid}/payments", json={}, headers=h).json() == {"provider": "mock", "key_id": ""}


def test_team_listing_and_staff_can_list_inventory(shop, monkeypatch):
    sid, h, uid = shop
    client.post(f"/owner/{sid}/staff", json={"email": "team@example.com"}, headers=h)
    team = client.get(f"/owner/{sid}/team", headers=h).json()
    assert team["staff_emails"] == ["team@example.com"] and team["owner_emails"] == [f"{uid}@example.com"]
    sh = bearer(monkeypatch, "staff-2", "team@example.com")
    assert client.get(f"/owner/{sid}/inventory", headers=sh).status_code == 200
    assert client.get(f"/owner/{sid}/team", headers=sh).status_code == 403
    assert client.patch(f"/owner/{sid}/inventory/some-product", json={"reorder_point": 1}, headers=sh).status_code == 403
