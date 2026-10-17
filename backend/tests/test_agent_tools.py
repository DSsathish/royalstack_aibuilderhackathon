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
    assert set(row) <= {"product_id", "name", "brand", "price", "mrp", "unit", "available", "aisle", "bay"}


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
    assert out == {"ok": False, "error": "out_of_stock"}


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
