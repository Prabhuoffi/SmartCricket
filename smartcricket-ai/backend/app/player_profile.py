"""Player-stated capture preferences and an explicit repeatability checklist."""
from .models import PlayerProfile
from .serialize import timestamp

DEFAULTS = {"handedness": "unspecified", "experience": "unspecified", "camera_view": "side-on",
            "focus": "", "notes": ""}
HANDEDNESS = {"unspecified": "Prefer not to state", "right": "Right-handed", "left": "Left-handed"}
EXPERIENCE = {"unspecified": "Not stated", "beginner": "Beginner", "regular": "Regular player",
              "experienced": "Experienced player"}
VIEWS = {"side-on": "Side-on", "front-on": "Front-on", "angled": "Angled"}
INTERPRETATION = ("These are your stated preferences, not measurements or a skill rating. "
                  "Handedness alone does not identify the front leg, visible body side, or movement phase. "
                  "A repeated checklist helps consistency but cannot verify identical recording conditions.")


def capture_checklist(camera_view: str) -> list[dict]:
    view = VIEWS.get(camera_view, VIEWS["side-on"])
    return [
        {"key": "whole_body", "title": "Keep the full body in frame",
         "detail": "Include head, shoulders, hips, knees and feet, with space for the bat through the movement."},
        {"key": "view", "title": f"Repeat your {view.lower()} camera view",
         "detail": "Use the same view for the baseline and retest. A different view can change apparent joint angles."},
        {"key": "camera", "title": "Mark a repeatable camera position",
         "detail": "Keep camera height, distance, orientation and zoom the same; use a stable support where practical."},
        {"key": "body_side", "title": "Confirm the same visible body side",
         "detail": "Check the left/right side in both captures yourself. Your batting handedness does not verify this."},
        {"key": "phase", "title": "Match the shot and movement phase",
         "detail": "Repeat the same shot. For video comparisons, select frames showing the same phase, such as the finish."},
        {"key": "light", "title": "Use clear, consistent light",
         "detail": "Avoid backlighting, motion blur, occluded joints and other people covering the batter."},
        {"key": "review", "title": "Review visibility before saving a comparison",
         "detail": "Retake an unclear capture. Keep setup warnings visible; a changed angle alone does not show better technique."},
    ]


def profile_out(row: PlayerProfile | None) -> dict:
    profile = {key: getattr(row, key) if row is not None else value for key, value in DEFAULTS.items()}
    profile["updated_at"] = timestamp(row.updated_at) if row is not None else None
    return {"saved": row is not None, "profile": profile,
            "options": {"handedness": HANDEDNESS, "experience": EXPERIENCE, "camera_view": VIEWS},
            "checklist": capture_checklist(profile["camera_view"]), "interpretation": INTERPRETATION}
