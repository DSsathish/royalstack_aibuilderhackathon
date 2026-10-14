import time

from app.services import qr


def test_entrance_token_round_trip():
    t = qr.entrance_token("demo")
    assert qr.verify(t) == {"kind": "entrance", "store_id": "demo"}


def test_tampered_token_rejected():
    t = qr.entrance_token("demo")
    assert qr.verify(t[:-2] + "zz") is None
    assert qr.verify("garbage") is None
    assert qr.verify("") is None


def test_receipt_token_carries_order_and_expires():
    t = qr.receipt_token("o1", "demo", 3)
    p = qr.verify(t)
    assert p["kind"] == "receipt" and p["order_id"] == "o1" and p["count"] == 3
    assert p["exp"] > time.time()
    expired = qr.sign({"kind": "receipt"}, ttl_s=-1)
    assert qr.verify(expired) is None


def test_non_ascii_token_is_rejected_not_500():
    assert qr.verify("abc.éé") is None
