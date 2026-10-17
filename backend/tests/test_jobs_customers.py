from datetime import timedelta

from fastapi.testclient import TestClient

from app.domain.models import Customer, Store, now
from app.main import app
from app.services import db

client = TestClient(app)


def test_nightly_job_runs_every_store(store_id):
    sid2 = store_id + "-b"
    for sid in (store_id, sid2):
        db.store_ref(sid).set(Store(store_id=sid, name="S").model_dump())
    db.customers(store_id).document("a").set(Customer(uid="a", store_id=store_id, visits=3, last_seen=now() - timedelta(days=60)).model_dump())
    res = client.post("/jobs/customers", headers={"X-Job-Key": "test-job-key"})
    assert res.status_code == 200, res.text
    assert {r["store_id"] for r in res.json()["stores"]} >= {store_id, sid2}
    assert db.customers(store_id).document("a").get().to_dict()["segment"] == "at_risk"
    assert client.post("/jobs/customers").status_code == 401


def test_forecast_job_covers_every_store_when_no_store_given(store_id, monkeypatch):
    from app.jobs import forecast as fj
    seen = []
    monkeypatch.setattr(fj, "run", lambda sid: seen.append(sid) or {"store_id": sid})
    db.store_ref(store_id).set(Store(store_id=store_id, name="S").model_dump())
    res = client.post("/jobs/forecast", headers={"X-Job-Key": "test-job-key"})
    assert res.status_code == 200 and store_id in seen


def test_sync_job_requires_key(store_id):
    assert client.post("/jobs/sync").status_code == 401
    res = client.post("/jobs/sync", headers={"X-Job-Key": "test-job-key"})
    assert res.status_code == 200 and "pulled" in res.json()
