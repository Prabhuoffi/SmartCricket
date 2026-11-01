"""Dynamic Time Warping on joint-angle sequences (module M5, Section 6.6 of the report)."""
import numpy as np

JOINTS = ["left_elbow", "right_elbow", "left_shoulder", "right_shoulder", "left_hip", "right_hip",
          "left_knee", "right_knee"]


def dtw(P: np.ndarray, R: np.ndarray):
    """Align two (frames x joints) angle sequences that may contain NaN for unseen joints.

    Returns (mean cost per aligned step, path as a list of (i, j)).
    The cost of a step is the RMS difference over the joints visible in both frames.
    """
    n, m = len(P), len(R)
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    cost = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            mask = ~np.isnan(P[i]) & ~np.isnan(R[j])
            cost[i, j] = np.sqrt(np.mean((P[i][mask] - R[j][mask]) ** 2)) if mask.any() else 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = cost[i - 1, j - 1] + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        k = int(np.argmin([D[i - 1, j - 1], D[i - 1, j], D[i, j - 1]]))
        i, j = (i - 1, j - 1) if k == 0 else (i - 1, j) if k == 1 else (i, j - 1)
    path.reverse()
    return float(D[n, m] / len(path)), path


def compare(player_seq: list[dict], ref_seq: list[dict]) -> dict:
    """Compare per-frame angle dicts ({joint: degrees or None}) of a player clip and a reference clip."""
    to_arr = lambda seq: np.array([[np.nan if f.get(k) is None else f[k] for k in JOINTS] for f in seq], float)
    P, R = to_arr(player_seq), to_arr(ref_seq)
    distance, path = dtw(P, R)
    per_joint = {}
    for k, name in enumerate(JOINTS):
        diffs = [P[i, k] - R[j, k] for i, j in path if not (np.isnan(P[i, k]) or np.isnan(R[j, k]))]
        per_joint[name] = None if not diffs else {
            "mean_abs_diff": round(float(np.mean(np.abs(diffs))), 1),
            "mean_diff": round(float(np.mean(diffs)), 1),  # positive: the player's joint is more open
            "pairs": len(diffs),
        }
    return {"distance": round(distance, 2), "path": path, "per_joint": per_joint,
            "player": [[None if np.isnan(v) else round(float(v), 1) for v in row] for row in P],
            "reference": [[None if np.isnan(v) else round(float(v), 1) for v in row] for row in R],
            "joints": JOINTS}
