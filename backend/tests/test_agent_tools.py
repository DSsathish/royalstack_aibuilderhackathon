"""Tools are plain functions; call them with a fake ToolContext carrying session state."""

from types import SimpleNamespace

import pytest

from app.agent import tools
from app.domain.models import Inventory, Location, Product, Store
from app.services import catalog, db


def put(store_id, sku, name, price, on_hand, *, subcategory="", substitutes=(), aisle="A1", bay=1):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=price + 5, threshold=500,
                         subcategory=subcategory, substitutes=[f"{store_id}-{s}" for s in substitutes], tags=[name.lower()])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand, reorder_point=5, supplier_id="sup-x").model_dump())
    db.locations(store_id).document(p.product_id).set(
        Location(product_id=p.product_id, store_id=store_id, aisle=aisle, bay=bay, shelf=2, side="right", x=100, y=200).model_dump())
    return p.product_id


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    put(store_id, "milk", "Toned Milk", 28, 10, subcategory="Milk", aisle="A2", bay=3)
    put(store_id, "soya", "Soya Milk", 110, 0, subcategory="Plant milk", substitutes=("almond",))
    put(store_id, "almond", "Almond Milk", 230, 4, subcategory="Plant milk")
    put(store_id, "oat", "Oat Milk", 250, 0, subcategory="Plant milk")
    put(store_id, "salt", "Salt", 20, 2, subcategory="Salt")
    catalog.invalidate(store_id)
    return store_id


def ctx(store_id, mode="instore", cart_id="c1"):
    return SimpleNamespace(state={"store_id": store_id, "mode": mode, "cart_id": f"{store_id}-{cart_id}", "session_id": "s1"})


def test_search_products_returns_compact_rows_and_signal(shop):
    out = tools.search_products("toned milk", tool_context=ctx(shop))
    assert out["signal"] == "found"
    row = out["products"][0]
    assert row["product_id"] == f"{shop}-milk" and row["available"] == 10 and row["aisle"] == "A2"
    assert set(row) <= {"product_id", "name", "brand", "price", "mrp", "unit", "available", "in_stock", "stock_note", "pack", "aisle", "bay"}


def test_search_products_not_carried(shop):
    assert tools.search_products("qwertyzz", tool_context=ctx(shop))["signal"] == "not_carried"


def test_get_product_includes_substitutes_and_location(shop):
    out = tools.get_product(f"{shop}-soya", tool_context=ctx(shop))
    assert out["substitutes"] == [f"{shop}-almond"] and out["location"]["aisle"] == "A1"


def test_get_product_unknown(shop):
    assert tools.get_product(f"{shop}-nope", tool_context=ctx(shop)) == {"error": "unknown_product"}


def test_suggest_substitutes_uses_list_then_same_subcategory_in_stock(shop):
    out = tools.suggest_substitutes(f"{shop}-soya", tool_context=ctx(shop))
    ids = [p["product_id"] for p in out["products"]]
    assert ids[0] == f"{shop}-almond"
    assert f"{shop}-oat" not in ids  # out of stock
    assert f"{shop}-soya" not in ids


def test_navigate_to_gives_directions(shop):
    out = tools.navigate_to(f"{shop}-milk", tool_context=ctx(shop))
    assert out["aisle"] == "A2" and out["bay"] == 3 and out["side"] == "right"
    assert "Aisle A2" in out["directions"] and "bay 3" in out["directions"]


def test_add_view_remove_cart(shop):
    c = ctx(shop)
    out = tools.add_to_cart(f"{shop}-milk", 2, tool_context=c)
    assert out["ok"] and out["cart"]["count"] == 2 and out["cart"]["total"] == 56
    assert tools.view_cart(tool_context=c)["cart"]["items"][0]["name"] == "Toned Milk"
    assert tools.remove_from_cart(f"{shop}-milk", tool_context=c)["cart"]["count"] == 0


