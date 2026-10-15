from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    res = TestClient(app).get("/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_unhandled_errors_are_json_with_cors(monkeypatch):
    from app.api import owner as owner_api
    monkeypatch.setattr(owner_api.insights, "overview", lambda store_id: 1 / 0)
    from app.services import db
    from app.domain.models import Store
    db.store_ref("t-err-store").set(Store(store_id="t-err-store", name="S").model_dump())
    db.users().document("owner-err").set({"stores": ["t-err-store"]})
    res = TestClient(app, raise_server_exceptions=False).get("/owner/t-err-store/overview",
        headers={"X-Test-Uid": "owner-err", "Origin": "http://localhost:3000"})
    assert res.status_code == 500
    assert res.json()["detail"].startswith("internal error")
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
