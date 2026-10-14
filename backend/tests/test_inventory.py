from concurrent.futures import ThreadPoolExecutor

import pytest

from app.domain.models import Inventory
from app.services import db, inventory


@pytest.fixture
def seeded(store_id):
    db.inventory(store_id).document("p1").set(
        Inventory(product_id="p1", store_id=store_id, on_hand=3).model_dump()
    )
    return store_id


def test_reserve_succeeds_when_enough_stock(seeded):
    assert inventory.reserve(seeded, "p1", 2) is True
    assert inventory.available(seeded, "p1") == 1


def test_reserve_fails_on_shortage(seeded):
    assert inventory.reserve(seeded, "p1", 4) is False
    assert inventory.available(seeded, "p1") == 3


def test_release_returns_stock(seeded):
    inventory.reserve(seeded, "p1", 2)
    inventory.release(seeded, "p1", 2)
    assert inventory.available(seeded, "p1") == 3


def test_commit_decrements_on_hand_and_reserved(seeded):
    inventory.reserve(seeded, "p1", 2)
    inventory.commit(seeded, "p1", 2)
    doc = db.inventory(seeded).document("p1").get().to_dict()
    assert doc["on_hand"] == 1
    assert doc["reserved"] == 0


def test_commit_never_goes_below_zero(seeded):
    inventory.commit(seeded, "p1", 10)
    doc = db.inventory(seeded).document("p1").get().to_dict()
    assert doc["on_hand"] == 0
    assert doc["reserved"] == 0


def test_unknown_product_cannot_be_reserved(store_id):
    assert inventory.reserve(store_id, "missing", 1) is False


def test_concurrent_reserve_of_last_unit_only_one_wins(store_id):
    db.inventory(store_id).document("p1").set(
        Inventory(product_id="p1", store_id=store_id, on_hand=1).model_dump()
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: inventory.reserve(store_id, "p1", 1), range(4)))
    assert results.count(True) == 1
    assert inventory.available(store_id, "p1") == 0
