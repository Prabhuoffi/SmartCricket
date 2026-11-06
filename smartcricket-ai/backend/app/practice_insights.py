"""Read-only summaries of owned practice activity and explicit-side photo measurements.

These summaries do not estimate batting skill or classifier accuracy. Known demo
records are excluded by default; older records without provenance cannot be
reliably distinguished from genuine history.
"""
import csv
import io
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Analysis, DailyLog, Media, PlanDrill, PracticeGoal
from .practice import JOINTS, joint_label
from .serialize import timestamp

TZ = ZoneInfo("Asia/Kolkata")
WINDOWS = (7, 14, 30)
INTERPRETATION = (
    "Joint angles are pose estimates from photos, not a technique score. Different camera views, "
    "body sides and movement phases can change the values. Confidence is a model score for a "
    "prediction, not measured accuracy. Activity completion does not establish sporting improvement."
)
PROVENANCE_NOTE = (
    "Explicitly labeled demo captures and drills are identified from stored provenance and Demo labels. "
    "Legacy unmarked synthetic records cannot be reliably identified. Check-ins on days containing only "
    "labeled demo drills are treated as demo activity; mixed or unmarked histories may remain ambiguous."
)


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value) if low <= value <= high else None


def _demo_label(value):
    return isinstance(value, str) and value.strip().lower().startswith(("demo ·", "demo:", "demo activity:"))


def is_demo_capture(analysis):
    summary = analysis.summary if isinstance(analysis.summary, dict) else {}
    provenance = summary.get("demo_provenance")
    return bool(summary.get("synthetic") is True
                or isinstance(provenance, dict) and provenance.get("synthetic_activity") is True
                or _demo_label(analysis.media.session_label))


def _photo_observation(analysis, joint):
    summary = analysis.summary if isinstance(analysis.summary, dict) else {}
    angle = (analysis.angles or {}).get(joint) if isinstance(analysis.angles, dict) else None
    deg = visibility = None
    reason = "No angle with a visibility score is stored for this joint."
    if summary.get("detected") is False:
        reason = "No batter was detected in this photo."
    elif isinstance(angle, dict):
        visibility = _number(angle.get("visibility"), 0, 1)
        value = _number(angle.get("deg"), 0, 180)
        if visibility is None or visibility < settings.min_visibility:
            reason = "Visibility is low or unavailable."
        elif value is None:
            reason = "The stored angle is missing or outside 0–180 degrees."
        else:
            deg, reason = round(value, 1), None
    quality = summary.get("quality")
    quality = quality if isinstance(quality, dict) else {}
    checks = quality.get("checks")
    checks = checks if isinstance(checks, list) else []
    view = next((row.get("label") for row in checks if isinstance(row, dict) and row.get("key") == "view"
                 and row.get("label") in ("Side-on view", "Front-on view", "Angled view")), None)
    grade = quality.get("grade") if quality.get("grade") in ("Good", "Fair", "Poor") else None
    return {
        "analysis_id": analysis.id, "at": timestamp(analysis.created_at),
        "date": _aware(analysis.created_at).astimezone(TZ).date().isoformat(),
        "label": analysis.media.session_label or analysis.media.original_name or f"Photo {analysis.id}",
        "joint": joint, "deg": deg, "visibility": visibility,
        "excluded_reason": reason, "quality": grade, "view": view,
        "visible_landmarks": _number(summary.get("visible"), 0, 33),
        "synthetic": is_demo_capture(analysis),
        "report_url": f"analysis.html?id={analysis.id}",
    }


