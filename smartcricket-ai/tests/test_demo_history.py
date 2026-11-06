from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from backend.app import trainer
from backend.app.models import Analysis, User
from scripts.demo_player_history import build_history


TZ = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 11, 5, 0, 1, tzinfo=TZ)


def player():
    return User(id=42, name="Demo Player", email="demo@example.com", role="player",
                created_at=NOW - timedelta(days=30))


def snapshot(history):
    return {key: [{column.name: getattr(row, column.name) for column in row.__table__.columns}
                  for row in rows] for key, rows in history.items() if key != "context"}


def test_complete_twelve_day_history_uses_actual_rules_and_correct_quizzes():
    user = player()
    history = build_history(user, [], NOW.date(), NOW)
    c = history["context"]
    dates = [NOW.date() - timedelta(days=i) for i in range(11, -1, -1)]
    assert len(history["logs"]) == len(history["quizzes"]) == 12
    assert len(history["drills"]) == 36
    assert [row.day for row in history["logs"]] == dates
    assert trainer.status(c)["streak"] == 12
    assert trainer.status(c)["xp"]["total"] == 835
    assert trainer.status(c)["today"] == {
        "checked_in": True, "drills_done": 3, "drills_total": 3, "quiz_done": True, "rest_day": False,
    }
    assert all(row.soreness == "none" for row in history["logs"])
    for day in dates:
        rows = trainer.daily_drills(c, day)
        assert len(rows) == len({row.code for row in rows}) == 3
        assert all(row.code in trainer.DRILLS and row.code != "rest" and row.done for row in rows)
        for row in rows:
            assert row.reason.startswith("Demo activity: ")
            assert row.dose == trainer.dose(row.code, row.difficulty)[0]
        answer = c.quiz[day]
        expected = trainer.quiz_today(trainer.Ctx(user=user, day=day))
        assert answer.question == expected["id"]
        assert answer.choice == trainer.QUIZ_BY_ID[answer.question][3]
        assert answer.correct is True
    assert [trainer.daily_drills(c, day)[0].difficulty for day in dates] == [2, 2] + [3] * 10


@pytest.mark.parametrize("now", [NOW, NOW.replace(hour=0, minute=0, second=0),
                                 NOW.astimezone(timezone.utc)])
def test_no_future_timestamps_even_at_india_midnight(now):
    history = build_history(player(), [], now.astimezone(TZ).date(), now)
    for log in history["logs"]:
        completed = [row.done_at for row in history["drills"] if row.day == log.day]
        assert log.created_at <= completed[0] <= completed[1] <= completed[2] <= now
        assert log.created_at.astimezone(TZ).date() == log.day
        assert all(value.astimezone(TZ).date() == log.day for value in completed)
    assert all(report.created_at <= now for report in history["reports"])


def test_builder_is_deterministic_and_reports_match_derived_totals():
    user = player()
    before = user.created_at
    first = build_history(user, [], NOW.date(), NOW)
    second = build_history(user, [], NOW.date(), NOW)
    assert snapshot(first) == snapshot(second)
    assert user.created_at == before
    assert sum(report.stats["drills_done"] for report in first["reports"]) == 36
    assert sum(report.stats["drills_planned"] for report in first["reports"]) == 36
    assert sum(report.stats["days_trained"] for report in first["reports"]) == 12
    assert sum(report.stats["quiz_correct"] for report in first["reports"]) == 12
    assert sum(report.stats["quiz_answered"] for report in first["reports"]) == 12
    assert sum(report.stats["balls_faced"] for report in first["reports"]) == sum(
        log.balls_faced for log in first["logs"])
    assert all(report.text.startswith("Demo training history. ") for report in first["reports"])
    assert all(report.stats == trainer.week_stats(first["context"], report.week_start)
               for report in first["reports"])


def test_plan_uses_only_evidence_available_at_practice_and_keeps_results_unchanged():
    # This measured photo arrives after day one's practice, so it may inform
    # day two but cannot retroactively alter day one's general plan.
    first_day = NOW.date() - timedelta(days=11)
    measured_at = datetime.combine(first_day, datetime.min.time(), TZ) + timedelta(hours=19)
    analysis = Analysis(id=7, mode="image", created_at=measured_at, summary={"detected": True},
                        angles={"left_knee": {"deg": 175}, "right_knee": {"deg": 170}})
    future = SimpleNamespace(created_at=NOW + timedelta(seconds=1), mode="image")
    original = (analysis.created_at, analysis.angles.copy(), analysis.summary.copy())
    history = build_history(player(), [future, analysis], NOW.date(), NOW)
    first = [row for row in history["drills"] if row.day == first_day]
    second = [row for row in history["drills"] if row.day == first_day + timedelta(days=1)]
    assert all(row.code in trainer.GENERAL for row in first)
    assert second[0].code == "knee_bend"
    assert history["context"].analyses == [analysis]
    assert (analysis.created_at, analysis.angles, analysis.summary) == original


@pytest.mark.parametrize("kwargs", [{"days": 0}, {"days": 91}, {"days": True},
                                   {"end_day": date(2026, 11, 6)},
                                   {"now": NOW.replace(tzinfo=None)}])
def test_invalid_ranges_and_naive_now_are_rejected(kwargs):
    params = {"user": player(), "analyses": [], "end_day": NOW.date(), "now": NOW}
    params.update(kwargs)
    with pytest.raises(ValueError):
        build_history(**params)
