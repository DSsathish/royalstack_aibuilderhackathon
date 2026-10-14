import pytest

from app.domain.models import Inventory, Product, Store
from app.services import cart, catalog, checkout, db, inventory, qr, sessions


def put(store_id, sku, price, on_hand):
    p = Product.from_row(store_id=store_id, sku=sku, name=sku.title(), price=price, mrp=price + 10, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand).model_dump())
    return p.product_id


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", self_checkout_item_limit=2).model_dump())
    put(store_id, "salt", 20, 5)
    put(store_id, "rice", 300, 3)
    put(store_id, "oil", 150, 3)
    catalog.invalidate(store_id)
    return store_id


@pytest.fixture
def session_with_cart(shop):
    s = sessions.create(shop, "instore")
    cart.add(shop, s.cart_id, f"{shop}-salt", 2, via="scan", mode="instore")
    cart.add(shop, s.cart_id, f"{shop}-rice", 1, via="scan", mode="instore")
    return s


def test_intent_creates_pending_order_with_server_totals(session_with_cart):
    o = checkout.intent(session_with_cart)
    assert o.status == "pending" and o.payment_provider == "mock"
    assert (o.subtotal, o.savings, o.total) == (340, 30, 340)
    assert [i.product_id for i in o.items] == [f"{session_with_cart.store_id}-salt", f"{session_with_cart.store_id}-rice"]
    assert checkout.get(o.order_id).order_id == o.order_id


def test_intent_rejects_empty_cart(shop):
    with pytest.raises(checkout.CheckoutError, match="empty"):
        checkout.intent(sessions.create(shop, "instore"))


def test_intent_rejects_owner_session(shop):
    s = sessions.create(shop, "owner")
    cart.add(shop, s.cart_id, f"{shop}-salt", 1, via="chat")
    with pytest.raises(checkout.CheckoutError, match="mode"):
        checkout.intent(s)


def test_intent_enforces_item_limit_in_store(shop):
    s = sessions.create(shop, "instore")
    for sku in ("salt", "rice", "oil"):
        cart.add(shop, s.cart_id, f"{shop}-{sku}", 1, via="scan", mode="online")  # bypass add-time limit
    with pytest.raises(checkout.CheckoutError, match="limit"):
        checkout.intent(s)


def test_confirm_commits_stock_and_issues_receipt(session_with_cart):
    shop = session_with_cart.store_id
    o = checkout.intent(session_with_cart)
    paid = checkout.confirm(o.order_id, payment_id="pay_1", signature="mock")
    assert paid.status == "paid" and paid.paid_at and paid.payment_id == "pay_1"
    inv = db.inventory(shop).document(f"{shop}-salt").get().to_dict()
    assert (inv["on_hand"], inv["reserved"]) == (3, 0)
    assert qr.verify(paid.receipt_token)["order_id"] == o.order_id
    assert qr.verify(paid.receipt_token)["count"] == 3
    assert cart.get(shop, session_with_cart.cart_id).status == "checked_out"


def test_confirm_bad_signature_rejected(session_with_cart):
    o = checkout.intent(session_with_cart)
    with pytest.raises(checkout.CheckoutError, match="signature"):
        checkout.confirm(o.order_id, payment_id="pay_1", signature="wrong")
    assert checkout.get(o.order_id).status == "pending"


def test_confirm_is_idempotent(session_with_cart):
    shop = session_with_cart.store_id
    o = checkout.intent(session_with_cart)
    first = checkout.confirm(o.order_id, payment_id="pay_1", signature="mock")
    second = checkout.confirm(o.order_id, payment_id="pay_1", signature="mock")
    assert first.receipt_token == second.receipt_token
    assert db.inventory(shop).document(f"{shop}-salt").get().to_dict()["on_hand"] == 3


def test_confirm_unknown_order(shop):
    with pytest.raises(checkout.CheckoutError, match="order"):
        checkout.confirm("nope", payment_id="p", signature="mock")


def test_razorpay_signature_check():
    from app.config import settings
    settings.razorpay_key_secret = "secret"
    try:
        import hashlib, hmac
        sig = hmac.new(b"secret", b"order_ref|pay_9", hashlib.sha256).hexdigest()
        assert checkout.razorpay_signature_ok("order_ref", "pay_9", sig) is True
        assert checkout.razorpay_signature_ok("order_ref", "pay_9", "bad") is False
    finally:
        settings.razorpay_key_secret = ""