def build_insights(db: Session, user_id: int, *, days=14, joint="left_knee", include_demo=False,
                   now: datetime | None = None):
    if days not in WINDOWS or isinstance(days, bool):
        raise ValueError("Choose 7, 14 or 30 days.")
    if joint not in JOINTS:
        raise ValueError("Choose a supported joint.")
    instant = _aware(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    end = instant.astimezone(TZ).date()
    start = end - timedelta(days=days - 1)
    start_utc = datetime.combine(start, time.min, TZ).astimezone(timezone.utc)
    captures = list(db.scalars(select(Analysis).join(Media).where(
        Media.user_id == user_id, Analysis.created_at >= start_utc, Analysis.created_at <= instant
    ).order_by(Analysis.created_at, Analysis.id)))
    drills = list(db.scalars(select(PlanDrill).where(
        PlanDrill.user_id == user_id, PlanDrill.day >= start, PlanDrill.day <= end
    ).order_by(PlanDrill.day, PlanDrill.id)))
    logs = list(db.scalars(select(DailyLog).where(
        DailyLog.user_id == user_id, DailyLog.day >= start, DailyLog.day <= end
    ).order_by(DailyLog.day)))
    goals = list(db.scalars(select(PracticeGoal).where(
        PracticeGoal.user_id == user_id).order_by(PracticeGoal.updated_at.desc(), PracticeGoal.id.desc())))
    demo_captures = sum(is_demo_capture(a) for a in captures)
    demo_drills = sum(_demo_label(d.reason) for d in drills)
    demo_only_days = {d.day for d in drills if _demo_label(d.reason)} - {
        d.day for d in drills if not _demo_label(d.reason)
    }
    if not include_demo:
        captures = [a for a in captures if not is_demo_capture(a)]
        drills = [d for d in drills if not _demo_label(d.reason)]
        logs = [row for row in logs if row.day not in demo_only_days]
    log_by_day = {row.day: row for row in logs}
    daily = []
    for index in range(days):
        day = start + timedelta(days=index)
        log = log_by_day.get(day)
        day_drills = [d for d in drills if d.day == day]
        rest = bool(log and log.soreness == "stop")
        active = [d for d in day_drills if d.code != "rest"] if not rest else []
        completed = sum(bool(d.done) for d in active)
        daily.append({"date": day.isoformat(), "checked_in": log is not None,
                      "recovery": rest, "planned_drills": len(active), "completed_drills": completed,
                      "adherence_pct": round(100 * completed / len(active), 1) if active else None,
                      "recovery_drills_completed": sum(bool(d.done) for d in day_drills if d.code == "rest"),
                      "synthetic_activity": day in demo_only_days,
                      "photo_captures": sum(a.mode == "image" for a in captures
                                            if _aware(a.created_at).astimezone(TZ).date() == day),
                      "video_captures": sum(a.mode == "video" for a in captures
                                            if _aware(a.created_at).astimezone(TZ).date() == day)})
    planned = sum(row["planned_drills"] for row in daily)
    completed = sum(row["completed_drills"] for row in daily)
    photos = [_photo_observation(a, joint) for a in captures if a.mode == "image"]
    valid = [row for row in photos if row["deg"] is not None]
    confidences = []
    for analysis in captures:
        if analysis.mode == "video" and analysis.shot:
            value = _number(analysis.confidence, 0, 1)
            if value is not None:
                confidences.append(value)
    goal_rows, excluded_goals = [], 0
    for goal in goals:
        # Guard old/invalid foreign links instead of leaking another player's capture details.
        linked = [a for a in (goal.baseline, goal.retest) if a is not None]
        foreign = any(a.media.user_id != user_id for a in linked)
        synthetic = any(is_demo_capture(a) for a in linked if a.media.user_id == user_id)
        if foreign or synthetic and not include_demo:
            excluded_goals += 1
            continue
        goal_rows.append({"id": goal.id, "title": goal.title, "status": goal.status,
                          "focus_joint": goal.focus_joint, "due_date": goal.due_date.isoformat() if goal.due_date else None,
                          "overdue": goal.status == "active" and bool(goal.due_date and goal.due_date < end),
                          "baseline_available": goal.baseline is not None, "retest_available": goal.retest is not None,
                          "synthetic": synthetic})
    views = {row["view"] for row in valid if row["view"]}
    warnings = ["The photo trend is exploratory: recording setup and movement phase are not automatically matched."]
    if len(views) > 1:
        warnings.append("The selected photo measurements include different camera-view categories.")
    if any(row["view"] is None or row["quality"] not in ("Good", "Fair") for row in valid):
        warnings.append("Some usable angles have unknown or poor recording-quality/view checks.")
    if len(valid) < 2:
        warnings.append("At least two visible measurements of the same joint are needed to inspect a trend.")
    if include_demo:
        warnings.append("Labeled demo records are included. This mixed view must not be presented as real player evidence.")
    return {
        "window": {"days": days, "start": start.isoformat(), "end": end.isoformat(),
                   "timezone": "Asia/Kolkata", "generated_at": timestamp(instant)},
        "filters": {"joint": joint, "include_demo": include_demo},
        "joints": [{"value": name, "label": joint_label(name)} for name in JOINTS],
        "totals": {"captures": len(captures), "photos": len(photos),
                   "videos": sum(a.mode == "video" for a in captures),
                   "planned_drills": planned, "completed_drills": completed,
                   "adherence_pct": round(100 * completed / planned, 1) if planned else None,
                   "checkin_days": len(logs), "recovery_days": sum(row["recovery"] for row in daily),
                   "usable_joint_photos": len(valid),
                   "quality_known_photos": sum(row["quality"] is not None for row in photos),
                   "average_visible_landmarks": round(sum(row["visible_landmarks"] for row in photos
                        if row["visible_landmarks"] is not None) / sum(row["visible_landmarks"] is not None for row in photos), 1)
                        if any(row["visible_landmarks"] is not None for row in photos) else None},
        "confidence": {"mean": round(sum(confidences) / len(confidences), 3) if confidences else None,
                       "predictions": len(confidences),
                       "note": "Mean stored model confidence for classified clips. This is not measured accuracy."},
        "daily": daily, "photos": photos,
        "goals": {"items": goal_rows, "active": sum(g["status"] == "active" for g in goal_rows),
                  "overdue": sum(g["overdue"] for g in goal_rows),
                  "completed": sum(g["status"] == "completed" for g in goal_rows)},
        "provenance": {"include_demo": include_demo, "labeled_demo_captures_in_window": demo_captures,
                       "labeled_demo_drills_in_window": demo_drills, "omitted_goals": excluded_goals,
                       "note": PROVENANCE_NOTE},
        "warnings": warnings, "interpretation": INTERPRETATION,
    }


def _csv_cell(value):
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + value
    return value


def insights_csv(data):
    """Export the exact derived rows, filters and interpretation of the JSON view."""
    output = io.StringIO()
    columns = ["record_type", "date", "label", "value", "planned_drills", "completed_drills", "adherence_pct",
               "analysis_id", "joint", "angle_deg", "visibility", "quality", "camera_view", "synthetic", "note"]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    def row(**values):
        writer.writerow({key: _csv_cell(value) for key, value in values.items()})

    row(record_type="context", label="Window and filters",
        value=f"{data['window']['start']} to {data['window']['end']}; Asia/Kolkata; {data['filters']['joint']}",
        note=f"include_demo={data['filters']['include_demo']}. {data['interpretation']}")
    row(record_type="provenance", label="Known demo-record handling", note=data["provenance"]["note"])
    for key, value in data["totals"].items():
        row(record_type="total", label=key, value=value)
    row(record_type="confidence", label="Mean model confidence, not accuracy", value=data["confidence"]["mean"],
        note=data["confidence"]["note"])
    for item in data["daily"]:
        row(record_type="activity", date=item["date"], planned_drills=item["planned_drills"],
            completed_drills=item["completed_drills"], adherence_pct=item["adherence_pct"],
            synthetic=item["synthetic_activity"], note="Recovery day; no batting drills in denominator." if item["recovery"] else "Recorded planned activity; not a skill score.")
    for item in data["photos"]:
        row(record_type="photo_measurement", date=item["date"], label=item["label"], analysis_id=item["analysis_id"],
            joint=item["joint"], angle_deg=item["deg"], visibility=item["visibility"], quality=item["quality"],
            camera_view=item["view"], synthetic=item["synthetic"], note=item["excluded_reason"] or "Exploratory photo measurement.")
    for item in data["goals"]["items"]:
        row(record_type="goal", date=item["due_date"], label=item["title"], joint=item["focus_joint"],
            value=item["status"], synthetic=item["synthetic"], note="Review overdue." if item["overdue"] else "Manual workflow status, not verified improvement.")
    for warning in data["warnings"]:
        row(record_type="warning", note=warning)
    return "\ufeff" + output.getvalue()
