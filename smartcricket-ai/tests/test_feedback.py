"""Player feedback: players send and see their own; only administrators list, reply and delete."""
import pytest
from fastapi.testclient import TestClient

from backend.app import auth
from backend.app.db import Base, engine
from backend.app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(auth, "ADMINS", {"coach@example.com"})
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def register(client, email, name="Test Player"):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


GOOD = {"category": "training", "rating": 4, "message": "  The drills are great, more spin please.  ",
        "tags": ["Helpful drills", "Helpful drills", "Motivating"]}


def test_player_sends_and_admin_replies(client):
    player, other = register(client, "p1@example.com", "Asha Rao"), register(client, "p2@example.com")
    admin = register(client, "coach@example.com", "Coach")

    r = client.post("/api/feedback", json=GOOD, headers=player)
    assert r.status_code == 201
    sent = r.json()
    assert sent["message"] == "The drills are great, more spin please."
    assert sent["tags"] == ["Helpful drills", "Motivating"] and sent["status"] == "new" and sent["reply"] is None

    assert client.get("/api/feedback/mine", headers=other).json()["items"] == []
    mine = client.get("/api/feedback/mine", headers=player).json()
    assert [f["id"] for f in mine["items"]] == [sent["id"]] and "Too hard" in mine["tags"]

    inbox = client.get("/api/admin/feedback", headers=admin).json()
    assert inbox[0]["player"]["name"] == "Asha Rao"

    r = client.post(f"/api/admin/feedback/{sent['id']}/reply", json={"reply": " Spin drills coming next week! "}, headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "read"
    seen = client.get("/api/feedback/mine", headers=player).json()["items"][0]
    assert seen["reply"] == "Spin drills coming next week!" and seen["replied_at"]

    assert client.post(f"/api/admin/feedback/{sent['id']}", json={"status": "new"}, headers=admin).json()["status"] == "new"
    assert client.delete(f"/api/admin/feedback/{sent['id']}", headers=admin).status_code == 204
    assert client.get("/api/feedback/mine", headers=player).json()["items"] == []
    assert client.delete(f"/api/admin/feedback/{sent['id']}", headers=admin).status_code == 404


def test_roles_are_enforced(client):
    player, admin = register(client, "p1@example.com"), register(client, "coach@example.com")
    assert client.post("/api/feedback", json=GOOD).status_code == 401
    assert client.post("/api/feedback", json=GOOD, headers=admin).status_code == 403
    assert client.get("/api/admin/feedback", headers=player).status_code == 403
    fid = client.post("/api/feedback", json=GOOD, headers=player).json()["id"]
    assert client.post(f"/api/admin/feedback/{fid}/reply", json={"reply": "hi"}, headers=player).status_code == 403
    assert client.delete(f"/api/admin/feedback/{fid}", headers=player).status_code == 403


@pytest.mark.parametrize("change", [
    {"rating": 0}, {"rating": 6}, {"category": "spam"}, {"message": "  hi "}, {"message": "x" * 1001},
    {"tags": ["Not a tag"]},
])
def test_invalid_feedback_rejected(client, change):
    player = register(client, "p1@example.com")
    assert client.post("/api/feedback", json=GOOD | change, headers=player).status_code == 422
