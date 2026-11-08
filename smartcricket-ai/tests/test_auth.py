"""Registration and session inputs fail cleanly at authentication boundaries."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db import Base, engine
from backend.app.main import app


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def signup(client, email, password="password123", name="Test Player"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


@pytest.mark.parametrize("password", ["a" * 73, "🏏" * 19])
def test_password_beyond_bcrypt_byte_limit_is_rejected(client, password):
    response = signup(client, "toolong@example.com", password=password)
    assert response.status_code == 422
    assert "72 UTF-8 bytes" in response.text


@pytest.mark.parametrize("password,email", [("a" * 72, "ascii@example.com"), ("🏏" * 18, "unicode@example.com")])
def test_password_at_byte_limit_can_register_and_sign_in(client, password, email):
    assert signup(client, email, password=password).status_code == 201
    assert client.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": password + "a"}).status_code == 401


def test_blank_name_is_rejected_and_name_is_trimmed(client):
    assert signup(client, "blank@example.com", name=" \t ").status_code == 422
    response = signup(client, "trimmed@example.com", name="  Test Player  ")
    assert response.status_code == 201 and response.json()["name"] == "Test Player"


@pytest.mark.parametrize("claims", [{}, {"sub": None}, {"sub": "not-an-id"}, {"sub": "0"}, {"sub": str(2**100)}])
def test_malformed_signed_session_is_unauthorized(client, claims):
    token = jwt.encode(claims | {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       settings.jwt_secret, algorithm="HS256")
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_mobile_login_uses_existing_player_account(client):
    assert signup(client, "mobile-player@example.com").status_code == 201
    response = client.post("/api/auth/player/login", json={
        "email": "MOBILE-PLAYER@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["role"] == "player"
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    assert client.get("/api/auth/me", headers=headers).json()["email"] == "mobile-player@example.com"
    assert client.get("/api/admin/overview", headers=headers).status_code == 403


def test_mobile_login_rejects_bad_credentials_without_role_disclosure(client):
    response = client.post("/api/auth/player/login", json={
        "email": "mobile-player@example.com", "password": "wrong-password"})
    assert response.status_code == 401
    assert "token" not in response.json()


def test_mobile_login_blocks_admin_before_issuing_token(client, monkeypatch):
    from backend.app import auth

    email = "mobile-admin@example.com"
    assert signup(client, email).status_code == 201
    # Admin configuration may be changed after the account was created.
    monkeypatch.setattr(auth, "ADMINS", {email})
    original = auth.make_token
    calls = []
    def tracked_token(user_id):
        calls.append(user_id)
        return original(user_id)
    monkeypatch.setattr(auth, "make_token", tracked_token)
    response = client.post("/api/auth/player/login", json={"email": email, "password": "password123"})
    assert response.status_code == 403
    assert "admin website" in response.json()["detail"]
    assert "token" not in response.json()
    assert calls == []
    # The existing administrator website remains available.
    assert client.post("/api/auth/login", json={"email": email, "password": "password123"}).status_code == 200
