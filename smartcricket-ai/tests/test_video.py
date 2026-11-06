"""Video mode, DTW comparison and admin tests (UT-07, UT-08, IT-04 to IT-06, ST-02, ST-03, ST-05 to ST-08)."""
import io
import json

import cv2
import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from backend.app import dtw
from backend.app import config as cfg
from backend.app.config import settings
from backend.app.db import Base, engine
from backend.app.main import app
from training import sc_common as sc


# ---------------------------------------------------------------- DTW units

def test_dtw_identical():  # UT-07
    P = np.array([[10.0, 20.0], [30.0, 40.0], [50.0, 60.0]])
    d, path = dtw.dtw(P, P.copy())
    assert d == 0 and path == [(0, 0), (1, 1), (2, 2)]


def test_dtw_time_stretched():  # UT-08
    base = np.linspace(60, 170, 8)[:, None]
    slow = np.repeat(base, 2, axis=0)  # same movement at half speed
    d, path = dtw.dtw(base, slow)
    assert d < 1e-6 and path[0] == (0, 0) and path[-1] == (7, 15)


def test_dtw_ignores_unseen_joints():
    P = np.array([[90.0, np.nan], [100.0, np.nan]])
    R = np.array([[90.0, 120.0], [100.0, 130.0]])
    assert dtw.dtw(P, R)[0] == 0


def test_compare_per_joint_sign():
    player = [{j: 100.0 for j in dtw.JOINTS} for _ in range(5)]
    ref = [{j: 90.0 for j in dtw.JOINTS} for _ in range(5)]
    player[0]["left_knee"] = None
    r = dtw.compare(player, ref)
    assert r["per_joint"]["right_knee"]["mean_diff"] == 10.0
    assert r["per_joint"]["left_knee"]["pairs"] == 4
    assert r["distance"] == 10.0


# ---------------------------------------------------------------- API

def make_clip(n=24, w=320, h=180) -> bytes:
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 25, (w, h))
    for t in range(n):
        f = np.full((h, w, 3), 60, np.uint8)
        cv2.circle(f, (60 + t * 8, 90), 20, (255, 255, 255), -1)
        vw.write(f)
    vw.release()
    data = open(path, "rb").read()
    os.unlink(path)
    return data


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture()
def models_dir(tmp_path, monkeypatch):
    """Random-weight checkpoints in a temporary models folder, so the pipeline runs without trained weights."""
    from backend.app.video import video_service
    pose_task = settings.model_dir / "pose_landmarker_full.task"
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    if pose_task.exists():
        (tmp_path / pose_task.name).write_bytes(pose_task.read_bytes())
    for kind in ("video", "pose", "fusion", "pose3d", "fusion3d"):
        torch.manual_seed(0)
        torch.save({"kind": kind, "state_dict": sc.build_model(kind).state_dict(), "temperature": 1.5,
                    "classes": sc.BASE_CLASSES}, tmp_path / f"{kind}.pt")
    video_service.models.clear()
    yield tmp_path
    video_service.models.clear()


