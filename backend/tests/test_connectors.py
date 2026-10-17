import io
import json
import sqlite3
from types import SimpleNamespace

import pytest

from app.connectors import normalizer
from app.domain.models import Inventory, Product, Store
from app.services import catalog, connectors, db

CSV = b"Item Code,Item Name,Rate,Closing Stock\nmilk,Toned Milk,30,12\nnew1,Ghee 1L,520,4\nbad,,10,1\n"
MAPPING = {"sku": "Item Code", "name": "Item Name", "price": "Rate", "on_hand": "Closing Stock"}
REAL_PUBLIC_HOST = connectors.public_host


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(connectors, "public_host", lambda host: None)                       # no DNS in tests
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(connectors.secrets, "put", lambda name, value: None)
    monkeypatch.setattr(connectors.secrets, "get", lambda name: "Bearer t")


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    p = Product.from_row(store_id=store_id, sku="milk", name="Toned Milk", price=28, mrp=28, threshold=500, category="Dairy")
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(Inventory(product_id=p.product_id, store_id=store_id, on_hand=20).model_dump())
    catalog.invalidate(store_id)
    return store_id


def _fake_fetch(content: bytes, ctype: str = "text/csv"):
    return lambda url, headers=None, hops=5: SimpleNamespace(content=content, headers={"content-type": ctype})


def test_inspect_proposes_a_mapping_and_previews_changes(shop):
    out = connectors.inspect(shop, "file", data=CSV, filename="stock.csv")
    assert out["columns"] == ["Item Code", "Item Name", "Rate", "Closing Stock"]
    assert out["mapping"] == MAPPING and out["proposal"]["source"] == "heuristic"
    assert out["row_count"] == 3 and out["problem"] == ""
    pv = out["preview"]
    assert (pv["adds"], pv["updates"], pv["restocks"], pv["unchanged"], pv["errors"]) == (1, 1, 0, 0, 1)
    assert pv["changes"][0] == {"kind": "update", "sku": "milk", "note": "Toned Milk: ₹28 -> ₹30"}
    assert pv["error_samples"][0]["message"] == "name is required"


def test_incomplete_mapping_gives_a_problem_not_a_preview(shop):
    out = connectors.inspect(shop, "file", data=b"a,b\n1,2\n", filename="x.csv")
    assert "needs" in out["problem"] and out["preview"] is None
    with pytest.raises(connectors.SourceError, match="not in the source"):
        connectors.check_mapping({"sku": "zzz", "name": "b", "price": "a", "on_hand": "a"}, ["a", "b"])
    with pytest.raises(connectors.SourceError, match="unknown fields"):
        connectors.check_mapping({"sku": "a", "weird": "b"}, ["a", "b"])


def test_apply_writes_bumps_and_audits(shop):
    r = connectors.apply(shop, "file", mapping=MAPPING, actor="owner-1", label="stock.csv", data=CSV, filename="stock.csv")
    assert (r["created"], r["updated"], r["errors"], r["rows"]) == (1, 1, 1, 2)
    assert catalog.get_by_sku(shop, "new1").name == "Ghee 1L"
    assert catalog.get_by_sku(shop, "milk").price == 30
    actions = [a.to_dict() for a in db.audit(shop).stream()]
    assert any(a["action"] == "connector_apply" and a["payload"]["created"] == 1 for a in actions)


def test_xlsx_and_json_readers():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["SKU", "Name", "Price", "Qty"]); ws.append(["a1", "Atta", 265.0, 10]); ws.append([None, None, None, None])
    buf = io.BytesIO(); wb.save(buf)
    cols, recs = connectors.read_file(buf.getvalue(), "stock.xlsx")
    assert cols == ["SKU", "Name", "Price", "Qty"] and recs == [{"SKU": "a1", "Name": "Atta", "Price": "265", "Qty": "10"}]
    data = json.dumps({"items": [{"sku": "a1", "name": "Atta", "price": 265, "stock": 3, "meta": {"x": 1}}]}).encode()
    cols, recs = connectors.read_file(data, "export.json")
    assert cols == ["sku", "name", "price", "stock", "meta"] and recs[0]["meta"] == '{"x": 1}'
    with pytest.raises(connectors.SourceError):
        connectors.read_file(b"x", "notes.docx")
    with pytest.raises(connectors.SourceError):
        connectors.read_file(b"{}", "empty.json")


