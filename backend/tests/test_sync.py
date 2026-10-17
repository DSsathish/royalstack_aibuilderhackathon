import json
import time
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Product, Store, now
from app.main import app
from app.services import cart, catalog, checkout, db, inventory, sessions, sync

client = TestClient(app)
OWNER = {"X-Test-Uid": "owner-1"}


@pytest.fixture(autouse=True)
def mem_secrets(monkeypatch):
    from app.services import secrets
    store: dict[str, str] = {}
    monkeypatch.setattr(secrets, "get", lambda name: store.get(name, ""))
    monkeypatch.setattr(secrets, "put", lambda name, value: store.__setitem__(name, value))
    return store


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    db.users().document("owner-1").set({"stores": [store_id], "roles": {store_id: "owner"}})
    for sku, name, price, on_hand, reserved in (("salt", "Salt", 20, 5, 1), ("rice", "Rice", 300, 1, 0)):
        p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=price, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand, reserved=reserved).model_dump())
    catalog.invalidate(store_id)
    return store_id


def signed(path: str, body: dict, secret: str, ts: str | None = None):
    raw = json.dumps(body).encode()
    ts = ts or str(int(time.time()))
    return client.post(path, content=raw, headers={"Content-Type": "application/json", "X-Sync-Signature": sync.sign(secret, ts, raw), "X-Sync-Timestamp": ts})


def test_inventory_webhook_sets_stock_keeps_reservations_and_dedupes(shop):
    secret = sync.new_secret(shop)
    body = {"event_id": "evt-1", "rows": [{"sku": "salt", "on_hand": 12}, {"sku": "ghost", "on_hand": 3}]}
    res = signed(f"/sync/{shop}/inventory", body, secret)
    assert res.status_code == 200, res.text
    assert res.json()["updated"] == 1 and res.json()["unknown"] == ["ghost"]
    inv = db.inventory(shop).document(f"{shop}-salt").get().to_dict()
    assert inv["on_hand"] == 12 and inv["reserved"] == 1
    assert signed(f"/sync/{shop}/inventory", body, secret).json()["duplicate"] is True
    log = [d.to_dict() for d in db.sync_log(shop).stream()]
    assert any(e["kind"] == "inventory" and e["rows"] == 2 and e["direction"] == "in" for e in log)


def test_bad_signature_stale_timestamp_and_missing_secret_are_rejected(shop):
    body = {"event_id": "e", "rows": []}
    assert signed(f"/sync/{shop}/inventory", body, "nope").status_code == 401            # no secret configured yet
    secret = sync.new_secret(shop)
    assert signed(f"/sync/{shop}/inventory", body, "wrong").status_code == 401
    assert signed(f"/sync/{shop}/inventory", body, secret, ts=str(int(time.time()) - 3600)).status_code == 401
    assert client.post(f"/sync/{shop}/inventory", json=body).status_code == 401           # unsigned
    assert signed(f"/sync/{shop}/inventory", body, secret).status_code == 200


def test_price_in_inventory_rows_updates_catalog_and_version(shop):
    secret = sync.new_secret(shop)
    v0 = db.store_ref(shop).get().to_dict().get("catalog_version", 0)
    signed(f"/sync/{shop}/inventory", {"event_id": "p1", "rows": [{"sku": "salt", "on_hand": 5, "price": 22}]}, secret)
    assert catalog.get_product(shop, f"{shop}-salt").price == 22
    assert db.store_ref(shop).get().to_dict()["catalog_version"] == v0 + 1


def test_products_webhook_upserts_and_pull_returns_snapshot(shop):
    secret = sync.new_secret(shop)
    res = signed(f"/sync/{shop}/products", {"event_id": "c1", "rows": [{"sku": "oil", "name": "Oil 1L", "price": 150, "on_hand": 7, "category": "Staples"}]}, secret)
    assert res.status_code == 200, res.text
    assert res.json()["created"] == 1
    assert catalog.get_product(shop, f"{shop}-oil").name == "Oil 1L"
    assert client.get(f"/sync/{shop}/inventory").status_code == 401
    assert client.get(f"/sync/{shop}/inventory", headers={"Authorization": "Bearer wrong"}).status_code == 401
    rows = {r["sku"]: r for r in client.get(f"/sync/{shop}/inventory", headers={"Authorization": f"Bearer {secret}"}).json()}
    assert rows["oil"]["available"] == 7 and rows["salt"]["on_hand"] == 5 and rows["salt"]["available"] == 4


