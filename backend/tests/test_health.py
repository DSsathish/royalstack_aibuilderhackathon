from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True