def test_add_to_cart_out_of_stock_error(shop):
    out = tools.add_to_cart(f"{shop}-soya", 1, tool_context=ctx(shop))
    assert out["ok"] is False and out["error"] == "out_of_stock" and out["alternatives"]


def test_start_checkout_summarises_cart(shop):
    c = ctx(shop)
    tools.add_to_cart(f"{shop}-salt", 1, tool_context=c)
    out = tools.start_checkout(tool_context=c)
    assert out["ok"] and out["total"] == 20 and out["cart_id"] == f"{shop}-c1"


def test_start_checkout_empty_cart(shop):
    assert tools.start_checkout(tool_context=ctx(shop, cart_id="empty")) == {"ok": False, "error": "empty_cart"}


def test_get_low_stock(shop):
    out = tools.get_low_stock(tool_context=ctx(shop, mode="owner"))
    ids = {i["product_id"] for i in out["items"]}
    assert {f"{shop}-soya", f"{shop}-oat", f"{shop}-salt", f"{shop}-almond"} <= ids
    assert f"{shop}-milk" not in ids


def test_record_demand_signal_writes_agent_sourced_signal(shop):
    assert tools.record_demand_signal("oat milk", tool_context=ctx(shop)) == {"ok": True}
    sigs = [d.to_dict() for d in db.demand_signals(shop).stream()]
    assert any(s["query_text"] == "oat milk" and s["type"] == "not_carried" and s["source"] == "agent" for s in sigs)


def test_search_found_records_no_automatic_signal(shop):
    tools.search_products("toned milk", tool_context=ctx(shop))
    assert [d.to_dict() for d in db.demand_signals(shop).stream()] == []


def test_mode_gating_table():
    names = {m: {t.__name__ for t in ts} for m, ts in tools.TOOLS_BY_MODE.items()}
    assert "navigate_to" in names["instore"] and "navigate_to" not in names["online"]
    assert "add_to_cart" not in names["owner"] and "get_low_stock" in names["owner"]
    assert "get_low_stock" not in names["instore"]
    assert "search_products" in names["instore"] & names["online"] & names["owner"]


def test_owner_tools_forecast_and_drafts(shop, monkeypatch):
    from app.services import forecast, reorder
    monkeypatch.setattr(reorder, "explain", lambda *a, **k: ("s", {}))
    forecast.put(shop, f"{shop}-milk", daily=[5] * 14, avg_daily=5, std_daily=1)
    out = tools.forecast_demand(tool_context=ctx(shop, mode="owner"), product_id=f"{shop}-milk", horizon_days=3)
    assert out["avg_daily"] == 5 and len(out["daily"]) == 3
    assert tools.forecast_demand(tool_context=ctx(shop, mode="owner"))["top"][0]["product_id"] == f"{shop}-milk"
    drafts = tools.draft_purchase_order(tool_context=ctx(shop, mode="owner"))["drafts"]
    assert drafts and all("po_id" in d for d in drafts)
    assert "exits" in tools.get_anomalies(tool_context=ctx(shop, mode="owner"))
    names = {t.__name__ for t in tools.TOOLS_BY_MODE["owner"]}
    assert {"forecast_demand", "draft_purchase_order", "get_anomalies"} <= names


def test_add_to_cart_resolves_a_name_when_the_id_is_unknown(shop):
    out = tools.add_to_cart("toned milk", 1, tool_context=ctx(shop))
    assert out["ok"] and out["cart"]["items"][0]["product_id"] == f"{shop}-milk" and out["resolved_from"] == "toned milk"
    out = tools.add_to_cart("india-gate-basmati-rice-5kg", 1, tool_context=ctx(shop))
    assert out == {"ok": False, "error": "unknown_product"}      # nothing matches: still an honest error


def test_instore_tools_cannot_add_to_cart_but_online_can():
    names = {m: {t.__name__ for t in ts} for m, ts in tools.TOOLS_BY_MODE.items()}
    assert "add_to_cart" not in names["instore"] and "add_to_cart" in names["online"]
    assert "navigate_to" in names["instore"]


