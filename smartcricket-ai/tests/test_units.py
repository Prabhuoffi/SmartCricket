"""Unit tests UT-05, UT-06, UT-12, UT-13 from Chapter 7 of the report."""
from types import SimpleNamespace as P

import numpy as np

from backend.app.auth import hash_password, verify_password
from backend.app.coach import numbers_grounded
from backend.app.pose import joint_angle


def test_right_angle():  # UT-05
    deg, _ = joint_angle(P(x=0, y=1, visibility=1), P(x=0, y=0, visibility=1), P(x=1, y=0, visibility=1))
    assert abs(deg - 90.0) < 0.1


def test_straight_line():
    deg, _ = joint_angle(P(x=-1, y=0, visibility=1), P(x=0, y=0, visibility=1), P(x=1, y=0, visibility=1))
    assert abs(deg - 180.0) < 0.1


def test_low_visibility_not_measured():  # UT-06
    deg, vis = joint_angle(P(x=0, y=1, visibility=0.3), P(x=0, y=0, visibility=1), P(x=1, y=0, visibility=1))
    assert deg is None and vis == 0.3


def test_pixel_aspect_used():
    # In a 2:1 image, normalised points that look 45 degrees apart are really at a different angle.
    deg, _ = joint_angle(P(x=1, y=0, visibility=1), P(x=0, y=0, visibility=1), P(x=1, y=1, visibility=1), w=2, h=1)
    assert abs(deg - 26.57) < 0.1


def test_coach_guard():  # UT-12
    facts = {"angles_deg": {"left_knee": 128.0, "right_knee": None}, "landmarks_visible": 33, "confidence": 0.83}
    assert numbers_grounded("Measured: your left knee is at 128 degrees.", facts)
    assert numbers_grounded("Measured: 83% confident. Try 3 sets of 10.", facts)
    assert not numbers_grounded("Measured: your right knee is at 145 degrees.", facts)
    # general cricket knowledge may use its own numbers, but only inside a "General tip:" paragraph
    assert numbers_grounded("Measured: your left knee is at 128 degrees.\n\nGeneral tip: the pitch is 22 yards, "
                            "and a high elbow near 90 degrees helps the drive.", facts)
    assert not numbers_grounded("General tip: keep the elbow high.\n\nYour right knee is at 145 degrees.", facts)


def test_password_hash():  # UT-13
    h = hash_password("correct horse")
    assert verify_password("correct horse", h)
    assert not verify_password("wrong", h)


# ---------------------------------------------------------------- input quality and smoothing
def test_quality_flags_dark_and_missing_batter():
    from backend.app import quality
    dark = np.full((240, 320, 3), 20, np.uint8)
    q = quality.assess([dark], [None])
    levels = {c["key"]: c["level"] for c in q["checks"]}
    assert levels["light"] == "bad" and levels["person"] == "bad" and q["grade"] == "Poor"


def test_quality_view_side_on_vs_front_on():
    from backend.app import quality
    pts = np.zeros((33, 3)); pts[:, 2] = 1.0
    pts[:, :2] = [[100, 100]] * 33
    pts[0] = [100, 20, 1]; pts[27] = [95, 300, 1]; pts[28] = [105, 300, 1]
    pts[23], pts[24] = [98, 200, 1], [102, 200, 1]
    pts[11], pts[12] = [97, 80, 1], [103, 80, 1]          # shoulders close together: side-on
    assert quality.body_stats(pts, 400, 320)["view"] < quality.SIDE_ON
    pts[11], pts[12] = [60, 80, 1], [140, 80, 1]          # shoulders wide apart: front-on
    assert quality.body_stats(pts, 400, 320)["view"] > quality.FRONT_ON


def test_largest_person_is_the_batter():
    from backend.app import quality
    small = np.array([[10, 10, 1], [20, 20, 1], [15, 30, 1]] + [[0, 0, 0]] * 30, float)
    big = np.array([[100, 100, 1], [200, 300, 1], [150, 200, 1]] + [[0, 0, 0]] * 30, float)
    assert quality.largest_person([small, big]) == 1


def test_smoothing_fills_short_gaps_only():
    from backend.app.video import smooth_landmarks
    lm = np.zeros((6, 33, 3)); lm[:, :, 2] = 1.0
    lm[:, 25, 0] = np.arange(6) * 10.0                     # knee moving steadily right
    lm[2, 25, 2] = 0.1                                     # lost for one frame
    out, filled = smooth_landmarks(lm, 640, 480)
    assert filled == 1 and out[2, 25, 2] >= 0.5 and abs(out[2, 25, 0] - 20.0) < 1e-6
    lm[1:5, 30, 2] = 0.1                                   # lost for four frames: too long to guess
    out, _ = smooth_landmarks(lm, 640, 480)
    assert (out[1:5, 30, 2] < 0.5).all()


def test_follow_batter_ignores_bowler_at_bottom_edge():
    from backend.app.video import follow_batter
    def person(x, y, hgt=100):
        p = np.zeros((33, 3)); p[:, 2] = 1.0
        p[:, 0] = x + np.linspace(-10, 10, 33); p[:, 1] = y + np.linspace(-hgt / 2, hgt / 2, 33)
        return p
    W, H = 640, 540
    # frames 0-2: only the bowler is found, close to the camera at the bottom edge
    # frames 3-8: the batter in the middle of the frame; frame 9: after a camera cut, the batter elsewhere
    found = [[person(430, 470, 140)] for _ in range(3)] + [[person(320, 280)] for _ in range(6)] + [[person(300, 180)], [person(300, 182)]]
    lm = follow_batter(found, W, H)
    kept = [(lm[t, :, 2] >= 0.5).sum() >= 6 for t in range(len(found))]
    assert kept == [False] * 3 + [True] * 6 + [True, True]
