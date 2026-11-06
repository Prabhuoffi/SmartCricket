"""Video-mode analysis (modules M3, M4, M5, M6).

Loads the models trained in training/SmartCricket_Train.ipynb (models/video.pt, pose.pt, fusion.pt) and
runs the same frame sampling and pose features as training, through training/sc_common.py.
"""
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np
import torch

from training import sc_common as sc

from . import quality
from .config import settings
from .dtw import JOINTS

KINDS = ["fusion", "fusion3d", "video", "pose", "pose3d"]   # trained shot classifiers (need models/<kind>.pt)
MOVEMENT = "movement"                          # body-movement analysis only: works without any trained model
LABELS = {"fusion": "Video + pose", "video": "Video only", "pose": "Pose only", "fusion3d": "Video + 3D pose",
          "pose3d": "3D pose only", MOVEMENT: "Movement analysis"}
# landmarks whose frame-to-frame travel measures how much the batter is moving (wrists follow the bat)
MOTION_POINTS = [13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
FRAME_W = 480  # width of saved frame images


class VideoService:
    def __init__(self):
        self.models: dict[str, dict] = {}
        self.backbones: dict[str, tuple] = {}   # backbone name -> (model, last conv block), loaded on first use
        self.pose = None
        self.lock = threading.Lock()
        self.device = torch.device(settings.torch_device)

    # ------------------------------------------------------------ loading
    def available(self) -> list[dict]:
        out = []
        for k in KINDS:
            p = settings.model_dir / f"{k}.pt"
            if p.exists():
                out.append({"kind": k, "label": LABELS[k]})
        return out

    def _load(self, kind: str):
        if self.pose is None:
            self.pose = self._make_pose()
        if kind not in self.models:
            path = settings.model_dir / f"{kind}.pt"
            if not path.exists():
                raise FileNotFoundError(f"{path.name} is not installed")
            ckpt = torch.load(path, map_location="cpu", weights_only=False)
            state = ckpt["state_dict"]
            # the video stream's input size tells which backbone the model was trained on
            gru = next((v for k, v in state.items() if k in ("gru.weight_ih_l0", "video.gru.weight_ih_l0")), None)
            feat_dim = gru.shape[1] if gru is not None and kind not in ("pose", "pose3d") else sc.FEAT_DIM
            backbone = ckpt.get("backbone") or next(b for b, d in sc.BACKBONES.items() if d == feat_dim)
            classes = ckpt.get("classes", sc.BASE_CLASSES)   # the shots this model was trained on
            model = sc.build_model(kind, feat_dim=feat_dim, n_classes=len(classes))
            model.load_state_dict(state)
            model.to(self.device).eval()
            self.models[kind] = {"model": model, "T": float(ckpt.get("temperature", 1.0)),
                                 "classes": classes, "backbone": backbone,
                                 "feat_dim": feat_dim, "crop": ckpt.get("crop") == "pose", "meta": {
                                     k: ckpt.get(k) for k in ("seed", "val_macro_f1", "pose_model", "backbone", "crop")}}
        entry = self.models[kind]
        if kind not in ("pose", "pose3d") and entry["backbone"] not in self.backbones:
            ft = settings.model_dir / sc.FT_FILE if entry["backbone"].endswith(sc.FT_SUFFIX) else None
            net, last = sc.build_backbone(entry["backbone"], ft_weights=ft)
            self.backbones[entry["backbone"]] = (net.to(self.device), last)

    def _make_pose(self):
        import mediapipe as mp  # noqa: F401
        from mediapipe.tasks import python as mpt
        from mediapipe.tasks.python import vision

        name = settings.video_pose_model
        path = settings.model_dir / f"pose_landmarker_{name}.task"
        if not path.exists():
            urllib.request.urlretrieve(
                f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{name}/float16/"
                f"latest/pose_landmarker_{name}.task", path)
        opts = vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=str(path)),
                                            running_mode=vision.RunningMode.IMAGE, num_poses=3)
        return vision.PoseLandmarker.create_from_options(opts)

    # ------------------------------------------------------------ pose
    def _detect_all(self, frames):
        """Up to three people per frame, each as a (33, 3) pixel array. Their 3D world landmarks (metres) are
        kept in self._world, in the same order, for the 3D view."""
        import mediapipe as mp

        h, w = frames[0].shape[:2]
        found, self._world = [], []
        for f in frames:
            r = self.pose.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(f)))
            found.append([sc.landmarks_to_array(p, w, h) for p in (r.pose_landmarks or [])])
            self._world.append([np.array([[q.x, q.y, q.z] for q in p]) for p in (r.pose_world_landmarks or [])])
        return found, w, h

    def _batter_world(self, found, lm):
        """3D landmarks of the person picked as the batter in each frame (None where no batter)."""
        out = []
        for t, people in enumerate(found):
            k = next((i for i, p in enumerate(people) if lm[t, :, 2].max() > 0 and np.array_equal(p, lm[t])), None)
            out.append(None if k is None or k >= len(self._world[t]) else self._world[t][k])
        return out

    def three_d(self, found, lm) -> dict:
        """Per frame: world landmarks (rounded) and the eight 3D joint angles."""
        from .pose import angles_3d
        world = self._batter_world(found, lm)
        return {"world_seq": [None if w3 is None else np.round(w3, 3).tolist() for w3 in world],
                "angles_3d_seq": [None if w3 is None else angles_3d(w3, lm[t, :, 2]) for t, w3 in enumerate(world)]}

    def _landmarks(self, frames):
        """The batter's landmarks in every frame (zeros where the batter was not found)."""
        found, w, h = self._detect_all(frames)
        return follow_batter(found, w, h), w, h

    @staticmethod
    def angle_sequence(lm: np.ndarray) -> list[dict]:
        """Per-frame joint angles in degrees (None where not clearly visible), in the order of dtw.JOINTS."""
        seq = []
        for f in lm:
            feat = sc.pose_features(f)
            seq.append({k: (round(float(feat[i] * 180), 1) if feat[-1] > 0 and feat[i] > 0 else None)
                        for i, k in enumerate(JOINTS)})
        return seq

    # ------------------------------------------------------------ main entry points
    def analyse(self, path: Path, kind: str, out_dir: Path) -> dict:
        with self.lock:
            if kind == MOVEMENT:
                if self.pose is None:
                    self.pose = self._make_pose()
                return self._movement(path, out_dir)
            self._load(kind)
            return self._analyse(path, kind, out_dir)

    def _movement(self, path, out_dir):
        """Pose-only analysis of a clip: skeleton on every frame, joint angles over time, the frame where the
        body moves most, and each joint's range. No shot label, so no trained model is needed."""
        timing = {}
        t0 = time.perf_counter()
        frames = sc.sample_frames(path)
        timing["read_frames_ms"] = _ms(t0)
        t1 = time.perf_counter()
        found, w, h = self._detect_all(frames)
        lm = follow_batter(found, w, h)
        q = quality.assess(frames, [quality.body_stats(f, w, h) for f in lm], frames=len(frames),
                           people=max((len(c) for c in found), default=0))
        d3 = self.three_d(found, lm)
        lm, filled = smooth_landmarks(lm, w, h)
        timing["pose_ms"] = _ms(t1)

        t2 = time.perf_counter()
        seq = self.angle_sequence(lm)
        vis = lm[:, :, 2] >= sc.MIN_VIS
        # Movement per frame: how far the limbs moved relative to the batter's own hips, in shoulder widths.
        # Measuring in body coordinates ignores camera pans and zooms; a sudden change of body size is a camera
        # cut (common in broadcast clips), so that step counts as no movement instead of a huge jump.
        def body(t):
            if not (vis[t, 11] and vis[t, 12] and (vis[t, 23] or vis[t, 24])):
                return None
            hips = [i for i in (23, 24) if vis[t, i]]
            sw = float(np.linalg.norm(lm[t, 11, :2] - lm[t, 12, :2])) + 1e-6
            return lm[t, :, :2] - lm[t, hips, :2].mean(0), sw
        motion, cuts = np.zeros(len(frames)), []
        prev = body(0)
        for t in range(1, len(frames)):
            cur = body(t)
            if cur and prev:
                ratio = cur[1] / prev[1]
                if not 0.7 < ratio < 1.43:
                    cuts.append(t)
                else:
                    pts = [i for i in MOTION_POINTS if vis[t, i] and vis[t - 1, i]]
                    if pts:
                        sw = (cur[1] + prev[1]) / 2
                        motion[t] = np.median([np.linalg.norm(cur[0][i] - prev[0][i]) for i in pts]) / sw
            prev = cur   # only neighbouring frames are compared
        share = motion / motion.sum() if motion.sum() > 0 else np.full(len(frames), 1 / len(frames))
        tracked = [t for t in range(len(frames)) if sum(v is not None for v in seq[t].values()) >= 4]
        key = int(np.argmax(motion)) if motion.sum() > 0 else (tracked[len(tracked) // 2] if tracked else 0)
        ranges = {}
        for j in JOINTS:
            vals = [(seq[t][j], t) for t in range(len(seq)) if seq[t][j] is not None]
            if vals:
                lo, hi = min(vals), max(vals)
                ranges[j] = {"min": lo[0], "max": hi[0], "range": round(hi[0] - lo[0], 1),
                             "min_frame": lo[1], "max_frame": hi[1], "frames": len(vals)}
        timing["measure_ms"] = _ms(t2)

        t3 = time.perf_counter()
        out_dir.mkdir(parents=True, exist_ok=True)
        for t, f in enumerate(frames):
            _save(out_dir / f"frame_{t:02d}.jpg", f)
            _save(out_dir / f"skel_{t:02d}.jpg", _skeleton(f, lm[t]))
        (out_dir / "thumb.jpg").write_bytes((out_dir / f"skel_{key:02d}.jpg").read_bytes())
        timing["save_ms"] = _ms(t3)

        return {
            "shot": None, "confidence": None, "uncertain": False, "top3": None,
            "attention": [round(float(x), 4) for x in share],
            "motion": [round(float(x), 3) for x in motion],
            "key_frame": key,
            "has_heatmaps": False,
            "overlay": "skeleton",
            "angles_seq": seq,
            "joint_ranges": ranges,
            "tracked_frames": len(tracked),
            "camera_cuts": cuts,
            "points_filled": filled,
            "quality": q,
            **d3,
            "landmarks": _norm_landmarks(lm, w, h),
            "visible_per_frame": vis.sum(1).tolist(),
            "frames": len(frames),
            "frame_size": [w, h],
            "model_label": LABELS[MOVEMENT],
            "timing": timing,
        }

    def reference_angles(self, path: Path, out_dir: Path) -> dict:
        """For reference clips: frames and the angle sequence only (no classification)."""
        with self.lock:
            if self.pose is None:
                self.pose = self._make_pose()
            frames = sc.sample_frames(path)
            lm, w, h = self._landmarks(frames)
            lm, _ = smooth_landmarks(lm, w, h)
            out_dir.mkdir(parents=True, exist_ok=True)
            for t, f in enumerate(frames):
                _save(out_dir / f"frame_{t:02d}.jpg", f)
            return {"angles": self.angle_sequence(lm), "landmarks": _norm_landmarks(lm, w, h)}

    def _analyse(self, path, kind, out_dir):
        timing = {}
        t0 = time.perf_counter()
        frames = sc.sample_frames(path)
        timing["read_frames_ms"] = _ms(t0)

        t1 = time.perf_counter()
        found, w, h = self._detect_all(frames)
        first = np.stack([c[0] if c else sc.landmarks_to_array(None, w, h) for c in found])
        lm = follow_batter(found, w, h)
        d3 = self.three_d(found, lm)
        # the model gets the same input as in training (first person reported); the player sees the batter's track
        if sc.uses_3d(kind):   # 3D models: world landmarks of the same first-reported person, as in training
            world0 = [w3[0] if w3 else np.zeros((33, 3)) for w3 in self._world]
            feats = [sc.pose_features_3d(w3, f[:, 2]) for w3, f in zip(world0, first)]
        else:
            feats = [sc.pose_features(f) for f in first]
        pose = torch.from_numpy(sc.fill_missing(np.stack(feats))).unsqueeze(0)
        timing["pose_ms"] = _ms(t1)

        entry = self.models[kind]
        model, T, classes = entry["model"], entry["T"], entry["classes"]
        acts, grads, cams = {}, {}, None
        # models trained on batter crops get the same crop, from the same first-reported person as in training
        box = sc.batter_box(first, w, h) if entry["crop"] else None

        t2 = time.perf_counter()
        with torch.enable_grad():
            if kind in ("pose", "pose3d"):
                feats = torch.zeros(1, sc.NUM_FRAMES, entry["feat_dim"])
            else:
                backbone, last_block = self.backbones[entry["backbone"]]

                def keep(_m, _i, o):  # store the activations and, on backward, their gradients
                    acts["a"] = o
                    o.register_hook(lambda g: grads.__setitem__("g", g))

                h1 = last_block.register_forward_hook(keep)
                feats = backbone(sc.to_tensor(sc.crop_frames(frames, box)).to(self.device)).unsqueeze(0)
                h1.remove()
            logits, att = model(feats.to(self.device), pose.to(self.device))
            probs = torch.softmax(logits.detach() / T, 1)[0].cpu().numpy()
            top = int(probs.argmax())
            if kind not in ("pose", "pose3d"):
                # Grad-CAM (Selvaraju et al.): gradients of the top class score on the last conv block
                model.zero_grad()
                backbone.zero_grad()
                logits[0, top].backward()
                a, g = acts["a"].detach(), grads["g"].detach()          # (15, C, 7, 7)
                cam = torch.relu((g.mean((2, 3), keepdim=True) * a).sum(1))
                cams = (cam / (cam.max() + 1e-8)).cpu().numpy()        # one scale for the whole clip
        timing["model_ms"] = _ms(t2)

        t3 = time.perf_counter()
        out_dir.mkdir(parents=True, exist_ok=True)
        attention = att.detach()[0].cpu().numpy()
        key = int(attention.argmax())
        for t, f in enumerate(frames):
            _save(out_dir / f"frame_{t:02d}.jpg", f)
            if cams is not None:
                _save(out_dir / f"heat_{t:02d}.jpg", _overlay(f, cams[t], box=box))
        thumb = out_dir / (f"heat_{key:02d}.jpg" if cams is not None else f"frame_{key:02d}.jpg")
        (out_dir / "thumb.jpg").write_bytes(thumb.read_bytes())
        timing["save_ms"] = _ms(t3)

        order = np.argsort(-probs)[:3]
        visible = (lm[:, :, 2] >= sc.MIN_VIS).sum(1)
        shown, _ = smooth_landmarks(lm, w, h)   # display and measurements only; the model saw raw landmarks
        q = quality.assess(frames, [quality.body_stats(f, w, h) for f in lm], frames=len(frames),
                           people=max((len(c) for c in found), default=0))
        return {
            "shot": classes[top],
            "confidence": round(float(probs[top]), 4),
            "uncertain": bool(probs[top] < settings.uncertain_threshold),
            "top3": [{"shot": classes[i], "prob": round(float(probs[i]), 4)} for i in order],
            "family": sc.family_probs(probs, classes)[0],
            "attention": [round(float(x), 4) for x in attention],
            "key_frame": key,
            "has_heatmaps": cams is not None,
            "quality": q,
            **d3,
            "angles_seq": self.angle_sequence(shown),
            "landmarks": _norm_landmarks(shown, w, h),
            "visible_per_frame": visible.tolist(),
            "frames": len(frames),
            "frame_size": [w, h],
            "temperature": round(T, 3),
            "model_label": LABELS[kind],
            "timing": timing,
        }


# ---------------------------------------------------------------- long videos: find and cut each shot
LONG_VIDEO_S = 5.0      # longer than this: treat as a practice video with several shots
SHOT_BEFORE_S, SHOT_AFTER_S = 1.1, 0.7   # window kept around each movement peak (backlift to follow-through)
MIN_GAP_S = 2.2         # two shots are at least this far apart


def video_info(path) -> tuple[int, float, int, int]:
    cap = cv2.VideoCapture(str(path))
    n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return n, fps, w, h


def find_shots(service, path) -> list[dict]:
    """Movement peaks in a long practice video. The video is scanned at about 8 frames a second, the batter is
    followed as in a single clip, and movement is measured relative to the body. Each clear peak (well above
    the video's usual movement) is one shot; peaks closer than MIN_GAP_S are the same shot."""
    n, fps, w, h = video_info(path)
    step = max(1, round(fps / 8))
    cap, frames, times = cv2.VideoCapture(str(path)), [], []
    for i in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ok, f = cap.read()
        if not ok:
            break
        if f.shape[1] > 640:   # pose on a smaller copy is quicker and accurate enough to find shots
            f = cv2.resize(f, (640, int(f.shape[0] * 640 / f.shape[1])), interpolation=cv2.INTER_AREA)
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB)); times.append(i / fps)
    cap.release()
    if len(frames) < 8:
        return []
    with service.lock:
        if service.pose is None:
            service.pose = service._make_pose()
        found, fw, fh = service._detect_all(frames)
    lm = follow_batter(found, fw, fh)
    lm, _ = smooth_landmarks(lm, fw, fh)
    seen = lm[:, :, 2] >= sc.MIN_VIS
    motion = np.zeros(len(frames))
    for t in range(1, len(frames)):
        ok = [i for i in MOTION_POINTS if seen[t, i] and seen[t - 1, i]]
        if not ok or not (seen[t, 11] and seen[t, 12] and seen[t - 1, 11] and seen[t - 1, 12]):
            continue
        sw = (np.linalg.norm(lm[t, 11, :2] - lm[t, 12, :2]) + np.linalg.norm(lm[t - 1, 11, :2] - lm[t - 1, 12, :2])) / 2
        hips = lambda k: lm[k, [23, 24], :2].mean(0)
        motion[t] = np.median([np.linalg.norm((lm[t, i, :2] - hips(t)) - (lm[t - 1, i, :2] - hips(t - 1))) for i in ok]) / (sw + 1e-6)
    motion = np.convolve(motion, np.ones(3) / 3, mode="same")
    if motion.max() <= 0:
        return []
    level = max(0.12, 0.4 * motion.max(), 3 * np.median(motion))
    peaks = [t for t in range(1, len(motion) - 1) if motion[t] >= level and motion[t] >= motion[t - 1] and motion[t] >= motion[t + 1]]
    shots = []
    for t in sorted(peaks, key=lambda t: -motion[t]):   # strongest first, then drop peaks too close to one already kept
        if all(abs(times[t] - s["peak_s"]) >= MIN_GAP_S for s in shots):
            shots.append({"peak_s": times[t], "strength": float(motion[t])})
    duration = n / fps
    for s in shots:
        s["start_s"] = max(0.0, s["peak_s"] - SHOT_BEFORE_S)
        s["end_s"] = min(duration, s["peak_s"] + SHOT_AFTER_S)
    return sorted(shots, key=lambda s: s["start_s"])[:12]