def test_add_to_cart_accepts_snake_case_and_sku(shop):
    out = tools.add_to_cart("toned_milk", 1, tool_context=ctx(shop))                 # snake_case guess at an id
    assert out["ok"] and out["cart"]["items"][0]["product_id"] == f"{shop}-milk"
    out = tools.add_to_cart("MILK", 1, tool_context=ctx(shop, cart_id="c2"))         # the SKU echoed back
    assert out["ok"] and out["resolved_from"] == "MILK"


def test_pack_size_parsing():
    assert tools.pack_size("India Gate Basmati Rice 5kg") == {"size": 5, "unit": "kg"}
    assert tools.pack_size("Amul Taaza Toned Milk 500 ml") == {"size": 500, "unit": "ml"}
    assert tools.pack_size("Tata Salt 1 Kg") == {"size": 1, "unit": "kg"}
    assert tools.pack_size("Maggi Noodles 12 x 70 g") == {"size": 840, "unit": "g"}
    assert tools.pack_size("Fortune Sunflower Oil 1L") == {"size": 1, "unit": "l"}
    assert tools.pack_size("Dolo 650 15 tablets") == {"size": 15, "unit": "pc"}
    assert tools.pack_size("Toothbrush") is None


def test_search_rows_state_stock_plainly_and_carry_alternatives(shop):
    out = tools.search_products("plant milk", tool_context=ctx(shop))
    rows = {r["name"]: r for r in out["products"]}
    assert rows["Soya Milk"]["in_stock"] is False and rows["Soya Milk"]["stock_note"] == "out of stock"
    assert rows["Almond Milk"]["in_stock"] is True and rows["Almond Milk"]["stock_note"] == "in stock"
    assert [a["name"] for a in rows["Soya Milk"]["alternatives"]] == ["Almond Milk"]        # listed substitute, in stock
    assert "alternatives" not in rows["Almond Milk"]
    assert out["out_of_stock"] == ["Soya Milk", "Oat Milk"] or set(out["out_of_stock"]) == {"Soya Milk", "Oat Milk"}
    salt = tools.search_products("salt", tool_context=ctx(shop))["products"][0]
    assert salt["stock_note"] == "only 2 left"


def test_add_to_cart_reports_insufficient_stock_with_what_is_left(shop):
    out = tools.add_to_cart(f"{shop}-salt", 5, tool_context=ctx(shop, mode="online"))
    assert out == {"ok": False, "error": "insufficient_stock", "name": "Salt", "available": 2, "requested": 5}
    out = tools.add_to_cart(f"{shop}-soya", 1, tool_context=ctx(shop, mode="online"))
    assert out["ok"] is False and out["error"] == "out_of_stock" and [a["name"] for a in out["alternatives"]] == ["Almond Milk"]


def test_suggest_substitutes_falls_back_to_the_category(shop):
    put(shop, "ghee", "Cow Ghee 500 ml", 300, 0, subcategory="")
    db.products(shop).document(f"{shop}-ghee").update({"category": "Dairy"})
    put(shop, "butter", "Butter 100 g", 60, 7, subcategory="")
    db.products(shop).document(f"{shop}-butter").update({"category": "Dairy"})
    catalog.invalidate(shop)
    out = tools.suggest_substitutes(f"{shop}-ghee", tool_context=ctx(shop))
    assert [p["name"] for p in out["products"]] == ["Butter 100 g"]


