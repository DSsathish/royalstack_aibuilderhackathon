import pytest

from app.connectors import csv_connector as csvc
from app.connectors import normalizer

HEADER = ["Item Code", "Item Name", "Rate (Rs)", "Qty on hand", "Dept", "Bar Code", "Shelf"]
SAMPLES = [{"Item Code": "A1", "Item Name": "Salt 1kg", "Rate (Rs)": "₹ 20.00", "Qty on hand": "12 pcs", "Dept": "Staples", "Bar Code": "8901234567890", "Shelf": "A1"}]


def test_model_proposal_is_validated(monkeypatch):
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: {
        "mapping": {"sku": "Item Code", "name": "Item Name", "price": "Rate (Rs)", "on_hand": "Qty on hand",
                    "category": "Dept", "barcode": "Bar Code", "aisle": "Shelf", "brand": "Brand", "bogus": "Item Name"},
        "notes": ["Rate is in rupees"], "questions": [], "confidence": 0.9})
    p = normalizer.propose(HEADER, SAMPLES)
    assert p.source == "model" and p.confidence == 0.9
    assert p.mapping["sku"] == "Item Code" and p.mapping["aisle"] == "Shelf"
    assert "brand" not in p.mapping          # header not in file: dropped, not guessed
    assert "bogus" not in p.mapping          # unknown canonical field: dropped
    assert p.notes == ["Rate is in rupees"]


def test_missing_required_becomes_a_question(monkeypatch):
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: {"mapping": {"sku": "Item Code", "name": "Item Name"}, "notes": [], "questions": [], "confidence": 0.5})
    p = normalizer.propose(HEADER, SAMPLES)
    assert any("price" in q for q in p.questions) and any("on_hand" in q for q in p.questions)


def test_heuristic_fallback_when_model_fails(monkeypatch):
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: (_ for _ in ()).throw(RuntimeError("down")))
    p = normalizer.propose(HEADER, SAMPLES)
    assert p.source == "heuristic"
    assert p.mapping == {"sku": "Item Code", "name": "Item Name", "price": "Rate (Rs)", "on_hand": "Qty on hand",
                         "category": "Dept", "barcode": "Bar Code", "aisle": "Shelf"}


def test_proposed_mapping_parses_messy_values(monkeypatch):
    monkeypatch.setattr(normalizer, "_ask_model", lambda header, samples: (_ for _ in ()).throw(RuntimeError("down")))
    p = normalizer.propose(HEADER, SAMPLES)
    data = "Item Code,Item Name,Rate (Rs),Qty on hand,Dept,Bar Code,Shelf\nA1,Salt 1kg,\"₹ 1,250.00\",12 pcs,Staples,8901234567890,A1\n".encode()
    rows, errors = csvc.parse(data, p.mapping)
    assert errors == [] and rows[0].price == 1250 and rows[0].on_hand == 12 and rows[0].aisle == "A1"


@pytest.mark.parametrize("raw,expected", [("₹ 1,250.00", 1250.0), ("Rs.20", 20.0), ("12 pcs", 12), ("3.5 kg", 3.5), ("  7 ", 7), ("", 0)])
def test_num_cleaning(raw, expected):
    assert csvc._num(raw, integer=isinstance(expected, int)) == expected


def test_num_still_rejects_negative_and_garbage():
    with pytest.raises(ValueError):
        csvc._num("-5", integer=True)
    with pytest.raises(Exception):
        csvc._num("abc", integer=True)