def test_sheet_links_become_csv_exports_and_unshared_sheets_are_explained(monkeypatch):
    assert connectors.sheet_csv_url("https://docs.google.com/spreadsheets/d/ABC-123/edit#gid=77") == \
        "https://docs.google.com/spreadsheets/d/ABC-123/export?format=csv&gid=77"
    assert connectors.sheet_csv_url("https://docs.google.com/spreadsheets/d/ABC/edit?usp=sharing").endswith("/ABC/export?format=csv")
    with pytest.raises(connectors.SourceError):
        connectors.sheet_csv_url("https://example.com/x")
    monkeypatch.setattr(connectors, "fetch", _fake_fetch(b"<html><body>Sign in</body></html>", "text/html"))
    with pytest.raises(connectors.SourceError, match="shared"):
        connectors.read_sheet("https://docs.google.com/spreadsheets/d/ABC/edit")
    monkeypatch.setattr(connectors, "fetch", _fake_fetch(CSV))
    assert connectors.read_sheet("https://docs.google.com/spreadsheets/d/ABC/edit")[0][0] == "Item Code"


def test_api_reader_sends_auth_and_reads_json_or_csv(monkeypatch):
    seen = {}
    def fake(url, headers=None, hops=5):
        seen["headers"] = headers
        return SimpleNamespace(content=b'[{"sku":"a","name":"A","price":1,"on_hand":2}]', headers={"content-type": "application/json"})
    monkeypatch.setattr(connectors, "fetch", fake)
    cols, recs = connectors.read_api("https://pos.example.com/items", auth="Bearer t")
    assert cols == ["sku", "name", "price", "on_hand"] and seen["headers"] == {"Authorization": "Bearer t"}
    monkeypatch.setattr(connectors, "fetch", _fake_fetch(CSV))
    assert connectors.read_api("https://pos.example.com/items.csv")[1][0]["Item Code"] == "milk"


def test_url_and_address_guards():
    for bad in ("http://example.com/x", "ftp://example.com/x", "https:///nohost"):
        with pytest.raises(connectors.SourceError):
            connectors.safe_url(bad)
    for host in ("127.0.0.1", "169.254.169.254", "10.1.2.3", "192.168.1.9", "::1"):
        with pytest.raises(connectors.SourceError):
            REAL_PUBLIC_HOST(host)


def test_db_reader_lists_tables_and_reads_one_read_only(tmp_path, monkeypatch):
    path = tmp_path / "pos.db"
    con = sqlite3.connect(path)
    con.execute("create table items (code text, name text, rate real, qty int)")
    con.execute("insert into items values ('a1','Atta',265,4)")
    con.commit(); con.close()
    dsn = f"sqlite:///{path}"
    assert connectors.discover(dsn) == ["items"]
    cols, recs = connectors.read_db(dsn, "items")
    assert cols == ["code", "name", "rate", "qty"] and recs == [{"code": "a1", "name": "Atta", "rate": "265", "qty": "4"}]
    with pytest.raises(connectors.SourceError, match="not in the database"):
        connectors.read_db(dsn, "sqlite_master")
    with pytest.raises(connectors.SourceError, match="only postgresql"):
        connectors._engine("mongodb://x/y")
    monkeypatch.setattr(connectors, "public_host", REAL_PUBLIC_HOST)
    with pytest.raises(connectors.SourceError, match="not allowed"):
        connectors._engine("postgresql://u:p@127.0.0.1/db")


def test_saved_connector_runs_when_due_and_can_be_removed(shop, monkeypatch):
    monkeypatch.setattr(connectors, "fetch", _fake_fetch(CSV))
    c = connectors.save(shop, "api", label="POS export", url="https://pos.example.com/x.csv", mapping=MAPPING, actor="owner-1", auth="Bearer t")
    assert [x.label for x in connectors.list_(shop)] == ["POS export"]
    assert connectors.run_due() == {"connectors_run": 1, "connectors_failed": 0}
    saved = connectors.get(shop, c.connector_id)
    assert saved.last_result["ok"] and saved.last_result["created"] == 1 and saved.last_run_at
    assert connectors.run_due()["connectors_run"] == 0                      # not due again yet
    monkeypatch.setattr(connectors, "fetch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert connectors.run(shop, saved)["ok"] is False
    assert connectors.remove(shop, c.connector_id, "owner-1") and connectors.list_(shop) == []
    with pytest.raises(connectors.SourceError):
        connectors.save(shop, "file", label="x", mapping=MAPPING, actor="owner-1")
