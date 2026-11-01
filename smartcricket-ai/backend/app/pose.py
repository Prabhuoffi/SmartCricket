"""Image-mode posture analysis with MediaPipe Pose Landmarker (module M2).

Angles are reported only when all three landmarks reach the visibility threshold;
hidden joints are left out rather than guessed (FR-4).
"""
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from . import quality
from .config import settings

MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
             "pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task")
MODEL_PATH = settings.model_dir / "pose_landmarker_heavy.task"

# MediaPipe landmark indices
IDX = {"nose": 0, "l_sh": 11, "r_sh": 12, "l_el": 13, "r_el": 14, "l_wr": 15, "r_wr": 16,
       "l_hip": 23, "r_hip": 24, "l_kn": 25, "r_kn": 26, "l_an": 27, "r_an": 28}
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
         (24, 26), (26, 28), (27, 29), (28, 30), (27, 31), (28, 32), (29, 31), (30, 32)]
ANGLES = {
    "left_elbow": ("l_sh", "l_el", "l_wr"), "right_elbow": ("r_sh", "r_el", "r_wr"),
    "left_knee": ("l_hip", "l_kn", "l_an"), "right_knee": ("r_hip", "r_kn", "r_an"),
    "left_hip": ("l_sh", "l_hip", "l_kn"), "right_hip": ("r_sh", "r_hip", "r_kn"),
    "left_shoulder": ("l_el", "l_sh", "l_hip"), "right_shoulder": ("r_el", "r_sh", "r_hip"),
}
LABEL_ON_IMAGE = ("left_elbow", "right_elbow", "left_knee", "right_knee")

GOOD, HIDDEN, POINT = (60, 200, 60), (170, 170, 170), (0, 140, 255)


def joint_angle(a, b, c, w=1.0, h=1.0, min_vis=None):
    """Angle at b (degrees) for landmarks a-b-c, or None if any point is not visible enough."""
    min_vis = settings.min_visibility if min_vis is None else min_vis
    vis = min(a.visibility, b.visibility, c.visibility)
    if vis < min_vis:
        return None, vis
    ba = np.array([(a.x - b.x) * w, (a.y - b.y) * h])
    bc = np.array([(c.x - b.x) * w, (c.y - b.y) * h])
    cos = ba @ bc / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))), vis


def angles_3d(world: np.ndarray, vis: np.ndarray, min_vis: float | None = None) -> dict:
    """The eight joint angles from MediaPipe's 3D world landmarks (metres, centred on the hips).
    A 3D angle does not depend on where the camera stands, unlike the 2D angle in the picture."""
    min_vis = settings.min_visibility if min_vis is None else min_vis
    out = {}
    for name, (a, b, c) in ANGLES.items():
        i, j, k = IDX[a], IDX[b], IDX[c]
        if min(vis[i], vis[j], vis[k]) < min_vis:
            out[name] = None
            continue
        ba, bc = world[i] - world[j], world[k] - world[j]
        cos = ba @ bc / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
        out[name] = round(float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))), 1)
    return out


