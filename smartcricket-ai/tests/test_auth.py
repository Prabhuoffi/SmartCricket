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
