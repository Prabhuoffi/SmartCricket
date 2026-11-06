"""Adaptive coaching (module M8): streaks, levels, XP, daily plan, check-in, quiz and weekly report."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app import trainer
from backend.app.db import Base, engine
from backend.app.main import app


# ---------------------------------------------------------------- units

def test_streaks():
    t = date(2026, 10, 30)
    days = {t - timedelta(days=i) for i in (0, 1, 2, 5, 6, 7, 8)}
    assert trainer.streaks(days, t) == (3, 4)
    assert trainer.streaks({t - timedelta(days=1)}, t) == (1, 1)  # still alive until the end of today
    assert trainer.streaks({t - timedelta(days=2)}, t) == (0, 1)


def test_sqlite_naive_utc_is_counted_on_the_correct_local_day(monkeypatch):
    import time
    if not hasattr(time, "tzset"):
        pytest.skip("tzset is needed to verify the local midnight boundary")
    try:
        with monkeypatch.context() as patch:
            patch.setenv("TZ", "Asia/Kolkata")
            time.tzset()
            utc_time = datetime(2026, 11, 3, 20, 30)
            assert trainer.local_day(utc_time) == date(2026, 11, 4)
            assert trainer.local_day(utc_time) == trainer.local_day(utc_time.replace(tzinfo=timezone.utc))
    finally:
        time.tzset()


def test_levels():
    base = {"analyses": 0, "best_streak": 0, "full_photos": 0, "plan_weeks": 0}
    assert trainer.level_info(base)["level"] == 1
    lv = trainer.level_info(base | {"analyses": 5, "best_streak": 3})
    assert lv["level"] == 2 and lv["next"]["name"] == "District" and lv["progress"] == .125
    # level 3 needs level 2 first, even with enough analyses
    assert trainer.level_info(base | {"analyses": 30, "full_photos": 9})["level"] == 1
    top = trainer.level_info({"analyses": 80, "best_streak": 30, "full_photos": 9, "plan_weeks": 3})
    assert top["level"] == 5 and top["next"] is None and top["progress"] == 1


def test_dose_scales_with_difficulty():
    assert trainer.dose("knee_bend", 1)[0] == "2 × 7 reps"
    assert trainer.dose("knee_bend", 2)[0] == "3 × 10 reps"
    assert trainer.dose("knee_bend", 3)[0] == "4 × 13 reps"
    assert trainer.dose("hip_hinge", 2)[0] == "3 × 20 s hold"
    assert trainer.dose("rest", 3)[0] == "10 min"


def test_template_summary_uses_only_given_numbers():
    s = {"days_trained": 5, "drills_done": 12, "drills_planned": 15, "completion_pct": 80, "balls_faced": 140,
         "sore_days": 0, "knee_avg_deg": 150.2, "knee_change_deg": -6.5}
    text = trainer.template_summary(s)
    assert "5 of 7 days" in text and "12 of 15" in text and "6.5° deeper" in text and "step up" in text
    assert "more-bent knee" in text and "similar poses and camera views" in text and "front-knee" not in text


def test_quiz_bank_is_well_formed():
    assert len({q[0] for q in trainer.QUIZ}) == len(trainer.QUIZ)
    assert all(len(q[2]) == 4 and 0 <= q[3] < 4 for q in trainer.QUIZ)


# ---------------------------------------------------------------- API

@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


def register(client, email):
    r = client.post("/api/auth/register", json={"name": "Test Player", "email": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_daily_flow(client):
    h = register(client, "t1@example.com")
    t = client.get("/api/train/today", headers=h).json()
    assert len(t["plan"]) == 3 and t["checkin"] is None and t["reflection"] is None
    assert t["status"]["level"] == 1 and t["status"]["xp"]["total"] == 0

    # soreness that needs rest swaps the plan for a rest day
    t = client.post("/api/train/checkin", headers=h, json={"balls_faced": 40, "soreness": "stop", "feeling": 2}).json()
    assert t["rest_day"] and [d["code"] for d in t["plan"]] == ["rest"]
    # a corrected check-in rebuilds the plan at the easy level for mild soreness
    t = client.post("/api/train/checkin", headers=h, json={"balls_faced": 40, "soreness": "mild", "feeling": 3}).json()
    assert len(t["plan"]) == 3 and not t["rest_day"] and t["difficulty"]["label"] == "Easy"

    first = t["plan"][0]["id"]
    r = client.post(f"/api/train/drills/{first}", headers=h, json={"done": True}).json()
    assert r["done"] and r["status"]["today"]["drills_done"] == 1
    xp = r["status"]["xp"]["parts"]
    assert xp["drill"] == 15 and xp["checkin"] == 5 and xp["streak"] == 5
    assert r["status"]["streak"] == 1

    # once a drill is done, a new check-in keeps the plan
    t = client.post("/api/train/checkin", headers=h, json={"soreness": "none"}).json()
    assert t["plan"][0]["id"] == first and t["plan"][0]["done"]

    other = register(client, "t2@example.com")
    assert client.post(f"/api/train/drills/{first}", headers=other, json={"done": True}).status_code == 404


def test_quiz_once_a_day(client):
    h = register(client, "t3@example.com")
    q = client.get("/api/train/today", headers=h).json()["quiz"]
    right = trainer.QUIZ_BY_ID[q["id"]][3]
    r = client.post("/api/train/quiz", headers=h, json={"choice": right}).json()
    assert r["correct"] and r["status"]["xp"]["parts"]["quiz"] == 10
    assert client.post("/api/train/quiz", headers=h, json={"choice": 0}).status_code == 409
    assert client.get("/api/train/today", headers=h).json()["quiz"]["answered"]["correct"]


def test_progress_week_and_chat(client):
    h = register(client, "t4@example.com")
    p = client.get("/api/train/progress", headers=h).json()
    assert len(p["weeks"]) == 8 and p["status"]["levels"][0]["reached"]
    w = client.post("/api/train/week/summary", headers=h).json()
    assert "so far this week" in w["text"]  # no API key in tests: rule-based summary
    assert client.post("/api/train/week/summary?offset=9", headers=h).status_code == 422
    assert "not set up" in client.post("/api/train/chat", headers=h, json={"text": "What should I do today?"}).json()["reply"]
    assert client.post("/api/train/reflection", headers=h, json={"analysis_id": 1, "answer": "Yes"}).status_code == 409


def test_clip_measurements_for_drills():
    from types import SimpleNamespace as NS
    r = {"left_knee": {"min": 150.0, "max": 175.0}, "right_knee": {"min": 165.0, "max": 178.0},
         "left_shoulder": {"min": 10.0, "max": 30.0}, "right_shoulder": {"min": 5.0, "max": 28.0}}
    seq = [{"left_elbow": 20.0, "right_elbow": 25.0}] * 3 + [{"left_elbow": 120.0, "right_elbow": 140.0}]
    clip = NS(mode="video", summary={"joint_ranges": r, "tracked_frames": 12, "angles_seq": seq, "key_frame": 3})
    m = trainer.measurements(clip)
    assert m["knee"] == 150.0          # deepest bend over the stroke
    assert m["elbow"] == 120.0         # at the frame of most movement, not the backlift minimum
    assert m["shoulder"] == 30.0       # highest arm position
    assert trainer.measurements(NS(mode="video", summary={"joint_ranges": r, "tracked_frames": 3})) is None


def test_rest_checkin_overrides_started_plan_and_preserves_history(client):
    h = register(client, "recovery@example.com")
    original = client.get("/api/train/today", headers=h).json()["plan"]
    first, remaining = original[0]["id"], original[1]["id"]
    assert client.post(f"/api/train/drills/{first}", headers=h, json={"done": True}).status_code == 200

    payload = client.post("/api/train/checkin", headers=h, json={"soreness": "stop"}).json()
    assert payload["rest_day"] and [d["code"] for d in payload["plan"]] == ["rest"]
    assert payload["status"]["today"]["rest_day"]
    assert payload["status"]["today"]["drills_total"] == 1
    assert payload["status"]["xp"]["parts"]["drill"] == 15
    assert client.get("/api/train/today", headers=h).json()["rest_day"]
    assert client.post(f"/api/train/drills/{remaining}", headers=h, json={"done": True}).status_code == 409
    assert client.post("/api/train/live-sessions", headers=h,
                       json={"drill_id": remaining, "title": "Active drill", "duration_s": 30,
                             "completed": True}).status_code == 409

    recovery = payload["plan"][0]["id"]
    result = client.post(f"/api/train/drills/{recovery}", headers=h, json={"done": True}).json()
    assert result["status"]["today"]["drills_done"] == 1
    week = client.get("/api/train/progress", headers=h).json()["weeks"][-1]
    assert week["completion_pct"] == 100 and week["drills_planned"] == 1
    from sqlalchemy import select
    from backend.app.db import SessionLocal
    from backend.app.models import User
    with SessionLocal() as db:
        player = db.scalar(select(User).where(User.email == "recovery@example.com"))
        assert trainer.snapshot(player, db)["plan_pct"] == 100

    # Correcting the check-in restores the original work and keeps its completion.
    corrected = client.post("/api/train/checkin", headers=h, json={"soreness": "none"}).json()
    assert not corrected["rest_day"] and not corrected["status"]["today"]["rest_day"]
    assert [d["id"] for d in corrected["plan"]] == [d["id"] for d in original]
    assert corrected["plan"][0]["done"]
    assert corrected["status"]["xp"]["parts"]["drill"] == 30


def test_live_completion_is_atomic_and_old_drills_are_rejected(client):
    from backend.app.db import SessionLocal
    from backend.app.models import PlanDrill

    h = register(client, "live-completion@example.com")
    drill = client.get("/api/train/today", headers=h).json()["plan"][0]
    body = {"drill_id": drill["id"], "title": drill["title"], "duration_s": 30, "reps": 10, "completed": True}
    saved = client.post("/api/train/live-sessions", headers=h, json=body)
    assert saved.status_code == 201
    assert saved.json()["status"]["today"]["drills_done"] == 1
    assert client.get("/api/train/today", headers=h).json()["plan"][0]["done"]
    again = client.post("/api/train/live-sessions", headers=h, json=body).json()
    assert again["status"]["xp"]["parts"]["drill"] == 15
    with SessionLocal() as db:
        db.get(PlanDrill, drill["id"]).day = trainer.today() - timedelta(days=1)
        db.commit()
    assert client.post("/api/train/live-sessions", headers=h, json=body).status_code == 409


def test_replanning_preserves_saved_live_session(client):
    from backend.app.db import SessionLocal
    from backend.app.models import LiveSession

    h = register(client, "live-replan@example.com")
    drill = client.get("/api/train/today", headers=h).json()["plan"][0]
    response = client.post("/api/train/live-sessions", headers=h,
                           json={"drill_id": drill["id"], "title": drill["title"], "duration_s": 30})
    assert response.status_code == 201
    assert client.post("/api/train/checkin", headers=h, json={"soreness": "mild"}).status_code == 200
    with SessionLocal() as db:
        saved = db.get(LiveSession, response.json()["id"])
        assert saved is not None and saved.drill_id is None and saved.duration_s == 30