def cut_clip(path, start_s: float, end_s: float, out_path) -> None:
    n, fps, w, h = video_info(path)
    cap = cv2.VideoCapture(str(path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * fps))
    out = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for _ in range(int((end_s - start_s) * fps)):
        ok, f = cap.read()
        if not ok:
            break
        out.write(f)
    out.release(); cap.release()


def overlay_kind(summary: dict) -> str | None:
    """Which drawn-over frames a video result has: 'skel' (body skeleton), 'heat' (Grad-CAM) or None."""
    if summary.get("overlay") == "skeleton":
        return "skel"
    return "heat" if summary.get("has_heatmaps") else None


def _ms(t):
    return round((time.perf_counter() - t) * 1000, 1)


def _save(path, rgb):
    h, w = rgb.shape[:2]
    img = cv2.resize(rgb, (FRAME_W, int(h * FRAME_W / w)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])


def _overlay(rgb, cam, alpha=0.45, box=None):
    if box is not None:   # the model saw only the batter crop: draw its heatmap inside that box
        x1, y1, x2, y2 = box
        out = rgb.copy()
        out[y1:y2, x1:x2] = _overlay(np.ascontiguousarray(rgb[y1:y2, x1:x2]), cam, alpha)
        return out
    heat = cv2.resize((cam * 255).astype(np.uint8), (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_CUBIC)
    heat = cv2.cvtColor(cv2.applyColorMap(heat, cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    return cv2.addWeighted(rgb, 1 - alpha, heat, alpha, 0)


def _skeleton(rgb, pts):
    """Frame with the tracked body drawn on it (points below the visibility threshold are left out)."""
    from .pose import EDGES
    img = rgb.copy()
    th = max(2, rgb.shape[1] // 320)
    ok = lambda i: pts[i, 2] >= sc.MIN_VIS
    for a, b in EDGES:
        if ok(a) and ok(b):
            cv2.line(img, tuple(int(v) for v in pts[a, :2]), tuple(int(v) for v in pts[b, :2]), (243, 233, 210), th + 2, cv2.LINE_AA)
            cv2.line(img, tuple(int(v) for v in pts[a, :2]), tuple(int(v) for v in pts[b, :2]), (31, 157, 85), th, cv2.LINE_AA)
    for i in range(11, 33):
        if ok(i):
            cv2.circle(img, tuple(int(v) for v in pts[i, :2]), th + 2, (200, 16, 46), -1, cv2.LINE_AA)
            cv2.circle(img, tuple(int(v) for v in pts[i, :2]), th + 2, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def _centre_size(p: np.ndarray):
    seen = p[:, 2] >= sc.MIN_VIS
    if seen.sum() < 6:
        return None
    xy = p[seen, :2]
    return xy.mean(0), float(np.ptp(xy[:, 1])) + 1e-6


def follow_batter(found: list[list[np.ndarray]], w: int, h: int, max_skip: int = 2, min_run: int = 2) -> np.ndarray:
    """Pick the batter among everyone detected, frame by frame.

    People are linked into tracks: a person joins a track when their body centre is close to where that track
    was last seen (within 15% of the frame size, a little more for each missed frame). The batter stays at the
    crease for the whole stroke, while a bowler or fielder only passes through. Frames that belong to no batter
    track are left empty rather than filled with someone else's body."""
    size = float(max(w, h))
    tracks = []   # each: {"frames": {t: person}, "last": (t, centre), "heights": [...]}
    for t, people in enumerate(found):
        cands = [(p, cs) for p in people if (cs := _centre_size(p))]
        cands.sort(key=lambda x: -x[1][1])          # larger people first
        used = set()
        for p, (c, ht) in cands:
            best, best_d = None, None
            for k, tr in enumerate(tracks):
                lt, lc = tr["last"]
                gap = t - lt
                if k in used or gap < 1 or gap > max_skip + 1:
                    continue
                d = np.linalg.norm(c - lc) / size
                if d < 0.15 + 0.05 * (gap - 1) and (best_d is None or d < best_d):
                    best, best_d = k, d
            if best is None:
                tracks.append({"frames": {t: p}, "last": (t, c), "heights": [ht]})
                used.add(len(tracks) - 1)
            else:
                tr = tracks[best]
                tr["frames"][t], tr["last"] = p, (t, c)
                tr["heights"].append(ht)
                used.add(best)
    # Which tracks are the batter? Camera operators frame the batter: horizontally near the middle and not at
    # the bottom edge, where whoever is closest to the camera appears (the bowler running in from behind the
    # camera, an umpire, a fielder). The best batter-like track, by length then size, is the batter. A camera cut
    # moves the batter on screen and starts a new track, so other batter-like tracks of at least min_run frames
    # that do not overlap it in time are the batter again after the cut.
    def centre(tr):
        return np.mean([_centre_size(p)[0] for p in tr["frames"].values()], axis=0) / [w, h]
    def batter_like(tr):
        x, y = centre(tr)
        return 0.15 <= x <= 0.85 and y <= 0.75
    ranked = sorted(tracks, key=lambda tr: (batter_like(tr), len(tr["frames"]), np.mean(tr["heights"])), reverse=True)
    out = np.stack([sc.landmarks_to_array(None, w, h)] * len(found))
    taken = set()
    for k, tr in enumerate(ranked):
        frames = set(tr["frames"])
        if (k == 0 or (batter_like(tr) and len(frames) >= min_run)) and not frames & taken:
            for t, p in tr["frames"].items():
                out[t] = p
            taken |= frames
    return out


def smooth_landmarks(lm: np.ndarray, w: int, h: int, max_gap: int = 2) -> tuple[np.ndarray, int]:
    """Steadier landmarks over the 15 frames, for measurements shown to the player.

    1. A point lost for up to max_gap frames between two frames where it was seen is filled by linear
       interpolation (a short motion-blur dropout, not a real disappearance).
    2. Each seen point is averaged with its neighbours (weights 1-2-1). A neighbour is skipped when it is not
       seen or has jumped more than 12% of the frame size, so camera cuts and tracking glitches are not blurred.
    Returns the new array and how many points were filled in."""
    out = lm.copy()
    T = len(lm)
    seen = lm[:, :, 2] >= sc.MIN_VIS
    filled = 0
    for i in range(lm.shape[1]):
        idx = np.flatnonzero(seen[:, i])
        for a, b in zip(idx[:-1], idx[1:]):
            close = np.linalg.norm(lm[b, i, :2] - lm[a, i, :2]) < 0.15 * max(w, h)
            if 1 < b - a <= max_gap + 1 and close:
                for t in range(a + 1, b):
                    f = (t - a) / (b - a)
                    out[t, i, :2] = (1 - f) * lm[a, i, :2] + f * lm[b, i, :2]
                    out[t, i, 2] = sc.MIN_VIS          # counts as seen, just at the threshold
                    filled += 1
    seen = out[:, :, 2] >= sc.MIN_VIS
    jump = 0.12 * max(w, h)
    smooth = out.copy()
    for t in range(T):
        for i in np.flatnonzero(seen[t]):
            acc, wsum = 2 * out[t, i, :2], 2.0
            for n in (t - 1, t + 1):
                if 0 <= n < T and seen[n, i] and np.linalg.norm(out[n, i, :2] - out[t, i, :2]) < jump:
                    acc, wsum = acc + out[n, i, :2], wsum + 1
            smooth[t, i, :2] = acc / wsum
    return smooth, filled


def _norm_landmarks(lm, w, h):
    """Per frame: 33 x [x/w, y/h, visibility], rounded, for drawing in the browser."""
    return [[[round(float(p[0] / w), 4), round(float(p[1] / h), 4), round(float(p[2]), 2)] for p in f] for f in lm]


video_service = VideoService()
