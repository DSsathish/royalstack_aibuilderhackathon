import pytest

from app.domain.models import Inventory, Location, Product, Store
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


def test_rare_words_outrank_common_ones_and_full_matches_win(store_id, monkeypatch):
    from app.services import gemini
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    for sku, name in (("rin", "Rin Detergent Bar 250g"), ("lux", "Lux Soap Bar 100g"), ("dove", "Dove Cream Bar 75g"),
                      ("amul", "Amul Dark Chocolate 150g"), ("cadbury", "Cadbury Dairy Milk Chocolate Bar 50g")):
        p = Product.from_row(store_id=store_id, sku=sku, name=name, price=50, mrp=50, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=5).model_dump())
    catalog.invalidate(store_id)
    monkeypatch.setattr(gemini, "embed_texts", lambda texts, for_query=False: [])
    names = [h.name for h in catalog.search(store_id, "chocolate bar", k=5)]
    assert names[0] == "Cadbury Dairy Milk Chocolate Bar 50g"          # both words
    assert names[1] == "Amul Dark Chocolate 150g"                       # the rare word beats the common one
    assert names[2:] and all("Bar" in n for n in names[2:])


def test_pack_sizes_do_not_decide_the_ranking(store_id, monkeypatch):
    from app.services import gemini
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    for sku, name in (("milk", "Aavin Toned Milk 500ml"), ("milk1l", "Amul Taaza Toned Milk 1 L"), ("colin", "Colin Glass Cleaner 500ml")):
        p = Product.from_row(store_id=store_id, sku=sku, name=name, price=50, mrp=50, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=5).model_dump())
    catalog.invalidate(store_id)
    monkeypatch.setattr(gemini, "embed_texts", lambda texts, for_query=False: [])
    names = [h.name for h in catalog.search(store_id, "toned milk 500ml", k=3)]
    assert names[:2] == ["Aavin Toned Milk 500ml", "Amul Taaza Toned Milk 1 L"]      # the milks before the cleaner that shares only the size
