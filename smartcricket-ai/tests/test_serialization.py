from datetime import datetime, timedelta, timezone

from backend.app.models import Analysis, CoachMessage
from backend.app.serialize import analysis_out, timestamp


def test_timestamps_keep_utc_explicit_when_sqlite_removes_timezone():
    naive = datetime(2026, 11, 4, 18, 45)
    assert timestamp(naive) == "2026-11-04T18:45:00+00:00"
    assert timestamp(None) is None
    india = timezone(timedelta(hours=5, minutes=30))
    assert timestamp(naive.replace(tzinfo=india)).endswith("+05:30")


def test_analysis_and_coach_message_use_the_same_timestamp_contract():
    analysis = Analysis(id=1, mode="image", created_at=datetime(2026, 11, 4, 18, 45),
                        messages=[CoachMessage(role="coach", text="Review your report.",
                                               created_at=datetime(2026, 11, 4, 18, 46))])
    result = analysis_out(analysis, with_messages=True)
    assert result["created_at"].endswith("+00:00")
    assert result["messages"][0]["created_at"].endswith("+00:00")
