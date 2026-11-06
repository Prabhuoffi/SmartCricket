"""Write a deterministic, fictional UI fixture; never reads models or databases.

Run from any directory: .venv/bin/python scripts/build_showcase.py
All dates, measurements and activity are invented. This is not training data.
"""
import copy
import json
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOINTS = ("left_elbow", "right_elbow", "left_shoulder", "right_shoulder",
          "left_hip", "right_hip", "left_knee", "right_knee")
LABEL = "SYNTHETIC DEMONSTRATION DATA — not real player evidence or model evaluation"


def capture(day, values, view="side-on", quality="clear", phase="finish", visibility=None):
    visibility = visibility or {}
    return {"date": day, "mode": "photo", "view": view, "quality": quality,
            "shot": "Cover drive", "phase": phase, "body_side": "left side visible",
            "angles": {joint: {"deg": value, "visibility": visibility.get(joint, .94)}
                       for joint, value in zip(JOINTS, values, strict=True)}}


def sessions(offset=0, recovery=False):
    start = date(2026, 10, 23)
    counts = [3, 2, 3, 1, 3, 3, 0, 3, 2, 3, 3, 2, 3, 3]
    result = []
    for i in range(14):
        rest = i == 6 or (recovery and i in (10, 11, 12, 13))
        completed = max(0, counts[(i + offset) % len(counts)] - (1 if offset == 2 else 0))
        result.append({"date": (start + timedelta(days=i)).isoformat(),
                       "check_in": "Rest" if rest else "Ready",
                       "planned": 0 if rest else 3,
                       "completed": 0 if rest else completed,
                       "note": "Fictional recovery day; no drills scheduled." if rest
                       else "Fictional shadow-batting, balance and repeat-capture practice."})
    return result