def test_pet_products_only_answer_pet_queries(shop):
    put(shop, "parleg", "Parle-G Biscuits", 10, 20, subcategory="Biscuits")
    put(shop, "dogbis", "Pedigree Dog Biscuits", 120, 8, subcategory="Pet Food")
    put(shop, "petmilk", "Pet Milk Replacer", 300, 5, subcategory="Pet Food")
    catalog.invalidate(shop)
    names = lambda q: [p["name"] for p in tools.search_products(q, tool_context=ctx(shop))["products"]]
    assert names("biscuits") == ["Parle-G Biscuits"]
    assert names("dog biscuits") == ["Pedigree Dog Biscuits"]
    assert "Pet Milk Replacer" not in names("milk")
    out = tools.search_products("soya milk", tool_context=ctx(shop))["products"][0]      # out of stock: alternatives stay with people's products
    assert out["name"] == "Soya Milk" and all(a["name"] != "Pet Milk Replacer" for a in out["alternatives"])


def test_navigate_speaks_block_kind_and_floor(shop):
    db.store_ref(shop).update({"floor_map": [{"aisle": "A2", "x": 80, "y": 80, "w": 90, "h": 420, "floor": 1, "kind": "aisle"},
                                             {"aisle": "Dairy", "x": 880, "y": 80, "w": 90, "h": 200, "floor": 2, "kind": "chiller"}]})
    db.locations(shop).document(f"{shop}-milk").update({"aisle": "Dairy", "bay": 2})
    catalog.invalidate(shop)
    out = tools.navigate_to(f"{shop}-milk", tool_context=ctx(shop))
    assert out["kind"] == "chiller" and out["floor"] == 2 and out["directions"].startswith("Chiller Dairy, bay 2") and "first floor" in out["directions"]
    out = tools.navigate_to(f"{shop}-salt", tool_context=ctx(shop))
    assert out["directions"].startswith("Aisle A1") and "floor" not in out["directions"]


def test_product_facts_tool_resolves_the_product_and_passes_language(shop, monkeypatch):
    from app.agent import tools
    from app.services import facts
    seen = {}
    monkeypatch.setattr(facts, "lookup", lambda store_id, session_id, q, product, language: seen.update(q=q, product=product, language=language) or {"ok": True})
    c = ctx(shop); c.state["language"] = "ta"
    assert tools.product_facts("What is in it?", "Toned Milk", tool_context=c) == {"ok": True}
    assert seen["product"].name == "Toned Milk" and seen["language"] == "ta"
    tools.product_facts("What is A2 milk?", "", tool_context=c)
    assert seen["product"] is None


def test_list_category_lists_a_whole_section(shop):
    out = tools.list_category("plant milks", tool_context=ctx(shop))
    assert out["matched_by"] == "section" and out["category"] == "Plant milk"
    assert (out["total"], out["in_stock"], out["more"]) == (3, 1, 0) and [r["Product"] for r in out["rows"]] == ["Almond Milk"]
    assert out["columns"] == ["Product", "Price", "Stock"] and out["rows"][0]["Price"] == "₹230"
    full = tools.list_category("plant milk", in_stock_only=False, tool_context=ctx(shop))
    assert [r["Product"] for r in full["rows"]] == ["Almond Milk", "Oat Milk", "Soya Milk"] and full["rows"][1]["Stock"] == "out of stock"
    assert tools.list_category("milk", tool_context=ctx(shop))["total"] == 4          # Milk and Plant milk sections
    assert tools.list_category("milk", limit=1, tool_context=ctx(shop))["more"] == 1
    assert tools.list_category("shoes", tool_context=ctx(shop))["signal"] == "not_carried"


def test_list_category_infers_the_section_from_a_search_in_another_language(shop, monkeypatch):
    from app.services import catalog
    plant = [catalog.get_by_sku(shop, s) for s in ("soya", "almond", "oat")]
    monkeypatch.setattr(catalog, "search", lambda store_id, q, k=6: plant if q == "தாவர பால்" else [])
    out = tools.list_category("தாவர பால்", tool_context=ctx(shop))             # "plant milk" in Tamil
    assert out["matched_by"] == "section" and out["category"] == "Plant milk" and out["total"] == 3
    none = tools.list_category("ஷூ", tool_context=ctx(shop))                      # nothing like it in the shop
    assert none["total"] == 0 and "do not say it is out of stock" in none["note"]
