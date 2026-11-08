"""Streak display evidence and additive demo refresh use isolated test data."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from backend.app import trainer
from backend.app.db import Base, SessionLocal, engine
from backend.app.models import Analysis, DailyLog, Media, PlanDrill, User
from backend.app.routers.admin import overview
from scripts.refresh_demo_streaks import refresh

NOW = datetime(2026, 11, 6, 16, 0, tzinfo=timezone.utc)
DAY = NOW.astimezone().date()


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(trainer, "today", lambda: DAY)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session
        session.rollback()
    Base.metadata.drop_all(engine)


def player(db, name="Demo Player", email="demo@example.com", role="player"):
    user = User(name=name, email=email, role=role, password_hash="unused-test-hash",
                created_at=NOW - timedelta(days=40))
    db.add(user)
    db.flush()
    return user


def test_snapshot_counts_practice_and_keeps_best_when_current_streak_expires(db):
    user = player(db)
    for offset in (0, 1, 2):
        db.add(DailyLog(user_id=user.id, day=DAY - timedelta(days=offset),
                        soreness="none", created_at=NOW - timedelta(days=offset)))
    db.flush()
    current = trainer.snapshot(user, db)
    assert current["streak"] == current["best_streak"] == 3
    assert datetime.fromisoformat(current["last_active"]) == NOW
    assert current["demo_activity"] is False
    later = DAY + timedelta(days=2)
    assert trainer.streaks(trainer.active_days(trainer.load(user, db)), later) == (0, 3)


def test_admin_last_active_includes_checkins_without_new_uploads(db):
    user = player(db)
    admin = player(db, "Admin", "admin@example.com", role="admin")
    db.add(DailyLog(user_id=user.id, day=DAY, soreness="none", created_at=NOW))
    db.flush()
    data = overview(admin, db)
    assert data["totals"]["active_week"] == 1
    assert data["players"][0]["analyses"] == 0
    assert data["players"][0]["streak"] == data["players"][0]["best_streak"] == 1
    assert datetime.fromisoformat(data["players"][0]["last_active"]) == NOW


def test_demo_refresh_is_additive_labeled_and_idempotent(db):
    user = player(db)
    media = Media(user_id=user.id, type="image", file_path="existing.jpg", original_name="existing.jpg")
    analysis = Analysis(media=media, mode="image", model="pose", summary={"detected": False},
                        angles={}, confidence=.45, created_at=NOW - timedelta(days=4))
    db.add(analysis)
    # Preserve an existing recovery check-in and don't manufacture active drills for it.
    rest_day = DAY - timedelta(days=2)
    db.add(DailyLog(user_id=user.id, day=rest_day, soreness="stop", created_at=NOW - timedelta(days=2)))
    db.flush()
    source = (analysis.created_at, analysis.summary.copy(), analysis.confidence)
    preview = refresh(db, NOW)
    assert preview[0]["added_checkins"] == 6
    assert db.scalar(select(func.count(DailyLog.id))) == 1
    rows = refresh(db, NOW, apply=True)
    assert rows[0]["streak_after"] >= 7
    assert db.scalar(select(func.count(Analysis.id))) == 1
    assert (analysis.created_at, analysis.summary, analysis.confidence) == source
    assert trainer.snapshot(user, db)["demo_activity"] is True
    assert all(row.reason.startswith("Demo activity:") for row in db.scalars(select(PlanDrill)))
    assert not db.scalars(select(PlanDrill).where(PlanDrill.day == rest_day)).all()
    again = refresh(db, NOW, apply=True)
    assert all(again[0][key] == 0 for key in ("added_checkins", "added_drills", "added_quizzes"))
    assert db.scalar(select(func.count(DailyLog.id))) == 7


def test_refresh_skips_real_accounts_admins_and_changed_demo_identity(db):
    player(db, "Actual Player", "actual@example.com")
    player(db, "Different Person", "arjun.sharma@example.com")
    player(db, "Rohan Iyer", "rohan.iyer@example.com", role="admin")
    assert refresh(db, NOW, apply=True) == []
    assert db.scalar(select(func.count(DailyLog.id))) == 0


def test_snapshot_last_activity_includes_a_completed_drill(db):
    user = player(db)
    db.add(PlanDrill(user_id=user.id, day=DAY, code="balance", title="Example", dose="3 reps",
                     difficulty=1, reason="Player practice", done=True, done_at=NOW))
    db.flush()
    result = trainer.snapshot(user, db)
    assert result["streak"] == 1
    assert datetime.fromisoformat(result["last_active"]) == NOW
