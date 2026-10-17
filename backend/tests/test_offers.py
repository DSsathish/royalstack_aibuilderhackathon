from datetime import timedelta

import pytest

from app.domain.models import Cart, CartItem, Inventory, Offer, Product, Store, now
from app.services import cart, catalog, db, offers


def put(store_id, sku, name, price, category):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=price, threshold=500, category=category)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=50).model_dump())


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    put(store_id, "milk", "Milk", 50, "Dairy")
    put(store_id, "curd", "Curd", 40, "Dairy")
    put(store_id, "rice", "Rice", 300, "Staples")
    catalog.invalidate(store_id)
    return store_id


def offer(store_id, **kw):
    return offers.create(store_id, Offer(offer_id="", store_id=store_id, created_by="owner-1", **{"name": "Offer", **kw}))


def basket(store_id, *lines):
    c = Cart(cart_id="c1", store_id=store_id)
    for pid, qty, price in lines:
        c.items.append(CartItem(product_id=pid, name=pid, qty=qty, unit_price=price, mrp=price))
    return c


def test_product_and_category_best_wins_per_line(shop):
    offer(shop, kind="product", product_id=f"{shop}-milk", percent_off=10, name="Milk 10%")
    offer(shop, kind="category", category="Dairy", amount_off=8, name="Dairy 8 off")      # per unit
    c = basket(shop, (f"{shop}-milk", 2, 50), (f"{shop}-curd", 1, 40), (f"{shop}-rice", 1, 300))
    lines, total = offers.apply(shop, c, "guest")
    assert total == 24 and {l.name: l.amount for l in lines} == {"Dairy 8 off": 24}     # 8/unit beats 5/unit on milk


def test_cart_threshold_offer_after_line_discounts(shop):
    offer(shop, kind="cart", min_total=350, amount_off=30, name="30 off above 350")
    offer(shop, kind="cart", min_total=300, percent_off=5, name="5% above 300")
    lines, total = offers.apply(shop, basket(shop, (f"{shop}-rice", 1, 300), (f"{shop}-milk", 1, 50)), "guest")
    assert total == 30 and lines[0].name == "30 off above 350"
    lines, total = offers.apply(shop, basket(shop, (f"{shop}-rice", 1, 300)), "guest")
    assert total == 15 and lines[0].name == "5% above 300"


def test_segment_dates_and_active_gate_offers(shop):
    offer(shop, kind="cart", amount_off=5, segment="vip", name="VIP")
    offer(shop, kind="cart", amount_off=6, segment="signed_in", name="Members")
    offer(shop, kind="cart", amount_off=7, active=False, name="Off")
    offer(shop, kind="cart", amount_off=9, ends_at=now() - timedelta(days=1), name="Expired")
    offer(shop, kind="cart", amount_off=8, starts_at=now() + timedelta(days=1), name="Soon")
    offer(shop, kind="cart", amount_off=1, name="Everyone")
    names = lambda seg: {o.name for o in offers.applicable(shop, seg)}
    assert names("guest") == {"Everyone"}
    assert names("regular") == {"Everyone", "Members"}
    assert names("vip") == {"Everyone", "Members", "VIP"}
    assert offers.apply(shop, basket(shop, (f"{shop}-milk", 1, 50)), "vip")[1] == 6     # one cart offer, the best


def test_discount_never_exceeds_amount(shop):
    offer(shop, kind="product", product_id=f"{shop}-curd", amount_off=100, name="Big")
    offer(shop, kind="cart", amount_off=500, name="Huge")
    assert offers.apply(shop, basket(shop, (f"{shop}-curd", 1, 40)), "guest")[1] == 40


def test_pricing_with_points(shop):
    offer(shop, kind="cart", amount_off=10, name="Ten")
    c = basket(shop, (f"{shop}-rice", 1, 300))
    p = cart.pricing(shop, c, "guest")
    assert (p.subtotal, p.discount_total, p.total) == (300, 10, 290)
    p = cart.pricing(shop, c, "regular", points=1000)
    assert (p.points_redeemed, p.points_value, p.total) == (290, 290, 0)      # capped at the amount due


def test_offer_validation():
    with pytest.raises(ValueError):
        Offer(offer_id="x", store_id="s", name="n", kind="cart", percent_off=95)
    with pytest.raises(ValueError):
        Offer(offer_id="x", store_id="s", name="n", kind="cart")                        # needs a value
    with pytest.raises(ValueError):
        Offer(offer_id="x", store_id="s", name="n", kind="product", percent_off=5)      # needs a product
    with pytest.raises(ValueError):
        Offer(offer_id="x", store_id="s", name="n", kind="cart", percent_off=5, amount_off=5)   # not both
