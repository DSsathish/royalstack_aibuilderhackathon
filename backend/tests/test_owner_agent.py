"""The owner agent: its own prompt, full-access tools, and confirmation in code before anything changes."""

from types import SimpleNamespace

import pytest

from app.agent import live, owner_tools as ot, prompts, tools
from app.domain.models import Customer, Inventory, Location, Product, Store
from app.services import catalog, db, offers, points


def put(store_id, sku, name, price, on_hand, *, category="", aisle="A1"):
    p = Product.from_row(store_id=store_id, sku=sku, name=name, price=price, mrp=price + 10, threshold=500, category=category, barcode=f"890{abs(hash(sku)) % 10**10:010d}")
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=on_hand, reorder_point=5, reorder_qty=20).model_dump())
    db.locations(store_id).document(p.product_id).set(Location(product_id=p.product_id, store_id=store_id, aisle=aisle).model_dump())
    return p.product_id


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S", floor_map=[{"aisle": "A1", "x": 80, "y": 80, "w": 90, "h": 420}, {"aisle": "Dairy", "x": 230, "y": 80, "w": 90, "h": 420}]).model_dump())
    put(store_id, "milk", "Toned Milk 500ml", 28, 2, category="Dairy")
    put(store_id, "rice", "Ponni Rice 5kg", 420, 30, category="Staples")
    put(store_id, "ghee", "Cow Ghee 500ml", 650, 0, category="Dairy")
    db.customers(store_id).document("c1").set(Customer(uid="c1", store_id=store_id, phone_last4="1234", name="Priya", visits=6, spend=7000, segment="vip").model_dump())
    catalog.invalidate(store_id)
    return store_id


def ctx(store_id):
    return SimpleNamespace(state={"store_id": store_id, "mode": "owner", "cart_id": "c", "session_id": "s", "user_id": "owner-1"})


def test_owner_prompt_and_tool_set_are_separate():
    assert "operations assistant" in prompts.for_mode("owner") and "scan it to add" not in prompts.for_mode("owner")
    names = {t.__name__ for t in tools.TOOLS_BY_MODE["owner"]}
    assert {"store_snapshot", "find_products", "create_offer", "approve_purchase_order", "sync_status"} <= names
    assert not {"add_to_cart", "start_checkout", "navigate_to", "get_offers"} & names
    assert "store_snapshot" not in {t.__name__ for t in tools.TOOLS_BY_MODE["instore"] + tools.TOOLS_BY_MODE["online"]}
    assert len(live.declarations("owner")) == len(tools.TOOLS_BY_MODE["owner"])     # every argument type is declarable


def test_snapshot_and_product_search(shop):
    snap = ot.store_snapshot(ctx(shop))
    assert snap["out_of_stock"] == 1 and snap["low_stock"] >= 1 and snap["signed_in_customers"] == 1
    assert any("out of stock" in a for a in snap["attention"])
    out = ot.find_products("", ctx(shop), status="out")
    assert [r["name"] for r in out["rows"]] == ["Cow Ghee 500ml"] and out["columns"][0] == "name"
    assert ot.find_products("rice", ctx(shop))["rows"][0]["available"] == 30


def test_acting_tools_plan_first_then_act_with_audit(shop):
    c = ctx(shop)
    plan = ot.set_reorder_rule("ponni rice", c, reorder_point=10)
    assert plan["needs_confirmation"] and "Ponni Rice 5kg" in plan["plan"] and plan["ok"] is False
    assert db.inventory(shop).document(f"{shop}-rice").get().to_dict()["reorder_point"] == 5          # nothing changed yet
    done = ot.set_reorder_rule("ponni rice", c, reorder_point=10, confirm=True)
    assert done["ok"] and db.inventory(shop).document(f"{shop}-rice").get().to_dict()["reorder_point"] == 10
    assert ot.adjust_stock("rice", 45, "delivery", c)["needs_confirmation"]
    assert ot.adjust_stock("rice", 45, "delivery", c, confirm=True)["on_hand"] == 45
    assert ot.update_price("Toned Milk", 30, c, confirm=True)["price"] == 30 and catalog.get_product(shop, f"{shop}-milk").price == 30
    assert ot.move_product("ghee", "dairy", c, bay=2, confirm=True)["aisle"] == "Dairy"
    assert ot.move_product("ghee", "Nowhere", c, confirm=True)["error"] == "aisle_not_on_map"
    actions = [e.to_dict() for e in db.audit(shop).stream()]
    assert {a["action"] for a in actions} >= {"reorder_rule", "stock_adjusted", "price_changed", "product_moved"}
    assert all(a["actor"] == "owner-1" for a in actions)


def test_offers_points_and_counts(shop):
    c = ctx(shop)
    plan = ot.create_offer("Dairy week", "category", c, percent_off=10, category="Dairy")
    assert plan["needs_confirmation"] and "10% off Dairy" in plan["plan"]
    assert offers.list_all(shop) == []
    assert ot.create_offer("Dairy week", "category", c, percent_off=10, category="Dairy", confirm=True)["ok"]
    assert [o["name"] for o in ot.list_offers(c)["rows"]] == ["Dairy week"]
    assert ot.set_offer_active("dairy week", False, c, confirm=True)["active"] is False
    assert ot.create_offer("Bad", "cart", c)["error"]                                         # needs a value
    assert ot.adjust_points("1234", 50, "birthday", c)["needs_confirmation"]
    assert ot.adjust_points("priya", 50, "birthday", c, confirm=True)["points"] == 50 and points.balance(shop, "c1") == 50
    assert ot.adjust_points("nobody", 5, "x", c, confirm=True)["error"] == "no_single_match"
    assert ot.record_shelf_count("rice", 28, c)["system"] == 30
    assert ot.customers_overview(c, segment="vip")["rows"][0]["last4"] == "1234" and ot.customers_overview(c)["segments"] == {"vip": 1}


def test_stock_report_totals(shop):
    out = ot.stock_report(ctx(shop))
    assert out["products"] == 3 and out["units_on_hand"] == 32 and out["stock_value"] == 2 * 28 + 30 * 420
    assert out["by_status"]["out"] == 1 and {c["category"] for c in out["rows"]} == {"Dairy", "Staples"}


def test_reports_and_status(shop):
    c = ctx(shop)
    assert ot.sales_report(c, days=7)["orders"] == 0
    assert ot.demand_signals(c)["count"] == 0
    assert ot.floor_map_summary(c)["rows"] == [{"aisle": "A1", "products": 3}, {"aisle": "Dairy", "products": 0}]
    st = ot.sync_status(c)
    assert st["has_secret"] is False and st["outbox_pending"] == 0
    assert ot.approve_purchase_order("nope", c, confirm=True)["error"] == "unknown_draft"
