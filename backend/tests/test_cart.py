import pytest

from app.domain.models import Inventory, Product, Store
from app.services import cart, catalog, db, inventory


def put(store_id, sku, name, price, mrp, on_hand):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=mrp, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand).model_dump())
    return p.product_id


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", self_checkout_item_limit=2).model_dump())
    put(store_id, "A", "Salt", 20, 22, 5)
    put(store_id, "B", "Sugar", 50, 55, 1)
    put(store_id, "C", "Rice", 300, 320, 9)
    catalog.invalidate(store_id)
    return store_id


def test_add_reserves_stock_and_computes_totals(shop):
    c = cart.add(shop, f"{shop}-cart1", f"{shop}-a", 2, via="scan")
    assert c.items[0].qty == 2
    assert inventory.available(shop, f"{shop}-a") == 3
    p = cart.pricing(shop, c)
    assert (p.subtotal, p.savings, p.total) == (40, 4, 40)


def test_add_same_product_merges_line(shop):
    cart.add(shop, f"{shop}-cart1", f"{shop}-a", 1, via="scan")
    c = cart.add(shop, f"{shop}-cart1", f"{shop}-a", 1, via="chat")
    assert len(c.items) == 1 and c.items[0].qty == 2


def test_add_out_of_stock_returns_error(shop):
    assert cart.add(shop, f"{shop}-cart1", f"{shop}-b", 2, via="scan") == "out_of_stock"


def test_add_unknown_product(shop):
    assert cart.add(shop, f"{shop}-cart1", f"{shop}-zz", 1, via="scan") == "unknown_product"


def test_item_limit_in_store_mode(shop):
    cart.add(shop, f"{shop}-cart1", f"{shop}-a", 1, via="scan")
    cart.add(shop, f"{shop}-cart1", f"{shop}-c", 1, via="scan")
    assert cart.add(shop, f"{shop}-cart1", f"{shop}-b", 1, via="scan", mode="instore") == "item_limit"
    assert isinstance(cart.add(shop, f"{shop}-cart2", f"{shop}-b", 1, via="scan", mode="online"), cart.Cart)


def test_remove_releases_stock(shop):
    cart.add(shop, f"{shop}-cart1", f"{shop}-a", 2, via="scan")
    c = cart.remove(shop, f"{shop}-cart1", f"{shop}-a")
    assert c.items == []
    assert inventory.available(shop, f"{shop}-a") == 5


def test_get_creates_empty_cart(shop):
    c = cart.get(shop, f"{shop}-fresh")
    assert c.items == [] and c.status == "open"
