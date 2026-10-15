import pytest

from app.domain.models import Inventory, Product, Store, Supplier
from app.services import catalog, db, forecast, reorder


def put(store_id, sku, price, on_hand, *, supplier="sup-a", lead=3, reorder_qty=20, avg_daily=None, std=0.5):
    p = Product.from_row(store_id=store_id, sku=sku, name=sku.title(), price=price, mrp=price, threshold=500)
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(
        product_id=p.product_id, store_id=store_id, on_hand=on_hand, reorder_point=0, reorder_qty=reorder_qty,
        lead_time_days=lead, supplier_id=supplier).model_dump())
    if avg_daily is not None:
        forecast.put(store_id, p.product_id, daily=[avg_daily] * 14, avg_daily=avg_daily, std_daily=std)
    return p.product_id


@pytest.fixture
def shop(store_id, monkeypatch):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    for sid, name in (("sup-a", "Metro"), ("sup-b", "Aavin")):
        db.suppliers(store_id).document(sid).set(Supplier(supplier_id=sid, store_id=store_id, name=name, lead_time_days=3).model_dump())
    put(store_id, "milk", 28, 2, supplier="sup-b", lead=1, avg_daily=8)      # point = ceil(8*1 + 0.75) = 9 -> low
    put(store_id, "atta", 265, 40, avg_daily=3)                               # point = ceil(9.75) = 10 -> fine
    put(store_id, "ghee", 650, 1, avg_daily=2)                                # point = ceil(6.75) = 7 -> low
    put(store_id, "salt", 20, 0)                                              # no forecast: falls back to reorder_qty
    catalog.invalidate(store_id)
    monkeypatch.setattr(reorder, "explain", lambda *a, **k: ("Seasonal demand ahead.", {"milk": "Daily seller, 1-day lead.", "ghee": "Festival demand."}))
    return store_id


def test_reorder_point_formula():
    assert reorder.reorder_point(avg_daily=8, lead_time_days=1, std_daily=0.5) == 9
    assert reorder.reorder_point(avg_daily=0, lead_time_days=3, std_daily=0) == 0
    assert reorder.reorder_point(avg_daily=2.5, lead_time_days=4, std_daily=2) == 13


def test_candidates_grouped_by_supplier(shop):
    groups = reorder.candidates(shop)
    assert set(groups) == {"sup-a", "sup-b"}
    ids = {line["product_id"] for g in groups.values() for line in g}
    assert ids == {f"{shop}-milk", f"{shop}-ghee", f"{shop}-salt"}
    milk = next(l for l in groups["sup-b"] if l["product_id"] == f"{shop}-milk")
    assert milk["reorder_point"] == 9 and milk["qty"] == max(20, 8 * 14)


def test_draft_creates_one_po_per_supplier_with_rationale(shop):
    drafts = reorder.draft(shop, created_by="agent")
    assert len(drafts) == 2 and all(d.status == "draft" for d in drafts)
    b = next(d for d in drafts if d.supplier_id == "sup-b")
    assert b.supplier_name == "Aavin" and b.lines[0]["reason"] == "Daily seller, 1-day lead."
    assert b.summary == "Seasonal demand ahead."
    assert len(reorder.list_drafts(shop)) == 2


def test_approve_and_reject(shop):
    a, b = reorder.draft(shop, created_by="agent")
    ok = reorder.approve(shop, a.po_id, by="owner-1", qty_override={a.lines[0]["product_id"]: 99})
    assert ok.status == "approved" and ok.lines[0]["qty"] == 99 and ok.decided_by == "owner-1"
    assert ok.supplier_name in ok.email_text and "99" in ok.email_text
    rj = reorder.reject(shop, b.po_id, by="owner-1", reason="enough stock")
    assert rj.status == "rejected" and rj.reason == "enough stock"
    actions = [d.to_dict()["action"] for d in db.audit(shop).stream()]
    assert "po_approved" in actions and "po_rejected" in actions


def test_approve_twice_is_rejected(shop):
    a, _ = reorder.draft(shop, created_by="agent")
    reorder.approve(shop, a.po_id, by="o")
    with pytest.raises(ValueError):
        reorder.approve(shop, a.po_id, by="o")
