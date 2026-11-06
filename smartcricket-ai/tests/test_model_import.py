"""Invalid model-result imports preserve existing results and return useful errors."""
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.auth import make_token
from backend.app.db import Base, SessionLocal, engine
from backend.app.main import app
from backend.app.models import ModelEvaluation, User
from backend.app.routers.admin import MAX_EVALUATION_BYTES, MAX_EVALUATION_ROWS


def result(model="fusion", **changes):
    return {"model": model, "seed": 1, "top1": .8, "macro_f1": .78, "precision": .79,
            "recall": .77, "ece_before": .08, "ece_after": .03, **changes}


@pytest.fixture
def scenario():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin = User(name="Import admin", email="import-admin@example.com", password_hash="unused", role="admin")
        player = User(name="Import player", email="import-player@example.com", password_hash="unused", role="player")
        db.add_all([admin, player, ModelEvaluation(model_name="video", accuracy=.6, macro_f1=.59, precision=.61,
                                                 recall=.58, ece_before=.08, ece_after=.04)])
        db.flush()
        headers = [{"Authorization": f"Bearer {make_token(user.id)}"} for user in (admin, player)]
        db.commit()
    with TestClient(app) as client:
        yield client, headers
    Base.metadata.drop_all(engine)


def upload(client, headers, payload):
    content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return client.post("/api/admin/evaluations", headers=headers,
                       files={"file": ("summary.json", content, "application/json")})


@pytest.mark.parametrize("payload", [
    b"not JSON", b"\xff", {}, [], {"results": []}, {"results": {}}, {"results": [None]},
    {"results": [result(), {"model": "fusion"}]},
    {"results": [result("unknown")]}, {"results": [result(model=[])]},
    {"results": [result(top1=True)]}, {"results": [result(top1="0.8")]},
    {"results": [result(top1=None)]}, {"results": [result(top1=-.1)]},
    {"results": [result(top1=1.1)]}, {"results": [result(top1=float("nan"))]},
    {"results": [result(ece_before=float("inf"))]}, {"results": [result(recall=10**1000)]},
])
def test_invalid_import_keeps_saved_evaluations(scenario, payload):
    client, (admin, _) = scenario
    before = client.get("/api/models", headers=admin).json()["evaluations"]
    response = upload(client, admin, payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get("/api/models", headers=admin).json()["evaluations"] == before


def test_size_and_row_limits_preserve_saved_results(scenario):
    client, (admin, _) = scenario
    before = client.get("/api/models", headers=admin).json()["evaluations"]
    assert upload(client, admin, b" " * (MAX_EVALUATION_BYTES + 1)).status_code == 413
    assert upload(client, admin, {"results": [result()] * (MAX_EVALUATION_ROWS + 1)}).status_code == 422
    assert client.get("/api/models", headers=admin).json()["evaluations"] == before


def test_valid_seed_rows_are_averaged_and_replace_previous_results(scenario):
    client, (admin, _) = scenario
    rows = [result(model, seed=seed, top1=score) for model in ("fusion", "pose3d")
            for seed, score in ((1, .7), (2, .9))]
    response = upload(client, admin, {"results": rows})
    assert response.status_code == 200 and response.json()["imported"] == {"fusion": 2, "pose3d": 2}
    saved = client.get("/api/models", headers=admin).json()["evaluations"]
    assert {row["model"] for row in saved} == {"fusion", "pose3d"}
    assert all(row["accuracy"] == pytest.approx(.8) and row["macro_f1"] == .78 for row in saved)


def test_model_import_requires_administrator(scenario):
    client, (_, player) = scenario
    assert upload(client, player, {"results": [result()]}).status_code == 403
    assert upload(client, {}, {"results": [result()]}).status_code == 401
