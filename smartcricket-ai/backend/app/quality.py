"""Input quality check (module M2/M3): is this photo or clip good enough to measure, and if not, what to fix.

Every check is a simple, explainable rule on the image or on the detected landmarks, so the player gets a
concrete tip ("turn the camera to the batter's side") instead of silently worse angles.
"""
import cv2
import numpy as np

MIN_VIS = 0.5
HEAD, ANKLES = 0, (27, 28)

# Rule-of-thumb thresholds, chosen on sample photos and clips; each is explained in the tip it produces.
SHARP_BAD, SHARP_WARN = 40, 90        # variance of the Laplacian on a 640-px-wide grey image
DARK, BRIGHT, FLAT = 55, 210, 22      # mean and standard deviation of brightness (0-255)
SMALL = 0.30                          # body height as a share of the image height
SIDE_ON, FRONT_ON = 0.35, 0.65        # shoulder width divided by torso length

PENALTY = {"bad": 30, "warn": 12}


def image_stats(rgb: np.ndarray) -> dict:
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    if grey.shape[1] > 640:
        grey = cv2.resize(grey, (640, int(grey.shape[0] * 640 / grey.shape[1])), interpolation=cv2.INTER_AREA)
    return {"sharpness": float(cv2.Laplacian(grey, cv2.CV_64F).var()),
            "brightness": float(grey.mean()), "contrast": float(grey.std())}


def body_stats(pts: np.ndarray, w: int, h: int) -> dict | None:
    """pts: (33, 3) pixel x, y and visibility of one person."""
    seen = pts[:, 2] >= MIN_VIS
    if seen.sum() < 6:
        return None
    xy = pts[seen, :2]
    height = (xy[:, 1].max() - xy[:, 1].min()) / h
    margin = 0.015
    touches = bool((xy[:, 0] < margin * w).any() or (xy[:, 0] > (1 - margin) * w).any()
                   or (xy[:, 1] < margin * h).any() or (xy[:, 1] > (1 - margin) * h).any())
    whole = bool(seen[HEAD] and all(seen[i] for i in ANKLES)) and not touches
    view = None
    if seen[11] and seen[12] and (seen[23] or seen[24]):
        hips = [i for i in (23, 24) if seen[i]]
        torso = np.linalg.norm(pts[[11, 12], :2].mean(0) - pts[hips, :2].mean(0)) + 1e-6
        view = float(abs(pts[11, 0] - pts[12, 0]) / torso)
    return {"height": float(height), "whole": whole, "view": view}


def largest_person(people: list[np.ndarray]) -> int:
    """Index of the person whose visible points cover the largest box: in a batting photo, the batter."""
    def area(p):
        xy = p[p[:, 2] >= MIN_VIS, :2]
        return 0.0 if len(xy) < 3 else float(np.ptp(xy[:, 0]) * np.ptp(xy[:, 1]))
    return int(np.argmax([area(p) for p in people])) if people else 0


def _check(key, level, label, tip=""):
    return {"key": key, "level": level, "ok": level == "good", "label": label, "tip": tip}


def assess(images: list[np.ndarray], bodies: list[dict | None], people: int = 1, frames: int = 1) -> dict:
    """images: RGB frames (one for a photo). bodies: body_stats per frame (None where no body was found).
    people: most people seen in one frame. frames: number of frames (1 for a photo)."""
    stats = [image_stats(i) for i in images]
    sharp = float(np.median([s["sharpness"] for s in stats]))
    bright = float(np.mean([s["brightness"] for s in stats]))
    contrast = float(np.mean([s["contrast"] for s in stats]))
    found = [b for b in bodies if b]
    checks = []

    checks.append(_check("sharp", "bad", "Blurry", "Hold the camera still and film in good light so the shutter is fast.") if sharp < SHARP_BAD
                  else _check("sharp", "warn", "A little soft", "A steadier camera or more light will sharpen the outline.") if sharp < SHARP_WARN
                  else _check("sharp", "good", "Sharp"))
    if bright < DARK:
        checks.append(_check("light", "bad", "Too dark", "Film in daylight or under the nets lights; avoid shade on the batter."))
    elif bright > BRIGHT:
        checks.append(_check("light", "bad", "Too bright", "Avoid filming into the sun; stand with the sun behind the camera."))
    elif contrast < FLAT:
        checks.append(_check("light", "warn", "Flat, low-contrast light", "A plain background behind the batter helps the body stand out."))
    else:
        checks.append(_check("light", "good", "Good light"))

    if not found:
        checks.append(_check("person", "bad", "No batter found", "Keep the whole batter in the frame, facing side-on to the camera."))
    else:
        if frames > 1:
            share = len(found) / frames
            checks.append(_check("person", "bad" if share < 0.34 else "warn" if share < 0.67 else "good",
                                 f"Body found in {len(found)} of {frames} frames",
                                 "" if share >= 0.67 else "Motion blur or a crowded frame lost the batter in some frames; film closer and in good light."))
        size = float(np.median([b["height"] for b in found]))
        checks.append(_check("size", "warn", "Batter small in the frame", "Move closer, or zoom in, so the batter fills at least half the height.")
                      if size < SMALL else _check("size", "good", "Batter fills the frame"))
        whole = sum(b["whole"] for b in found) / len(found)
        checks.append(_check("whole", "good", "Whole body in view") if whole >= 0.5
                      else _check("whole", "warn", "Part of the body cut off", "Keep head to feet inside the frame, with a little space around."))
        views = [b["view"] for b in found if b["view"] is not None]
        if views:
            v = float(np.median(views))
            checks.append(_check("view", "good", "Side-on view") if v < SIDE_ON
                          else _check("view", "warn", "Angled view", "Turn the camera a little more to the batter's side for the clearest knee and elbow angles.") if v < FRONT_ON
                          else _check("view", "warn", "Front-on view", "Knee and elbow bends look smaller from the front. Film from the side (square of the batter) for posture."))
    if people > 1:
        checks.append(_check("people", "warn", f"{people} people in the frame",
                             "The batter was picked out and followed" + (" across the frames" if frames > 1 else "")
                             + ". Frame only the batter for the most reliable result."))

    score = max(0, 100 - sum(PENALTY.get(c["level"], 0) for c in checks))
    grade = "Good" if score >= 80 else "Fair" if score >= 55 else "Poor"
    return {"score": score, "grade": grade, "checks": checks,
            "measures": {"sharpness": round(sharp, 1), "brightness": round(bright, 1), "contrast": round(contrast, 1)}}
