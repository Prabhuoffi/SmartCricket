"""Integration and system tests: IT-01, IT-02, IT-03, IT-09, ST-01, ST-02, ST-03 and others from Chapter 7."""
import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db import Base, engine
from backend.app.main import app

SAMPLES = Path(__file__).parent / "samples"


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def register(client, email):
    r = client.post("/api/auth/register", json={"name": "Test", "email": email, "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def blank_png() -> bytes:
    ok, buf = cv2.imencode(".png", np.full((120, 160, 3), 200, np.uint8))
    return buf.tobytes()


def test_register_and_login(client):  # IT-01
    register(client, "a@example.com")
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["token"]
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope1234"}).status_code == 401
    assert client.post("/api/auth/register",
                       json={"name": "X", "email": "a@example.com", "password": "password123"}).status_code == 409


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"name": "X", "email": "s@example.com", "password": "short"})
    assert r.status_code == 422


def test_requires_token(client):  # IT-02
    assert client.get("/api/history").status_code == 401


def test_wrong_type(client):  # ST-01
    h = register(client, "b@example.com")
    r = client.post("/api/image/analyse", headers=h, files={"file": ("a.gif", b"GIF89a", "image/gif")})
    assert r.status_code == 400


def test_unreadable_image(client):  # ST-03 (image variant)
    h = register(client, "c@example.com")
    r = client.post("/api/image/analyse", headers=h, files={"file": ("a.jpg", b"not really a jpeg", "image/jpeg")})
    assert r.status_code == 422


def test_too_large(client, monkeypatch):  # ST-02
    h = register(client, "d@example.com")
    monkeypatch.setattr(settings, "max_image_mb", 0)
    r = client.post("/api/image/analyse", headers=h, files={"file": ("a.png", blank_png(), "image/png")})
    assert r.status_code == 413


def test_no_person(client):
    h = register(client, "e@example.com")
    r = client.post("/api/image/analyse", headers=h, files={"file": ("blank.png", blank_png(), "image/png")})
    assert r.status_code == 200
    j = r.json()
    assert j["summary"]["detected"] is False and j["uncertain"] is True


@pytest.mark.skipif(not (SAMPLES / "batter.jpg").exists(), reason="sample photo not present")
def test_real_photo_flow(client):  # IT-03, IT-07, IT-09, FR-15, FR-17
    h = register(client, "f@example.com")
    with open(SAMPLES / "batter.jpg", "rb") as f:
        r = client.post("/api/image/analyse", headers=h, files={"file": ("batter.jpg", f, "image/jpeg")},
                        data={"session_label": "Test nets"})
    assert r.status_code == 200
    a = r.json()
    assert a["summary"]["detected"] and a["summary"]["visible"] >= 20
    measured = [v["deg"] for v in a["angles"].values() if v["deg"] is not None]
    assert measured and all(0 <= d <= 180 for d in measured)

    assert client.get(f"/api/files/{a['id']}/output", headers=h).status_code == 200
    assert len(client.get("/api/history", headers=h).json()) == 1
    assert client.get("/api/dashboard", headers=h).json()["images"] == 1
    assert "left_knee_deg" in client.get("/api/reports/history.csv", headers=h).text
    assert "Posture report" in client.get(f"/api/reports/{a['id']}", headers=h).text
    pdf = client.get(f"/api/reports/{a['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and "attachment" in pdf.headers["content-disposition"]

    reply = client.post(f"/api/coach/{a['id']}", headers=h, json={"text": "How is my knee?"}).json()["reply"]
    assert "not set up" in reply  # no API key in tests

    other = register(client, "g@example.com")  # IT-09: another user cannot see it
    assert client.get(f"/api/analyses/{a['id']}", headers=other).status_code == 404
    assert client.get(f"/api/files/{a['id']}/output", headers=other).status_code == 404

    assert client.delete(f"/api/analyses/{a['id']}", headers=h).status_code == 204
    assert client.get("/api/history", headers=h).json() == []
