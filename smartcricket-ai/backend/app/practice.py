"""Evidence-based comparisons of a player's own captures, without a technique score."""
import math
from datetime import datetime, timezone

from .config import settings
from .models import Analysis
from .serialize import timestamp

JOINTS = ("left_elbow", "right_elbow", "left_knee", "right_knee", "left_hip", "right_hip",
          "left_shoulder", "right_shoulder")


class PracticeError(ValueError):
    pass


def joint_label(joint: str) -> str:
    return joint.replace("_", " ").capitalize()


def finite_angle(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and 0 <= value <= 180 else None


def _visible_angle(value) -> float | None:
    if isinstance(value, dict):
        visibility = value.get("visibility")
        if visibility is not None and (isinstance(visibility, bool) or not isinstance(visibility, (int, float))
                                       or not math.isfinite(visibility) or not settings.min_visibility <= visibility <= 1):
            return None
        value = value.get("deg")
    return finite_angle(value)


def capture_measurements(a: Analysis, frame: int | None = None) -> tuple[dict, int | None, int]:
    """Return valid visible 2D angles, resolved frame and available frame count."""
    summary = a.summary if isinstance(a.summary, dict) else {}
    if a.mode == "image":
        if frame is not None:
            raise PracticeError("Photos do not have selectable video frames.")
        raw = a.angles if isinstance(a.angles, dict) and summary.get("detected") is not False else {}
        return {j: _visible_angle(raw.get(j)) for j in JOINTS}, None, 1
    if a.mode != "video":
        raise PracticeError("Only photo and video analyses can be compared.")
    sequence = summary.get("angles_seq")
    if not isinstance(sequence, list) or not sequence:
        raise PracticeError("This video has no stored joint frames. Analyse the clip again or choose another capture.")
    frames = min(len(sequence), 64)  # protected frame URLs support indices 0..63
    if frame is None:
        key = summary.get("key_frame", 0)
        frame = key if isinstance(key, int) and not isinstance(key, bool) and 0 <= key < frames else 0
    if not isinstance(frame, int) or isinstance(frame, bool) or not 0 <= frame < frames:
        raise PracticeError(f"Choose a video frame between 1 and {frames}.")
    raw = sequence[frame] if isinstance(sequence[frame], dict) else {}
    return {j: _visible_angle(raw.get(j)) for j in JOINTS}, frame, frames


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _quality(a: Analysis) -> dict:
    value = (a.summary or {}).get("quality")
    if not isinstance(value, dict):
        return {"grade": None, "score": None}
    score = value.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        score = None
    return {"grade": value.get("grade") if isinstance(value.get("grade"), str) else None, "score": score}


def _view(a: Analysis) -> str | None:
    quality = (a.summary or {}).get("quality") or {}
    checks = quality.get("checks", []) if isinstance(quality, dict) else []
    return next((c.get("label") for c in checks if isinstance(c, dict) and c.get("key") == "view"
                 and c.get("label") in ("Side-on view", "Angled view", "Front-on view")), None)


def capture_out(a: Analysis, frame: int | None, frames: int) -> dict:
    return {"id": a.id, "mode": a.mode, "name": a.media.session_label or a.media.original_name or f"Capture {a.id}",
            "created_at": timestamp(a.created_at), "frame": frame, "frames": frames,
            "preview_url": f"/api/practice/captures/{a.id}/preview" + (f"?frame={frame}" if frame is not None else ""),
            "report_url": f"{'clip' if a.mode == 'video' else 'analysis'}.html?id={a.id}",
            "quality": _quality(a), "shot": a.shot, "uncertain": a.uncertain}


def compare_analyses(baseline: Analysis, retest: Analysis, baseline_frame: int | None = None,
                     retest_frame: int | None = None, same_setup: bool = False) -> dict:
    if baseline.id == retest.id:
        raise PracticeError("Choose two different captures for the baseline and retest.")
    if baseline.mode != retest.mode:
        raise PracticeError("Compare two photos or two videos. Mixed capture types cannot be compared.")
    if baseline.created_at and retest.created_at and _aware(retest.created_at) < _aware(baseline.created_at):
        raise PracticeError("Choose a retest saved on or after the baseline. Swap the captures.")
    left, baseline_frame, n_left = capture_measurements(baseline, baseline_frame)
    right, retest_frame, n_right = capture_measurements(retest, retest_frame)
    rows, omitted = [], []
    for joint in JOINTS:
        b, r = left[joint], right[joint]
        if b is not None and r is not None:
            rows.append({"joint": joint, "label": joint_label(joint), "baseline_deg": round(b, 1),
                         "retest_deg": round(r, 1), "change_deg": round(r - b, 1)})
        else:
            absent = "both captures" if b is None and r is None else "the baseline" if b is None else "the retest"
            omitted.append({"joint": joint, "label": joint_label(joint),
                            "reason": f"Not clearly measured in {absent}."})
    if not rows:
        raise PracticeError("No joint is clearly measured in both captures. Choose clearer captures or another video frame.")

    checks = []
    def check(key, good, label, detail):
        checks.append({"key": key, "level": "good" if good else "warn", "label": label, "detail": detail})

    check("setup", same_setup, "Capture setup confirmed" if same_setup else "Confirm matching capture setup",
          "You confirmed the same shot, body side, camera view, and movement phase. This is a player confirmation."
          if same_setup else "Use the same shot, body side, camera view, and movement phase before interpreting a change.")
    check("visibility", len(rows) >= 4, f"{len(rows)} of 8 joints shared",
          "Only joints clearly measured in both selected captures are compared."
          + (" Fewer than four shared joints makes this a limited comparison." if len(rows) < 4 else ""))
    q1, q2 = _quality(baseline), _quality(retest)
    known_grades = {"Good", "Fair"}
    quality_ok = q1["grade"] in known_grades and q2["grade"] in known_grades
    check("quality", quality_ok, "Capture quality available" if quality_ok else "Capture quality needs attention",
          f"Baseline: {q1['grade'] or 'unavailable'}. Retest: {q2['grade'] or 'unavailable'}. "
          "Quality checks describe the recording, not batting skill.")
    view1, view2 = _view(baseline), _view(retest)
    view_ok = bool(view1 and view1 == view2)
    check("view", view_ok, "Camera-view checks match" if view_ok else "Camera views may differ",
          f"Baseline: {view1 or 'unavailable'}. Retest: {view2 or 'unavailable'}. "
          "Matching categories do not prove identical camera position.")
    shot_mismatch = bool(baseline.shot and retest.shot and not baseline.uncertain and not retest.uncertain
                         and baseline.shot != retest.shot)
    check("shot", not shot_mismatch, "Shot labels do not conflict" if not shot_mismatch else "Shot predictions differ",
          f"Baseline prediction: {baseline.shot or 'not identified'}. Retest prediction: {retest.shot or 'not identified'}. "
          "Confirm the actual shot yourself; predictions can be wrong.")
    comparable = all(c["level"] == "good" for c in checks)
    return {"baseline": capture_out(baseline, baseline_frame, n_left),
            "retest": capture_out(retest, retest_frame, n_right), "rows": rows, "omitted": omitted,
            "common_joints": len(rows), "comparable": comparable, "checks": checks,
            "note": ("Capture checks are consistent; interpret the measured differences in context. " if comparable else
                     "This is an exploratory comparison because one or more capture checks need attention. ")
                    + "Change is retest minus baseline, in degrees. A smaller or larger angle alone does not establish better technique or prove that practice caused the change."}
