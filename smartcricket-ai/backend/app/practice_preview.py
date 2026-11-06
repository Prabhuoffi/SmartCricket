"""Render saved pose overlays without repeating inference or changing source media."""
from pathlib import Path

import cv2
import numpy as np

from .config import settings
from .pose import EDGES
from .practice import PracticeError, capture_measurements


def capture_preview_bytes(analysis, frame=None) -> bytes:
    _, frame, _ = capture_measurements(analysis, frame)
    output = Path(analysis.output_path) if analysis.output_path else None
    if output is None:
        raise FileNotFoundError("Capture preview unavailable")
    if analysis.mode == "image":
        path = output
    else:
        skeleton = output / f"skel_{frame:02d}.jpg"
        path = skeleton if skeleton.is_file() else output / f"frame_{frame:02d}.jpg"
    picture = cv2.imread(str(path)) if path.is_file() else None
    if picture is None:
        raise FileNotFoundError("Capture preview unavailable")
    if analysis.mode == "video" and not skeleton.is_file():
        sequence = (analysis.summary or {}).get("landmarks")
        if isinstance(sequence, list) and frame < len(sequence):
            try:
                points = np.asarray(sequence[frame], dtype=float)
            except (ValueError, TypeError):
                points = np.empty((0, 3))
            if points.shape == (33, 3):
                h, w = picture.shape[:2]
                seen = np.isfinite(points).all(axis=1) & (points[:, 2] >= settings.min_visibility) & (points[:, 2] <= 1)
                safe_points = np.nan_to_num(points, nan=0, posinf=0, neginf=0)
                xy = np.clip(safe_points[:, :2], -2, 3) * [w, h]
                width = max(2, w // 320)
                for first, second in EDGES:
                    if seen[first] and seen[second]:
                        ends = tuple(xy[first].astype(int)), tuple(xy[second].astype(int))
                        cv2.line(picture, *ends, (210, 233, 243), width + 2, cv2.LINE_AA)
                        cv2.line(picture, *ends, (85, 157, 31), width, cv2.LINE_AA)
                for point in range(11, 33):
                    if seen[point]:
                        cv2.circle(picture, tuple(xy[point].astype(int)), width + 2, (46, 16, 200), -1, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", picture)
    if not ok:
        raise PracticeError("Capture preview could not be rendered")
    return encoded.tobytes()