def user(client, email, admin=False, monkeypatch=None):
    if admin:
        monkeypatch.setattr(cfg, "ADMINS", {email})
        import backend.app.auth as auth
        monkeypatch.setattr(auth, "ADMINS", {email})
    r = client.post("/api/auth/register", json={"name": "T", "email": email, "password": "password123"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()


def test_status_without_models(client, tmp_path, monkeypatch):
    h, _ = user(client, "v1@example.com")
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    st = client.get("/api/video/status", headers=h).json()
    assert st["ready"] and not st["shot_models"] and st["default"] == "movement"
    r = client.post("/api/video/analyse", headers=h, files={"file": ("a.mp4", make_clip(), "video/mp4")},
                    data={"model": "fusion"})
    assert r.status_code == 503  # a shot model that is not installed


def test_video_wrong_type_and_unreadable(client, models_dir):  # ST-03
    h, _ = user(client, "v2@example.com")
    assert client.post("/api/video/analyse", headers=h, files={"file": ("a.gif", b"GIF89a", "image/gif")}).status_code == 400
    r = client.post("/api/video/analyse", headers=h, files={"file": ("a.mp4", b"not a video", "video/mp4")})
    assert r.status_code == 422


def test_video_too_large(client, models_dir, monkeypatch):  # ST-02
    h, _ = user(client, "v3@example.com")
    monkeypatch.setattr(settings, "max_video_mb", 0)
    r = client.post("/api/video/analyse", headers=h, files={"file": ("a.mp4", make_clip(), "video/mp4")})
    assert r.status_code == 413


@pytest.mark.parametrize("kind", ["fusion", "video", "pose", "fusion3d", "pose3d"])
def test_video_pipeline(client, models_dir, kind):  # IT-04, IT-05, ST-05, ST-07
    h, _ = user(client, f"v4{kind}@example.com")
    r = client.post("/api/video/analyse", headers=h, files={"file": ("clip.mp4", make_clip(), "video/mp4")},
                    data={"model": kind, "session_label": "Nets"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["mode"] == "video" and a["shot"] in sc.CLASSES
    assert 0 < a["confidence"] <= 1 and len(a["top3"]) == 3
    assert abs(sum(a["attention"]) - 1) < 1e-3 and len(a["attention"]) == 15
    s = a["summary"]
    pose_only = kind in ("pose", "pose3d")
    assert s["frames"] == 15 and len(s["angles_seq"]) == 15 and s["has_heatmaps"] == (not pose_only)
    kinds = ["frame", "heat"] if not pose_only else ["frame"]
    for k in kinds:
        assert client.get(f"/api/files/{a['id']}/{k}/{s['key_frame']}", headers=h).status_code == 200
    assert client.get(f"/api/files/{a['id']}/output", headers=h).status_code == 200
    assert "Shot analysis report" in client.get(f"/api/reports/{a['id']}", headers=h).text
    assert client.get(f"/api/reports/{a['id']}/pdf", headers=h).content[:4] == b"%PDF"
    hist = client.get("/api/history", headers=h).json()
    assert "landmarks" not in hist[0]["summary"]  # history stays light
    assert client.get("/api/dashboard", headers=h).json()["videos"] == 1
    assert client.delete(f"/api/analyses/{a['id']}", headers=h).status_code == 204


def test_admin_only(client):
    h, _ = user(client, "p1@example.com")
    assert client.get("/api/admin/users", headers=h).status_code == 403
    assert client.post("/api/admin/references", headers=h, data={"shot": "Pull"},
                       files={"file": ("a.mp4", make_clip(), "video/mp4")}).status_code == 403


def test_evaluations_import(client, monkeypatch):
    h, info = user(client, "admin1@example.com", admin=True, monkeypatch=monkeypatch)
    assert info["role"] == "admin"
    summary = {"best_model": "fusion", "results": [
        {"model": m, "seed": s, "top1": 0.8 + s / 100, "macro_f1": 0.78, "precision": 0.79, "recall": 0.77,
         "ece_before": 0.08, "ece_after": 0.03} for m in ("video", "pose", "fusion") for s in (1, 2, 3)]}
    r = client.post("/api/admin/evaluations", headers=h,
                    files={"file": ("summary.json", json.dumps(summary).encode(), "application/json")})
    assert r.status_code == 200 and r.json()["imported"] == {"video": 3, "pose": 3, "fusion": 3}
    ev = client.get("/api/models", headers=h).json()["evaluations"]
    assert len(ev) == 3 and abs(ev[0]["accuracy"] - 0.82) < 1e-6
    bad = client.post("/api/admin/evaluations", headers=h, files={"file": ("x.json", b"{}", "application/json")})
    assert bad.status_code == 422


@pytest.mark.skipif(not (cfg.ROOT / "tests" / "samples" / "batter_clip.mp4").exists(),
                    reason="needs a real clip with a person: tests/samples/batter_clip.mp4")
def test_reference_and_compare(client, models_dir, monkeypatch):  # IT-06, ST-08
    clip = (cfg.ROOT / "tests" / "samples" / "batter_clip.mp4").read_bytes()
    ha, _ = user(client, "admin2@example.com", admin=True, monkeypatch=monkeypatch)
    ref = client.post("/api/admin/references", headers=ha, data={"shot": "Pull", "label": "Demo pull"},
                      files={"file": ("ref.mp4", clip, "video/mp4")})
    assert ref.status_code == 201, ref.text
    hp, _ = user(client, "player9@example.com")
    a = client.post("/api/video/analyse", headers=hp, files={"file": ("c.mp4", clip, "video/mp4")}).json()
    r = client.post(f"/api/video/{a['id']}/compare", headers=hp, json={"reference_id": ref.json()["id"]})
    assert r.status_code == 200 and r.json()["distance"] < 1e-6  # same clip on both sides


def test_roles_are_separate(client, monkeypatch):  # players analyse and train; admins only manage
    ha, _ = user(client, "admin3@example.com", admin=True, monkeypatch=monkeypatch)
    for method, path in [("get", "/api/train/today"), ("get", "/api/history"), ("get", "/api/dashboard"),
                         ("get", "/api/video/status"), ("post", "/api/train/quiz")]:
        r = getattr(client, method)(path, headers=ha, **({"json": {"choice": 0}} if method == "post" else {}))
        assert r.status_code == 403, (path, r.status_code)
    assert client.post("/api/image/analyse", headers=ha, files={"file": ("a.png", b"x", "image/png")}).status_code == 403
    assert client.get("/api/admin/overview", headers=ha).status_code == 200
    assert client.get("/api/models", headers=ha).status_code == 200
    hp, _ = user(client, "p9@example.com")
    assert client.get("/api/train/today", headers=hp).status_code == 200
    assert client.get("/api/admin/overview", headers=hp).status_code == 403
    overview = client.get("/api/admin/overview", headers=ha).json()
    assert all(p["email"] != "admin3@example.com" for p in overview["players"])  # admins are not listed as players


def test_movement_without_trained_models(client, tmp_path, monkeypatch):  # video works before training
    from backend.app.video import video_service
    pose_task = settings.model_dir / "pose_landmarker_full.task"
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    if pose_task.exists():
        (tmp_path / pose_task.name).write_bytes(pose_task.read_bytes())
    video_service.models.clear()
    h, _ = user(client, "mv1@example.com")
    r = client.post("/api/video/analyse", headers=h, files={"file": ("clip.mp4", make_clip(), "video/mp4")})
    assert r.status_code == 200, r.text
    a = r.json()
    s = a["summary"]
    assert a["model"] == "movement" and a["shot"] is None and a["confidence"] is None
    assert s["frames"] == 15 and len(s["angles_seq"]) == 15 and s["overlay"] == "skeleton"
    assert abs(sum(a["attention"]) - 1) < 1e-3 and 0 <= s["key_frame"] < 15
    assert client.get(f"/api/files/{a['id']}/skel/{s['key_frame']}", headers=h).status_code == 200
    assert client.get(f"/api/reports/{a['id']}/pdf", headers=h).content[:4] == b"%PDF"
    assert "Movement analysis report" in client.get(f"/api/reports/{a['id']}", headers=h).text
    assert client.get("/api/dashboard", headers=h).json()["videos"] == 1


def _jpeg(t):
    f = np.full((180, 320, 3), 60, np.uint8)
    cv2.circle(f, (60 + t * 8, 90), 20, (255, 255, 255), -1)
    return cv2.imencode(".jpg", f)[1].tobytes()


def test_live_recognise(client, tmp_path, monkeypatch, models_dir):
    h, _ = user(client, "rec1@example.com")
    files = [("frames", (f"f{t}.jpg", _jpeg(t), "image/jpeg")) for t in range(15)]
    r = client.post("/api/video/recognise", headers=h, files=files)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["shot"] in sc.CLASSES and 0 < j["confidence"] <= 1 and len(j["top3"]) == 3
    assert client.get("/api/history", headers=h).json() == []          # nothing is stored
    assert client.post("/api/video/recognise", headers=h, files=files[:3]).status_code == 422


def test_live_recognise_needs_models(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    h, _ = user(client, "rec2@example.com")
    files = [("frames", (f"f{t}.jpg", _jpeg(t), "image/jpeg")) for t in range(15)]
    assert client.post("/api/video/recognise", headers=h, files=files).status_code == 503


def test_save_live_session(client):
    h, _ = user(client, "ls1@example.com")
    plan = client.get("/api/train/today", headers=h).json()["plan"]
    r = client.post("/api/train/live-sessions", headers=h, json={"drill_id": plan[0]["id"], "title": plan[0]["title"],
                    "duration_s": 95, "reps": 8, "completed": True, "stats": {"best_metric": "knee", "best_deg": 141}})
    assert r.status_code == 201 and r.json()["status"]["xp"]["parts"]["live"] == 5
    p = client.get("/api/train/progress", headers=h).json()
    assert p["live_sessions"][0]["reps"] == 8 and p["live_sessions"][0]["stats"]["best_deg"] == 141
    other, _ = user(client, "ls2@example.com")
    bad = client.post("/api/train/live-sessions", headers=other, json={"drill_id": plan[0]["id"], "title": "x", "duration_s": 5})
    assert bad.status_code == 404


@pytest.mark.skipif(not (cfg.ROOT / "tests" / "samples" / "batter_clip.mp4").exists(), reason="needs a real clip")
def test_long_video_is_split_into_shots(client, tmp_path, monkeypatch):
    import tempfile, os
    from backend.app.video import video_service
    pose_task = settings.model_dir / "pose_landmarker_full.task"
    monkeypatch.setattr(settings, "model_dir", tmp_path)
    if pose_task.exists():
        (tmp_path / pose_task.name).write_bytes(pose_task.read_bytes())
    # a practice video: stand still, play a stroke, stand still, play it again, stand still
    cap = cv2.VideoCapture(str(cfg.ROOT / "tests" / "samples" / "batter_clip.mp4"))
    stroke = []
    while (ok_f := cap.read())[0]:
        stroke.append(ok_f[1])
    cap.release()
    fd, path = tempfile.mkstemp(suffix=".mp4"); os.close(fd)
    hgt, wid = stroke[0].shape[:2]
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 30, (wid, hgt))
    for part in ([stroke[0]] * 90, stroke, [stroke[0]] * 90, stroke, [stroke[0]] * 90):
        for f in part:
            out.write(f)
    out.release()
    h, _ = user(client, "long1@example.com")
    r = client.post("/api/video/analyse", headers=h, files={"file": ("nets.mp4", open(path, "rb").read(), "video/mp4")})
    os.unlink(path)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("multi") and j["count"] == 2, j.get("shots")
    assert len(client.get("/api/history", headers=h).json()) == 2