def test_catalog_cache_reloads_when_another_instance_bumps_version(shop, monkeypatch):
    monkeypatch.setattr(catalog, "VERSION_CHECK_S", 0)
    assert catalog.get_product(shop, f"{shop}-salt").name == "Salt"
    db.products(shop).document(f"{shop}-salt").update({"name": "Rock Salt"})         # written by another instance
    assert catalog.get_product(shop, f"{shop}-salt").name == "Salt"                   # version unchanged: cache serves
    from google.cloud import firestore
    db.store_ref(shop).update({"catalog_version": firestore.Increment(1)})
    assert catalog.get_product(shop, f"{shop}-salt").name == "Rock Salt"


class Resp:
    def __init__(self, status: int, content: bytes = b""):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)


def test_sale_webhook_is_signed_queued_on_failure_and_retried(shop, monkeypatch):
    monkeypatch.setattr(sync, "notify_sale_async", lambda o: None)        # the wiring is covered below; deliver by hand here
    secret = sync.new_secret(shop)
    db.store_ref(shop).update({"sync.webhook_url": "https://shop.example/hook"})
    calls = []
    monkeypatch.setattr(sync.httpx, "post", lambda url, content, headers, timeout: calls.append((url, content, headers)) or Resp(500 if len(calls) == 1 else 200))
    s = sessions.create(shop, "online")
    cart.add(shop, s.cart_id, f"{shop}-salt", 2, via="chat")
    o = checkout.confirm(checkout.intent(s).order_id, payment_id="p", signature="mock")
    sync.notify_sale(o)
    assert len(calls) == 1 and db.sync_outbox(shop).document(o.order_id).get().exists      # failed: queued
    url, raw, headers = calls[0]
    assert url == "https://shop.example/hook" and sync.verify(secret, headers["X-Sync-Timestamp"], raw, headers["X-Sync-Signature"])
    payload = json.loads(raw)
    assert payload["event"] == "sale" and payload["items"][0]["sku"] == "salt" and payload["total"] == 40
    db.sync_outbox(shop).document(o.order_id).update({"next_at": now() - timedelta(minutes=1)})
    assert sync.retry_outbox(shop) == 1
    assert not db.sync_outbox(shop).document(o.order_id).get().exists and len(calls) == 2
    assert any(e["direction"] == "out" and e["ok"] for e in (d.to_dict() for d in db.sync_log(shop).stream()))


