from fastapi.testclient import TestClient

from app.main import app
from app.services import auth, db

client = TestClient(app)


def test_a_changed_email_follows_the_member_everywhere(monkeypatch):
    uid, staff = "owner-9", "staff-9"
    monkeypatch.setitem(auth._EMAILS, uid, "first@example.com")
    r = client.post("/owner/register", json={"name": "Email Change Mart"}, headers={"X-Test-Uid": uid})
    assert r.status_code == 200, r.text
    sid = r.json()["store"]["store_id"]
    assert client.post(f"/owner/{sid}/staff", json={"email": "helper@example.com"}, headers={"X-Test-Uid": uid}).status_code == 200
    monkeypatch.setitem(auth._EMAILS, staff, "helper@example.com")
    assert client.get(f"/owner/{sid}/inventory", headers={"X-Test-Uid": staff}).status_code == 200      # staff joined by email

    monkeypatch.setitem(auth._EMAILS, uid, "second@example.com")            # the owner's next token carries the new address
    team = client.get(f"/owner/{sid}/team", headers={"X-Test-Uid": uid})
    assert team.status_code == 200 and team.json()["owner_emails"] == ["second@example.com"]
    assert db.users().document(uid).get().to_dict()["email"] == "second@example.com"

    monkeypatch.setitem(auth._EMAILS, staff, "helper2@example.com")
    assert client.get(f"/owner/{sid}/inventory", headers={"X-Test-Uid": staff}).status_code == 200    # access continues
    assert client.get(f"/owner/{sid}/team", headers={"X-Test-Uid": uid}).json()["staff_emails"] == ["helper2@example.com"]
    changes = sorted((a.to_dict()["payload"]["from"], a.to_dict()["payload"]["to"]) for a in db.audit(sid).stream() if a.to_dict()["action"] == "member_email_changed")
    assert changes == [("first@example.com", "second@example.com"), ("helper@example.com", "helper2@example.com")]