class PoseService:
    """Loads the landmarker once; MediaPipe detectors are not thread-safe, so calls are serialised."""

    def __init__(self):
        self._det = None
        self._lock = threading.Lock()

    def _load(self):
        if self._det is not None:
            return
        import mediapipe as mp  # noqa: F401  (imported lazily: slow to import)
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision

        if not MODEL_PATH.exists():
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=str(MODEL_PATH)),
                                            running_mode=vision.RunningMode.IMAGE, num_poses=3)
        self._det = vision.PoseLandmarker.create_from_options(opts)

    def analyse_image(self, path: Path, out_path: Path) -> dict:
        import mediapipe as mp

        img = cv2.imread(str(path))
        h, w = img.shape[:2]
        rgb = np.ascontiguousarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        with self._lock:
            self._load()
            t0 = time.perf_counter()
            res = self._det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            detect_ms = (time.perf_counter() - t0) * 1000

        if not res.pose_landmarks:
            cv2.imwrite(str(out_path), img)
            return {"detected": False, "visible": 0, "total": 33, "angles": {}, "detect_ms": round(detect_ms, 1),
                    "notes": ["No person was found. Try a photo where the whole batter is in view."],
                    "quality": quality.assess([rgb], [None])}

        # up to three people are found; the largest is taken as the batter (not whoever the model listed first)
        people = [np.array([[p.x * w, p.y * h, p.visibility] for p in person]) for person in res.pose_landmarks]
        pick = quality.largest_person(people)
        lm = res.pose_landmarks[pick]
        world = np.array([[p.x, p.y, p.z] for p in res.pose_world_landmarks[pick]]) if res.pose_world_landmarks else None
        q = quality.assess([rgb], [quality.body_stats(people[pick], w, h)], people=len(people))
        th = max(2, w // 400)
        out = img.copy()
        for a, b in EDGES:
            ok = min(lm[a].visibility, lm[b].visibility) >= settings.min_visibility
            cv2.line(out, _px(lm[a], w, h), _px(lm[b], w, h), GOOD if ok else HIDDEN, th, cv2.LINE_AA)
        for i, p in enumerate(lm):
            if 0 < i < 11:  # face detail points are not drawn
                continue
            ok = p.visibility >= settings.min_visibility
            cv2.circle(out, _px(p, w, h), th * 2 + 2, POINT if ok else HIDDEN, -1, cv2.LINE_AA)

        angles, notes = {}, []
        for name, (a, b, c) in ANGLES.items():
            deg, vis = joint_angle(lm[IDX[a]], lm[IDX[b]], lm[IDX[c]], w, h)
            angles[name] = {"deg": None if deg is None else round(deg, 1), "visibility": round(float(vis), 2)}
            if deg is not None and name in LABEL_ON_IMAGE:
                _label(out, f"{deg:.0f}", _px(lm[IDX[b]], w, h), w)
        hidden = [n.replace("_", " ") for n, v in angles.items() if v["deg"] is None]
        if hidden:
            notes.append("Not measured (not clearly visible): " + ", ".join(hidden) + ".")
        borderline = [n.replace("_", " ") for n, v in angles.items()
                      if v["deg"] is not None and v["visibility"] < settings.min_visibility + 0.15]
        if borderline:
            notes.append("Less certain (visibility just above the threshold): " + ", ".join(borderline) + ".")

        sh_ok = min(lm[11].visibility, lm[12].visibility) >= settings.min_visibility
        shoulder_line = None
        if sh_ok:
            dy, dx = (lm[12].y - lm[11].y) * h, (lm[12].x - lm[11].x) * w
            ang = abs(np.degrees(np.arctan2(dy, dx))) % 180
            shoulder_line = round(float(min(ang, 180 - ang)), 1)  # tilt from horizontal, 0 to 90

        cv2.imwrite(str(out_path), out, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return {
            "detected": True,
            "visible": sum(1 for p in lm if p.visibility >= settings.min_visibility),
            "total": len(lm),
            "angles": angles,
            "shoulder_line_deg": shoulder_line,
            "detect_ms": round(detect_ms, 1),
            "image_size": [w, h],
            "notes": notes,
            "quality": q,
            # 3D: world landmarks in metres (hip-centred) and the joint angles measured in 3D
            "world": None if world is None else np.round(world, 4).tolist(),
            "angles_3d": None if world is None else angles_3d(world, np.array([p.visibility for p in lm])),
            # normalised x, y and visibility of all 33 points, for the animated overlay in the browser
            "landmarks": [[round(p.x, 4), round(p.y, 4), round(float(p.visibility), 2)] for p in lm],
            "edges": EDGES,
        }


def _px(p, w, h):
    return int(p.x * w), int(p.y * h)


def _label(img, text, xy, w):
    scale, x, y = max(0.5, w / 900), xy[0] + 8, xy[1] - 8
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), max(3, w // 300), cv2.LINE_AA)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (30, 30, 200), max(1, w // 600), cv2.LINE_AA)


pose_service = PoseService()