def test_no_webhook_url_means_nothing_is_sent(shop, monkeypatch):
    monkeypatch.setattr(sync.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not post")))
    s = sessions.create(shop, "online")
    cart.add(shop, s.cart_id, f"{shop}-salt", 1, via="chat")
    o = checkout.confirm(checkout.intent(s).order_id, payment_id="p", signature="mock")
    sync.notify_sale(o)
    assert list(db.sync_outbox(shop).stream()) == []


def test_confirm_triggers_the_notification(shop, monkeypatch):
    sent = []
    monkeypatch.setattr(sync, "notify_sale_async", lambda o: sent.append(o.order_id))
    s = sessions.create(shop, "online")
    cart.add(shop, s.cart_id, f"{shop}-salt", 1, via="chat")
    o = checkout.confirm(checkout.intent(s).order_id, payment_id="p", signature="mock")
    assert sent == [o.order_id]


def test_feed_pull_imports_csv_and_schedule_respects_interval(shop, monkeypatch):
    db.store_ref(shop).update({"sync.feed_url": "https://docs.example/pub?output=csv",
                               "sync.feed_mapping": {"sku": "SKU", "name": "Item", "price": "Rate", "on_hand": "Stock"}})
    csv = b"SKU,Item,Rate,Stock\nsalt,Salt,21,30\ntea,Tea 250g,90,4\n"
    monkeypatch.setattr(sync.httpx, "get", lambda url, timeout, follow_redirects: Resp(200, csv))
    out = sync.pull_feed(shop)
    assert (out["created"], out["updated"]) == (1, 1), out
    assert catalog.get_product(shop, f"{shop}-tea").price == 90
    assert inventory.available(shop, f"{shop}-salt") == 29                                # on_hand 30, reserved 1 kept
    assert db.store_ref(shop).get().to_dict()["sync"]["last_pull_at"]
    assert sync.run_scheduled()["pulled"] == 0                                             # just pulled, not due
    db.store_ref(shop).update({"sync.last_pull_at": now() - timedelta(hours=1)})
    assert sync.run_scheduled()["pulled"] >= 1


def test_owner_sync_settings_secret_log_and_public_store(shop):
    assert client.get(f"/owner/{shop}/sync", headers={"X-Test-Uid": "stranger"}).status_code == 403
    assert client.patch(f"/owner/{shop}/sync", json={"webhook_url": "http://insecure.example/x"}, headers=OWNER).status_code == 422
    res = client.patch(f"/owner/{shop}/sync", json={"webhook_url": "https://shop.example/hook", "feed_every_min": 30}, headers=OWNER)
    assert res.status_code == 200, res.text
    assert res.json()["settings"]["feed_every_min"] == 30
    secret = client.post(f"/owner/{shop}/sync/secret", headers=OWNER).json()["secret"]
    assert len(secret) == 64
    body = client.get(f"/owner/{shop}/sync", headers=OWNER).json()
    assert body["settings"]["has_secret"] is True and secret not in json.dumps(body)
    assert body["endpoints"]["inventory"].endswith(f"/sync/{shop}/inventory")
    assert "sync" not in client.get(f"/stores/{shop}").json()
    assert any(e.to_dict()["action"] == "sync_secret_rotated" for e in db.audit(shop).stream())


def test_owner_test_event_and_pull_now(shop, monkeypatch):
    sync.new_secret(shop)
    db.store_ref(shop).update({"sync.webhook_url": "https://shop.example/hook"})
    monkeypatch.setattr(sync.httpx, "post", lambda url, content, headers, timeout: Resp(200))
    res = client.post(f"/owner/{shop}/sync/test", headers=OWNER)
    assert res.status_code == 200 and res.json()["ok"] is True
    assert client.post(f"/owner/{shop}/sync/pull", headers=OWNER).json()["skipped"] == "no feed_url"


def test_products_webhook_applies_csv_bounds(shop):
    secret = sync.new_secret(shop)
    res = signed(f"/sync/{shop}/products", {"event_id": "neg", "rows": [{"sku": "bad", "name": "Bad", "price": -50, "on_hand": -3}, {"name": "No sku", "price": 5, "on_hand": 1}]}, secret)
    assert res.status_code == 200 and res.json()["created"] == 0 and len(res.json()["errors"]) == 2
    assert catalog.get_product(shop, f"{shop}-bad") is None


def test_failed_apply_is_not_remembered_as_processed(shop, monkeypatch):
    secret = sync.new_secret(shop)
    body = {"event_id": "flaky", "rows": [{"sku": "salt", "on_hand": 9}]}
    real = sync.apply_inventory
    monkeypatch.setattr(sync, "apply_inventory", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("firestore hiccup")))
    assert signed(f"/sync/{shop}/inventory", body, secret).status_code == 500
    monkeypatch.setattr(sync, "apply_inventory", real)
    res = signed(f"/sync/{shop}/inventory", body, secret)                        # the sender's retry lands
    assert res.status_code == 200 and res.json()["duplicate"] is False and res.json()["updated"] == 1
    assert any(e["ok"] is False for e in (d.to_dict() for d in db.sync_log(shop).stream()))


def test_rows_cap_is_enforced(shop):
    secret = sync.new_secret(shop)
    body = {"event_id": "big", "rows": [{"sku": "salt", "on_hand": 1}] * (sync.MAX_ROWS + 1)}
    assert signed(f"/sync/{shop}/inventory", body, secret).status_code == 422


def test_feed_redirect_off_https_is_refused(shop, monkeypatch):
    db.store_ref(shop).update({"sync.feed_url": "https://docs.example/pub", "sync.feed_mapping": {"sku": "SKU", "name": "Item", "price": "Rate", "on_hand": "Stock"}})

    class Redirect(Resp):
        headers = {"location": "http://10.0.0.5/internal.csv"}
    monkeypatch.setattr(sync.httpx, "get", lambda url, timeout, follow_redirects: Redirect(302))
    assert "https" in sync.pull_feed(shop)["error"]


def test_outbox_gives_up_after_six_attempts(shop, monkeypatch):
    sync.new_secret(shop)
    db.sync_outbox(shop).document("o9").set({"key": "o9", "url": "https://shop.example/hook", "payload": "{}", "attempts": 5,
                                             "next_at": now() - timedelta(minutes=1), "created_at": now(), "last_error": "", "dead": False})
    monkeypatch.setattr(sync.httpx, "post", lambda url, content, headers, timeout: Resp(503))
    assert sync.retry_outbox(shop) == 0
    e = db.sync_outbox(shop).document("o9").get().to_dict()
    assert e["attempts"] == 6 and e["dead"] is True
    assert sync.retry_outbox(shop) == 0                                            # dead entries are left alone
