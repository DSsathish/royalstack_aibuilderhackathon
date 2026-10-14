from app.domain.models import Inventory, Product, Store


def test_store_defaults():
    s = Store(store_id="demo", name="Demo")
    assert s.currency == "INR"
    assert s.self_checkout_item_limit == 15
    assert s.high_value_threshold == 500.0
    assert s.floor_map == []


def test_product_high_value_derived_from_threshold():
    cheap = Product.from_row(store_id="demo", sku="A1", name="Salt", price=20, mrp=22, threshold=500)
    pricey = Product.from_row(store_id="demo", sku="B2", name="Ghee 1kg", price=650, mrp=700, threshold=500)
    assert cheap.is_high_value is False
    assert pricey.is_high_value is True
    assert cheap.product_id == "demo-a1"


def test_inventory_available():
    inv = Inventory(product_id="demo-a1", store_id="demo", on_hand=5, reserved=2)
    assert inv.available == 3
