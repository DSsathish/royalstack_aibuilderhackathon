import pytest

from app.connectors import csv_connector as csvc
from app.services import db

CANON = {"sku": "sku", "name": "name", "price": "price", "on_hand": "on_hand"}
CUSTOM = {"sku": "Item Code", "name": "Item Name", "price": "Rate", "on_hand": "Qty", "aisle": "Aisle"}


def test_parse_with_canonical_headers():
    data = b"sku,name,price,on_hand\nA1,Salt 1kg,20,10\n"
    rows, errors = csvc.parse(data, CANON)
    assert errors == []
    assert rows[0].sku == "A1" and rows[0].price == 20 and rows[0].on_hand == 10


def test_parse_with_custom_mapping():
    data = b"Item Code,Item Name,Rate,Qty,Aisle\nB2,Ghee 1kg,650,3,A4\n"
    rows, errors = csvc.parse(data, CUSTOM)
    assert errors == []
    assert rows[0].name == "Ghee 1kg" and rows[0].aisle == "A4"


def test_parse_reports_row_errors_and_keeps_good_rows():
    data = b"sku,name,price,on_hand\nA1,Salt,20,10\n,NoSku,5,1\nC3,Neg,-5,1\nD4,BadQty,5,x\n"
    rows, errors = csvc.parse(data, CANON)
    assert [r.sku for r in rows] == ["A1"]
    assert sorted(e.line for e in errors) == [3, 4, 5]


def test_parse_rejects_missing_mapped_header():
    data = b"sku,name,price\nA1,Salt,20\n"
    with pytest.raises(csvc.ImportError_) as e:
        csvc.parse(data, CANON)
    assert "on_hand" in str(e.value)


def test_parse_rejects_oversize_file():
    with pytest.raises(csvc.ImportError_):
        csvc.parse(b"x" * (csvc.MAX_BYTES + 1), CANON)


def test_parse_rejects_too_many_rows():
    body = b"sku,name,price,on_hand\n" + b"A,B,1,1\n" * (csvc.MAX_ROWS + 1)
    with pytest.raises(csvc.ImportError_):
        csvc.parse(body, CANON)


def test_upsert_is_idempotent(store_id):
    rows, _ = csvc.parse(b"sku,name,price,on_hand,aisle\nA1,Salt 1kg,20,10,A1\n", {**CANON, "aisle": "aisle"})
    first = csvc.upsert(store_id, rows, high_value_threshold=500)
    second = csvc.upsert(store_id, rows, high_value_threshold=500)
    assert (first.created, first.updated) == (1, 0)
    assert (second.created, second.updated) == (0, 1)
    pid = f"{store_id}-a1"
    assert db.products(store_id).document(pid).get().exists
    assert db.inventory(store_id).document(pid).get().to_dict()["on_hand"] == 10
    assert db.locations(store_id).document(pid).get().to_dict()["aisle"] == "A1"


def test_upsert_marks_high_value(store_id):
    rows, _ = csvc.parse(b"sku,name,price,on_hand\nG1,Ghee,650,2\n", CANON)
    csvc.upsert(store_id, rows, high_value_threshold=500)
    assert db.products(store_id).document(f"{store_id}-g1").get().to_dict()["is_high_value"] is True


def test_upsert_converts_substitute_skus_to_product_ids(store_id):
    rows, _ = csvc.parse(b"sku,name,price,on_hand,substitutes\nA1,Salt,20,10,\nB2,Rock Salt,30,5,A1|ZZ9\n",
                         {**CANON, "substitutes": "substitutes"})
    csvc.upsert(store_id, rows, high_value_threshold=500)
    assert db.products(store_id).document(f"{store_id}-b2").get().to_dict()["substitutes"] == [f"{store_id}-a1", f"{store_id}-zz9"]


def test_imported_inventory_works_with_reserve(store_id):
    from app.services import inventory
    rows, _ = csvc.parse(b"sku,name,price,on_hand\nA1,Salt,20,10\n", CANON)
    csvc.upsert(store_id, rows, high_value_threshold=500)
    assert inventory.available(store_id, f"{store_id}-a1") == 10
    assert inventory.reserve(store_id, f"{store_id}-a1", 2) is True
    assert inventory.available(store_id, f"{store_id}-a1") == 8
