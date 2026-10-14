import pytest
from fastapi.testclient import TestClient

from app.domain.models import Store
from app.main import app
from app.services import db

client = TestClient(app)


@pytest.fixture
def shop(store_id):
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    return store_id


def test_create_session(shop):
    res = client.post("/sessions", json={"store_id": shop, "mode": "online"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "online" and body["cart_id"] and body["session_id"]


def test_create_session_unknown_store(store_id):
    assert client.post("/sessions", json={"store_id": store_id, "mode": "online"}).status_code == 404


def test_create_session_bad_mode(shop):
    assert client.post("/sessions", json={"store_id": shop, "mode": "admin"}).status_code == 422


def test_chat_unknown_session_is_404():
    res = client.post("/agent/chat", data={"session_id": "nope", "message": "hi"})
    assert res.status_code == 404


def test_chat_image_too_large_is_413(shop):
    sid = client.post("/sessions", json={"store_id": shop, "mode": "instore"}).json()["session_id"]
    big = b"x" * (4 * 1024 * 1024 + 1)
    res = client.post("/agent/chat", data={"session_id": sid, "message": "what is this"},
                      files={"image": ("a.jpg", big, "image/jpeg")})
    assert res.status_code == 413


def test_chat_rejects_non_image_upload(shop):
    sid = client.post("/sessions", json={"store_id": shop, "mode": "instore"}).json()["session_id"]
    res = client.post("/agent/chat", data={"session_id": sid, "message": "x"},
                      files={"image": ("a.txt", b"hello", "text/plain")})
    assert res.status_code == 415


def test_chat_message_required(shop):
    sid = client.post("/sessions", json={"store_id": shop, "mode": "instore"}).json()["session_id"]
    assert client.post("/agent/chat", data={"session_id": sid, "message": ""}).status_code == 422
