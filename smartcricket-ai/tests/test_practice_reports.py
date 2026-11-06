"""Comparison downloads use the same selected evidence and ownership as the screen."""
from datetime import datetime, timedelta, timezone
import re
import zlib

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import make_token
from backend.app.db import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import Analysis, Media, User


@pytest.fixture(scope="module")
def scenario():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        owner = User(name="Player", email="pdf-player@example.com", password_hash="unused", role="player")
        other = User(name="Other", email="pdf-other@example.com", password_hash="unused", role="player")
        admin = User(name="Admin", email="pdf-admin@example.com", password_hash="unused", role="admin")
        db.add_all([owner, other, admin])
        db.flush()
        captures = []
        for day, value in enumerate((148, 139, 144)):
            media = Media(user_id=owner.id, type="image", file_path="/missing-test-photo.jpg", original_name=f"Capture {day + 1}.jpg")
            capture = Analysis(media=media, mode="image", model="mediapipe", output_path=None,
                               angles={joint: {"deg": value, "visibility": .95} for joint in
                                       ("left_knee", "right_knee", "left_elbow", "right_elbow")},
                               summary={"detected": True, "visible": 30, "quality": {"grade": "Good", "score": 90,
                                   "checks": [{"key": "view", "label": "Side-on view"}]}},
                               created_at=datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=day))
            db.add(capture)
            db.flush()
            captures.append(capture.id)
        db.commit()
        headers = [{"Authorization": f"Bearer {make_token(user.id)}"} for user in (owner, other, admin)]
    with TestClient(app) as client:
        yield client, headers, captures
    Base.metadata.drop_all(engine)


def text_streams(pdf):
    blocks = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        stream = match.group(1).strip()
        # ReportLab's default PDF streams use ASCII85 then zlib.
        import base64
        try:
            blocks.append(zlib.decompress(base64.a85decode(stream, adobe=True)))
        except (ValueError, zlib.error):
            blocks.append(stream)
    return b"\n".join(blocks)


def test_pdf_keeps_signed_changes_and_marks_exploratory_conditions(scenario):
    client, (owner, _, _), (baseline, retest, _) = scenario
    response = client.get("/api/practice/compare/pdf", headers=owner,
                          params={"baseline_id": baseline, "retest_id": retest})
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    text = text_streams(response.content)
    assert b"148.0 degrees" in text and b"139.0 degrees" in text and b"-9.0 degrees" in text
    assert b"Exploratory comparison" in text and b"Confirm matching capture setup" in text
    assert b"not a score of batting skill" in text


def test_pdf_goal_is_owned_and_uses_its_own_baseline(scenario):
    client, (owner, other, admin), (baseline, retest, newer) = scenario
    created = client.post("/api/practice/goals", headers=owner, json={
        "title": "Repeat a balanced stance", "baseline_id": baseline, "focus_joint": "left_knee", "target_deg": 140,
    })
    assert created.status_code == 201
    query = {"baseline_id": baseline, "retest_id": retest, "same_setup": True, "goal_id": created.json()["id"]}
    response = client.get("/api/practice/compare/pdf", headers=owner, params=query)
    assert response.status_code == 200
    assert b"Repeat a balanced stance" in text_streams(response.content)
    assert b"baseline 8.0 degrees; retest 1.0 degrees" in text_streams(response.content)
    assert client.get("/api/practice/compare/pdf", headers=other, params=query).status_code == 404
    assert client.get("/api/practice/compare/pdf", headers=admin, params=query).status_code == 403
    assert client.get("/api/practice/compare/pdf", params=query).status_code == 401
    assert client.get("/api/practice/compare/pdf", headers=owner,
                      params={**query, "baseline_id": retest, "retest_id": newer}).status_code == 400


def test_pdf_rejects_invalid_capture_frames_instead_of_printing_other_evidence(scenario):
    client, (owner, _, _), (baseline, retest, _) = scenario
    response = client.get("/api/practice/compare/pdf", headers=owner,
                          params={"baseline_id": baseline, "retest_id": retest, "baseline_frame": 0})
    assert response.status_code == 400
    assert "Photos do not have" in response.json()["detail"]