def build():
    before = capture("2026-10-23", [145, 103, 53, 62, 151, 155, 148, 159])
    after = capture("2026-11-05", [139, 107, 56, 61, 149, 154, 141, 157])
    base = {"synthetic": True, "provenance": LABEL, "player": "Fictional Player A",
            "handedness": "Right-handed (fictional profile)", "setup_confirmed": True,
            "baseline": before, "retest": after,
            "goal": {"title": "Repeat a personal finish position", "focus_joint": "left_knee",
                     "target_deg": 140, "status": "Active — fictional workflow status",
                     "review_date": "2026-11-06",
                     "notes": "This illustrative target is chosen for the demo; it is not an ideal batting angle."},
            "sessions": sessions()}
    scenarios = []

    def add(identifier, title, description, change=None):
        value = copy.deepcopy(base)
        value.update({"id": identifier, "title": title, "description": description})
        if change:
            change(value)
        scenarios.append(value)

    add("matched-setup", "Same setup, closer to a personal number",
        "A fictional baseline and retest share the stated recording setup. The focus angle is closer to the selected personal target; no skill gain is inferred.")

    def farther(value):
        value["player"] = "Fictional Player B"
        value["retest"]["angles"]["left_knee"]["deg"] = 155
        value["sessions"] = sessions(1)
    add("farther-target", "Same setup, farther from a personal number",
        "Practice activity can be present while a new measurement is farther from a chosen target. The page does not turn attendance into a technique claim.", farther)

    def mismatched(value):
        value["player"] = "Fictional Player C"
        value["retest"]["view"] = "front-on"
        value["retest"]["phase"] = "contact"
        value["setup_confirmed"] = False
        value["sessions"] = sessions(2)
    add("capture-mismatch", "Camera and movement phase mismatch",
        "A different camera view and movement phase make the displayed changes exploratory. This illustrates why capture guidance matters.", mismatched)

    def occluded(value):
        value["player"] = "Fictional Player D"
        value["retest"]["quality"] = "poor light"
        for joint in ("left_elbow", "right_elbow", "left_hip", "left_knee", "right_knee"):
            value["retest"]["angles"][joint]["visibility"] = .29
        value["retest"]["angles"]["right_hip"]["deg"] = None
        value["sessions"] = sessions(3)
    add("low-visibility", "Low visibility and missing measurements",
        "Occluded joints and a missing angle are excluded, leaving only two shared joints. The personal target cannot be evaluated when its joint is excluded.", occluded)

    def recovery(value):
        value["player"] = "Fictional Player E"
        value["goal"]["title"] = "Keep a consistent capture routine"
        value["goal"]["target_deg"] = None
        value["goal"]["status"] = "Paused for rest — fictional workflow status"
        value["sessions"] = sessions(4, recovery=True)
    add("recovery", "Recovery days and honest activity totals",
        "Rest days contain no planned drills. The activity denominator excludes them, and the goal has no numeric angle target.", recovery)

    def left_handed(value):
        value["player"] = "Fictional Player F"
        value["handedness"] = "Left-handed (fictional profile)"
        value["goal"].update(focus_joint="right_knee", target_deg=154,
                             title="Repeat a chosen right-knee measurement")
        value["goal"]["notes"] = "The right knee is selected explicitly. Handedness alone does not identify a front or back leg."
        value["baseline"]["body_side"] = value["retest"]["body_side"] = "right side visible"
        value["retest"]["angles"]["right_knee"]["deg"] = 153
    add("left-handed-focus", "Left-handed profile with an explicit joint",
        "The player chooses the right knee explicitly. The example does not infer a front leg, an ideal angle or better batting from handedness.", left_handed)

    def all_rest(value):
        value["player"] = "Fictional Player G"
        value["goal"].update(target_deg=None, status="Paused — fictional rest period")
        for session in value["sessions"]:
            session.update(check_in="Rest", planned=0, completed=0,
                           note="Fictional rest period. There are no planned drills and no adherence percentage.")
    add("all-rest", "A full rest period with no percentage",
        "Fourteen rest days produce zero planned drills. Adherence is unavailable, rather than an invented zero or perfect score.", all_rest)

    def unchanged(value):
        value["player"] = "Fictional Player H"
        value["retest"]["angles"] = copy.deepcopy(value["baseline"]["angles"])
        value["goal"].update(status="Completed manually — fictional workflow status",
                             notes="A completed workflow can contain unchanged measurements. Completion is not a verified skill result.")
    add("unchanged-measurements", "Unchanged measurements and manual completion",
        "Every signed change is zero. The fictional goal is manually complete, demonstrating that a workflow status does not prove physical improvement.", unchanged)

    def video_frames(value):
        value["player"] = "Fictional Player I"
        for capture_value, frame in ((value["baseline"], 11), (value["retest"], 13)):
            capture_value.update(mode="video", selected_frame=frame, frame_count=15)
        value["goal"]["notes"] = "Fictional selected-frame snapshots at the stated finish phase; no automatic phase alignment or model inference."
    add("video-frames", "Video snapshots at explicitly selected frames",
        "Constructed video-frame measurements illustrate matching a movement phase even when frame indices differ. No footage or automatic alignment is implied.", video_frames)

    def different_shot(value):
        value["player"] = "Fictional Player J"
        value["retest"]["shot"] = "Sweep"
        value["setup_confirmed"] = False
    add("different-shot", "Different stated shots need a new capture",
        "The fictional baseline is a cover drive and the retest is a sweep. Numeric changes remain descriptive, with a clear stated-shot mismatch warning.", different_shot)

    return {"schema_version": 1, "synthetic": True, "provenance": LABEL,
            "purpose": "UI and presentation demonstration only; never use as training, test, or accuracy evidence.",
            "date_note": "Dates are fixed fictional scenario dates, not timestamps of real captures.",
            "interpretation": "Angle changes and personal target distances do not establish better batting technique or causal improvement.",
            "scenarios": scenarios}


if __name__ == "__main__":
    target = ROOT / "frontend" / "data" / "showcase.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fixture = build()
    target.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    count = len(fixture["scenarios"])
    days = sum(len(s["sessions"]) for s in fixture["scenarios"])
    print(f"Wrote {count} synthetic scenarios and {days} fictional practice days to {target.relative_to(ROOT)}")
