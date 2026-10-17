from datetime import timedelta

import pytest

from app.domain.models import Inventory, Product, Store, now
from app.services import cart, catalog, checkout, customers, db, points, sessions


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    p = Product.from_row(store_id=store_id, sku="rice", name="Rice", price=300, mrp=300, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=50).model_dump())
    catalog.invalidate(store_id)
    return store_id


def signed_session(store_id, uid="cust-1"):
    s = sessions.create(store_id, "online")
    customers.link(s, uid, "+919999900001")
    return sessions.get(s.session_id)


def pay(store_id, s, qty=1, use_points=0):
    cart.add(store_id, s.cart_id, f"{store_id}-rice", qty, via="chat")
    o = checkout.intent(s, points=use_points)
    return checkout.confirm(o.order_id, payment_id="p", signature="mock")


def test_earn_one_point_per_100_paid(shop):
    s = signed_session(shop)
    o = pay(shop, s, qty=2)                                   # 600 rupees
    assert o.points_earned == 6 and points.balance(shop, "cust-1") == 6
    e = points.ledger(shop, "cust-1")[0]
    assert e["kind"] == "earn" and e["remaining"] == 6 and e["order_id"] == o.order_id
    assert e["expires_at"] > now() + timedelta(days=360)


def test_guest_earns_nothing(shop):
    assert pay(shop, sessions.create(shop, "online")).points_earned == 0


def test_redeem_rules(shop):
    s = signed_session(shop)
    pay(shop, s, qty=2)                                       # 6 points
    points.adjust(shop, "cust-1", 100, "welcome", by="owner-1")
    s2 = signed_session(shop)
    cart.add(shop, s2.cart_id, f"{shop}-rice", 1, via="chat")
    with pytest.raises(checkout.CheckoutError):
        checkout.intent(s2, points=49)                        # below the minimum
    with pytest.raises(checkout.CheckoutError):
        checkout.intent(s2, points=200)                       # above the balance
    o = checkout.intent(s2, points=100)
    assert (o.points_redeemed, o.points_value, o.total) == (100, 100, 200)
    assert points.balance(shop, "cust-1") == 6                # held at intent
    o = checkout.confirm(o.order_id, payment_id="p", signature="mock")
    assert o.points_earned == 2 and points.balance(shop, "cust-1") == 8


def test_redeem_consumes_oldest_first_and_abandoned_intent_is_released(shop):
    s = signed_session(shop)
    points.adjust(shop, "cust-1", 60, "old", by="owner-1")
    points.adjust(shop, "cust-1", 60, "new", by="owner-1")
    cart.add(shop, s.cart_id, f"{shop}-rice", 1, via="chat")
    o1 = checkout.intent(s, points=80)
    rem = {e["reason"]: e["remaining"] for e in points.ledger(shop, "cust-1") if e["kind"] == "adjust"}
    assert rem == {"old": 0, "new": 40} and points.balance(shop, "cust-1") == 40
    o2 = checkout.intent(s, points=50)                        # retry: the first hold is released
    assert points.balance(shop, "cust-1") == 70 and checkout.get(o1.order_id).status == "cancelled"
    assert o2.points_redeemed == 50


def test_guest_cannot_redeem(shop):
    s = sessions.create(shop, "online")
    cart.add(shop, s.cart_id, f"{shop}-rice", 1, via="chat")
    with pytest.raises(checkout.CheckoutError):
        checkout.intent(s, points=50)


def test_expiry_and_adjust_floor(shop):
    s = signed_session(shop)
    pay(shop, s, qty=2)                                       # 6 points
    for d in points.ledger_ref(shop, "cust-1").stream():
        d.reference.update({"expires_at": now() - timedelta(days=1)})
    assert points.expire(shop) == 6
    assert points.balance(shop, "cust-1") == 0
    assert [e["kind"] for e in points.ledger(shop, "cust-1")][0] == "expire"
    with pytest.raises(ValueError):
        points.adjust(shop, "cust-1", -10, "oops", by="owner-1")      # never below zero


def test_stale_pending_redemptions_are_released_by_the_job(shop):
    s = signed_session(shop)
    points.adjust(shop, "cust-1", 100, "welcome", by="owner-1")
    cart.add(shop, s.cart_id, f"{shop}-rice", 1, via="chat")
    o = checkout.intent(s, points=60)
    db.orders().document(o.order_id).update({"created_at": now() - timedelta(days=2)})
    assert points.release_stale(shop) == 1
    assert points.balance(shop, "cust-1") == 100 and checkout.get(o.order_id).status == "cancelled"
