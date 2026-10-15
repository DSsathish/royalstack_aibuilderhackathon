import pytest

from app.domain.models import DemandSignal, Inventory, Product, Store
from app.services import cart, catalog, checkout, db, insights, sessions


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    for sku, price, qty in (("milk", 28, 5), ("oat", 250, 0), ("salt", 20, 50), ("dead", 90, 10)):
        p = Product.from_row(store_id=store_id, sku=sku, name=sku.title(), price=price, mrp=price, threshold=500)
        db.products(store_id).document(p.product_id).set(p.model_dump())
        db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=qty, reorder_point=6).model_dump())
    catalog.invalidate(store_id)
    return store_id


def sig(store_id, text, kind, matched=None, source="search"):
    import uuid
    s = DemandSignal(signal_id=uuid.uuid4().hex, store_id=store_id, query_text=text, type=kind, matched_product_id=matched, source=source)
    db.demand_signals(store_id).document(s.signal_id).set(s.model_dump())


def test_signals_grouped_and_lost_sales(shop):
    sig(shop, "oat milk", "not_carried", source="agent"); sig(shop, "Oat Milk", "not_carried", source="agent"); sig(shop, "quinoa", "not_carried")
    sig(shop, "oat", "out_of_stock", matched=f"{shop}-oat"); sig(shop, "oat milk 1l", "out_of_stock", matched=f"{shop}-oat")
    out = insights.signals(shop, days=7)
    assert out["not_carried"][0] == {"query": "oat milk", "count": 2, "source": "agent"}
    assert out["out_of_stock"][0]["product_id"] == f"{shop}-oat" and out["out_of_stock"][0]["count"] == 2
    assert out["out_of_stock"][0]["lost_sales"] == 500


def test_shrink_candidates_from_quick_counts(shop):
    insights.record_count(shop, f"{shop}-salt", counted=46, by="owner")
    insights.record_count(shop, f"{shop}-milk", counted=5, by="owner")
    out = insights.shrink(shop)
    assert out == [{"product_id": f"{shop}-salt", "name": "Salt", "system": 50, "counted": 46, "difference": -4, "value": 80}]


def test_overview_counts_today(shop, monkeypatch):
    monkeypatch.setattr(insights, "daily_revenue_history", lambda store_id, days: [{"day": "2026-10-01", "revenue": 100.0}])
    s = sessions.create(shop, "instore")
    cart.add(shop, s.cart_id, f"{shop}-milk", 2, via="scan", mode="instore")
    checkout.confirm(checkout.intent(s).order_id, payment_id="p", signature="mock")
    out = insights.overview(shop)
    assert out["today"]["orders"] == 1 and out["today"]["revenue"] == 56 and out["today"]["by_channel"] == {"store": 56.0}
    assert out["low_stock"] == 2 and out["out_of_stock"] == 1       # milk (3 left) and oat (0) are <= reorder point 6
    assert out["series"][-1]["revenue"] == 56 and out["series"][0]["day"] == "2026-10-01"


def test_inventory_rows_status(shop):
    from app.services import forecast
    forecast.put(shop, f"{shop}-milk", daily=[2] * 14, avg_daily=2, std_daily=0.3)
    rows = {r["product_id"]: r for r in insights.inventory(shop)}
    assert rows[f"{shop}-milk"]["days_of_cover"] == 2.5 and rows[f"{shop}-milk"]["status"] == "low"
    assert rows[f"{shop}-oat"]["status"] == "out"
    assert rows[f"{shop}-salt"]["status"] == "ok" and rows[f"{shop}-salt"]["days_of_cover"] is None
