import pytest

from app.domain.models import Inventory, Product, Store, VisionResult
from app.services import cart, catalog, checkout, db, qr, sessions, verification, vision


def put(store_id, sku, price, on_hand=10):
    p = Product.from_row(store_id=store_id, sku=sku, name=sku.title(), price=price, mrp=price, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand).model_dump())


@pytest.fixture
def shop(store_id, monkeypatch):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", self_checkout_item_limit=5, audit_rate=0.0).model_dump())
    put(store_id, "salt", 20); put(store_id, "rice", 300); put(store_id, "ghee", 650)
    catalog.invalidate(store_id)
    monkeypatch.setattr(vision, "check_bag", lambda *a, **k: VisionResult(confidence=0.9, skipped=False))
    return store_id


def paid_order(shop, *skus):
    s = sessions.create(shop, "instore")
    for sku in skus:
        cart.add(shop, s.cart_id, f"{shop}-{sku}", 1, via="scan", mode="instore")
    o = checkout.intent(s)
    return checkout.confirm(o.order_id, payment_id="p", signature="mock")


def test_clear_exit(shop):
    o = paid_order(shop, "salt", "rice")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=2, kiosk_id="k1")
    assert v.verdict == "clear" and v.reasons == []
    assert v.layers.receipt_ok and v.layers.order_ok and v.layers.count_ok and v.layers.limit_ok
    assert checkout.get(o.order_id).status == "verified"


def test_receipt_is_single_use(shop):
    o = paid_order(shop, "salt")
    verification.verify_exit(shop, o.receipt_token, image=None, counted_items=None, kiosk_id="k1")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=None, kiosk_id="k1")
    assert v.verdict == "flag" and any("already" in r for r in v.reasons)


def test_invalid_token_flags(shop):
    v = verification.verify_exit(shop, "nope.nope", image=None, counted_items=None, kiosk_id="k1")
    assert v.verdict == "flag" and v.layers.receipt_ok is False


def test_token_for_other_store_flags(shop):
    o = paid_order(shop, "salt")
    v = verification.verify_exit("other-store", o.receipt_token, image=None, counted_items=None, kiosk_id="k1")
    assert v.verdict == "flag"


def test_count_mismatch_flags(shop):
    o = paid_order(shop, "salt", "rice")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=5, kiosk_id="k1")
    assert v.verdict == "flag" and v.layers.count_ok is False


def test_count_within_tolerance_is_ok(shop):
    o = paid_order(shop, "salt", "rice")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=3, kiosk_id="k1")
    assert v.layers.count_ok is True


def test_high_value_item_is_spot_check(shop):
    o = paid_order(shop, "ghee")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=None, kiosk_id="k1")
    assert v.verdict == "spot_check" and v.layers.high_value == [f"{shop}-ghee"]
    assert checkout.get(o.order_id).status == "verified"


def test_random_audit_rate(shop):
    db.store_ref(shop).update({"audit_rate": 0.3})
    hits = sum(verification.random_audit(shop) for _ in range(600))
    assert 0.24 < hits / 600 < 0.36


def test_vision_low_confidence_flags(shop, monkeypatch):
    monkeypatch.setattr(vision, "check_bag", lambda *a, **k: VisionResult(confidence=0.2, unexpected_items=["whisky bottle"], skipped=False))
    o = paid_order(shop, "salt")
    v = verification.verify_exit(shop, o.receipt_token, image=(b"jpegbytes", "image/jpeg"), counted_items=None, kiosk_id="k1")
    assert v.verdict == "flag" and "whisky bottle" in " ".join(v.reasons)
    assert v.image_hash and v.vision and v.vision.confidence == 0.2


def test_vision_failure_does_not_block(shop, monkeypatch):
    monkeypatch.setattr(vision, "check_bag", lambda *a, **k: VisionResult(skipped=True))
    o = paid_order(shop, "salt")
    v = verification.verify_exit(shop, o.receipt_token, image=(b"x", "image/jpeg"), counted_items=None, kiosk_id="k1")
    assert v.verdict == "clear" and v.vision.skipped is True


def test_review_issue_confirmed_keeps_flag(shop):
    o = paid_order(shop, "salt", "rice")
    v = verification.verify_exit(shop, o.receipt_token, image=None, counted_items=9, kiosk_id="k1")
    r = verification.review(shop, v.verification_id, outcome="issue_confirmed", by="staff-1", note="extra items")
    assert r.review_outcome == "issue_confirmed" and checkout.get(o.order_id).status == "flagged"
    r2 = verification.review(shop, v.verification_id, outcome="cleared", by="staff-1", note="")
    assert checkout.get(o.order_id).status == "verified"


def test_summary_counts(shop):
    paid = [paid_order(shop, "salt") for _ in range(3)]
    for o in paid:
        verification.verify_exit(shop, o.receipt_token, image=None, counted_items=None, kiosk_id="k1")
    verification.verify_exit(shop, "bad.token", image=None, counted_items=None, kiosk_id="k1")
    s = verification.summary(shop, days=7)
    assert s["total"] == 4 and s["clear"] == 3 and s["flag"] == 1
    assert s["flag_rate"] == 0.25


def test_concurrent_exits_on_one_receipt_only_one_clears(shop, monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(vision, "check_bag", lambda *a, **k: (time.sleep(0.5), VisionResult(confidence=0.9, skipped=False))[1])
    o = paid_order(shop, "salt")
    run = lambda _: verification.verify_exit(shop, o.receipt_token, image=(b"x", "image/jpeg"), counted_items=None, kiosk_id="k")
    with ThreadPoolExecutor(max_workers=2) as pool:
        verdicts = [v.verdict for v in pool.map(run, range(2))]
    assert sorted(verdicts) == ["clear", "flag"]
