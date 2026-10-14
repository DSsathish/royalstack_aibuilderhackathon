import pytest
from fastapi.testclient import TestClient

from app.domain.models import Inventory, Location, Product, Store
from app.main import app
from app.services import catalog, db

client = TestClient(app)


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="Test Shop").model_dump())
    p = Product.from_row(store_id=store_id, sku="MILK1", name="Toned Milk", price=28, threshold=500,
                         barcode="8901234567890", tags=["milk"])
    db.products(store_id).document(p.product_id).set(p.model_dump())
    db.inventory(store_id).document(p.product_id).set(
        Inventory(product_id=p.product_id, store_id=store_id, on_hand=4).model_dump())
    db.locations(store_id).document(p.product_id).set(
        Location(product_id=p.product_id, store_id=store_id, aisle="A2").model_dump())
    catalog.invalidate(store_id)
    return store_id


def test_get_store(shop):
    res = client.get(f"/stores/{shop}")
    assert res.status_code == 200
    assert res.json()["name"] == "Test Shop"


def test_get_store_404(store_id):
    assert client.get(f"/stores/{store_id}").status_code == 404


def test_get_product(shop):
    res = client.get(f"/stores/{shop}/products/{shop}-milk1")
    assert res.status_code == 200
    body = res.json()
    assert body["available"] == 4 and body["location"]["aisle"] == "A2"
    assert "embedding" not in body


def test_get_by_barcode(shop):
    assert client.get(f"/stores/{shop}/products/by-barcode/8901234567890").json()["sku"] == "MILK1"


def test_barcode_validation(shop):
    assert client.get(f"/stores/{shop}/products/by-barcode/abc").status_code == 422


def test_search(shop):
    res = client.get(f"/stores/{shop}/search", params={"q": "milk"})
    assert res.status_code == 200
    assert res.json()[0]["product_id"] == f"{shop}-milk1"


def test_search_query_too_long(shop):
    assert client.get(f"/stores/{shop}/search", params={"q": "x" * 201}).status_code == 422


def test_store_id_validation():
    assert client.get("/stores/BAD_ID!").status_code == 422
