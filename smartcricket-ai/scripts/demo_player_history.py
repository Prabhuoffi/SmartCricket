"""Build labelled demo training rows without accessing or changing a database.

The caller owns backup, account selection, existing-row cleanup and persistence.
Analysis results are read as evidence; their values and timestamps are never changed.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from backend.app import trainer
from backend.app.models import DailyLog, QuizAnswer, WeeklyReport


TZ = ZoneInfo("Asia/Kolkata")
MAX_DAYS = 90


class _PlanCollector:
    """Let the normal plan builder create ORM rows without persistence or commits."""

    def add_all(self, rows):
        pass

    def commit(self):
        pass


def _instant(value: datetime) -> datetime:
    # Saved SQLite datetimes can lose their UTC offset; this matches trainer.local_day.
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(TZ)


def _schedule(day: date, now: datetime) -> tuple[datetime, list[datetime]]:
    if day == now.date():
        midnight = datetime.combine(day, time.min, TZ)
        checkin = max(midnight, now - timedelta(minutes=5))
        elapsed = now - checkin
        return checkin, [checkin + elapsed * fraction / 3 for fraction in (1, 2, 3)]
    checkin = datetime.combine(day, time(hour=7), TZ)
    practice = datetime.combine(day, time(hour=18), TZ)
    return checkin, [practice + timedelta(minutes=5 * i) for i in range(3)]


def build_history(user, analyses, end_day: date, now: datetime, days: int = 12) -> dict:
    """Return deterministic check-ins, completed plans, correct quizzes and reports.

    All activity is synthetic and labelled. Historical plans use only analysis
    evidence available when practice began, plus preceding training history.
    ``now`` must be timezone-aware; dates and schedules use Asia/Kolkata.
    The returned context is useful for checking the app's derived totals before
    the caller persists the returned row lists in one transaction.
    """
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be a timezone-aware datetime")
    now = now.astimezone(TZ)
    if not isinstance(end_day, date) or isinstance(end_day, datetime) or end_day > now.date():
        raise ValueError("end_day must be a date on or before today in Asia/Kolkata")
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
        raise ValueError(f"days must be between 1 and {MAX_DAYS}")
    if not isinstance(user.id, int) or user.id < 1:
        raise ValueError("user must have a saved positive id")

    evidence = sorted(analyses, key=lambda a: _instant(a.created_at))
    c = trainer.Ctx(user=user, day=end_day)
    logs, drills, quizzes = [], [], []
    collector = _PlanCollector()
    first_day = end_day - timedelta(days=days - 1)

    for index in range(days):
        day = first_day + timedelta(days=index)
        checkin_at, completed_at = _schedule(day, now)
        c.day = day
        c.analyses = [a for a in evidence if _instant(a.created_at) <= completed_at[0]]
        log = DailyLog(user_id=user.id, day=day, balls_faced=(24, 30, 36, 42)[index % 4],
                       soreness="none", feeling=(4, 4, 5)[index % 3], created_at=checkin_at)
        logs.append(log)
        c.logs[day] = log

        plan = trainer.make_plan(collector, c, day)
        for row, finished in zip(plan, completed_at, strict=True):
            row.reason = "Demo activity: " + row.reason
            row.done = True
            row.done_at = finished
        drills.extend(plan)

        question = trainer.quiz_today(c)
        correct_choice = trainer.QUIZ_BY_ID[question["id"]][3]
        answer = QuizAnswer(user_id=user.id, day=day, question=question["id"],
                            choice=correct_choice, correct=True)
        quizzes.append(answer)
        c.quiz[day] = answer

    # Summaries describe all existing evidence as of now, not just the evidence
    # that was available when the final day's plan was generated.
    c.analyses = [a for a in evidence if _instant(a.created_at) <= now]
    reports = []
    for start in sorted({trainer.monday(first_day + timedelta(days=i)) for i in range(days)}):
        stats = trainer.week_stats(c, start)
        reports.append(WeeklyReport(user_id=user.id, week_start=start, stats=stats,
                                    text="Demo training history. " + trainer.template_summary(stats),
                                    created_at=now))
    return {"logs": logs, "drills": drills, "quizzes": quizzes, "reports": reports, "context": c}
