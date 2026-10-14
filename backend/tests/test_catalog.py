import pytest

from app.domain.models import Inventory, Location, Product
from app.services import catalog, db


def put(store_id, sku, name, *, price=10, on_hand=5, tags=(), brand="", category="", aisle="A1"):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, threshold=500,
                         barcode=f"890{abs(hash(sku)) % 10**10:010d}", tags=list(tags),
                         brand=brand, category=category)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand).model_dump())
    db.locations(store_id).document(p.product_id).set(
        Location(product_id=p.product_id, store_id=store_id, aisle=aisle, bay=2).model_dump())
    return p


@pytest.fixture
def shop(store_id):
    put(store_id, "MILK1", "Aavin Toned Milk 500ml", brand="Aavin", category="Dairy",
        tags=["milk", "பால்", "दूध"], aisle="A2")
    put(store_id, "ATTA1", "Aashirvaad Atta 5kg", brand="Aashirvaad", category="Staples", tags=["atta", "wheat flour"])
    put(store_id, "SOYA1", "Soya Milk 1L", brand="Sofit", category="Dairy", tags=["soya", "milk"], on_hand=0)
    catalog.invalidate(store_id)
    return store_id


def test_get_product_joins_stock_and_location(shop):
    v = catalog.get_product(shop, f"{shop}-milk1")
    assert v.name.startswith("Aavin")
    assert v.available == 5
    assert v.location.aisle == "A2"


def test_get_product_missing_returns_none(shop):
    assert catalog.get_product(shop, "nope") is None


def test_get_by_barcode(shop):
    p = db.products(shop).document(f"{shop}-atta1").get().to_dict()
    v = catalog.get_by_barcode(shop, p["barcode"])
    assert v.product_id == f"{shop}-atta1"


def test_keyword_search_ranks_name_match_first(shop):
    hits = catalog.search(shop, "aashirvaad atta")
    assert hits[0].product_id == f"{shop}-atta1"


def test_search_matches_tamil_alias(shop):
    hits = catalog.search(shop, "பால்")
    assert hits and hits[0].product_id == f"{shop}-milk1"


def test_search_records_not_carried_signal(shop):
    assert catalog.search(shop, "qwertyuiop") == []
    sigs = [d.to_dict() for d in db.demand_signals(shop).stream()]
    assert any(s["type"] == "not_carried" and s["query_text"] == "qwertyuiop" for s in sigs)


def test_search_records_out_of_stock_signal(shop):
    catalog.search(shop, "soya")
    sigs = [d.to_dict() for d in db.demand_signals(shop).stream()]
    assert any(s["type"] == "out_of_stock" and s["matched_product_id"] == f"{shop}-soya1" for s in sigs)


def test_search_respects_k(shop):
    assert len(catalog.search(shop, "milk", k=1)) == 1
