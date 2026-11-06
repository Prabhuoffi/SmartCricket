"""Shared code for training (Colab) and inference (the web app).

Keeping frame sampling, pose features and model definitions in one file guarantees that the
app prepares a clip exactly the way the models saw clips during training.
"""
import math

import cv2
import numpy as np
import torch
import torch.nn as nn

BASE_CLASSES = ["Cover Drive", "Defensive", "Down The Wicket", "Flick", "Hook", "Late Cut", "Lofted Legside",
                "Lofted Offside", "Pull", "Reverse Sweep", "Scoop", "Square Cut", "Straight Drive", "Sweep", "Upper Cut"]
# Shots not in CricShot10k. They are trained only once enough clips of them are added (see the notebook's
# extra_shots folder); a model's checkpoint lists the classes it was actually trained on.
NEW_SHOTS = ["Slog Sweep", "Paddle Sweep", "Switch Hit", "Leg Glance", "Leave"]
CLASSES = BASE_CLASSES + NEW_SHOTS
# Cricket shot families: shots of the same family share the batting movement, so the family is a coarser,
# more reliable label shown next to the exact shot (10 families for the 15 CricShot10k shots).
# Shots not listed are their own family.
FAMILIES = {"Cover Drive": "Drive", "Straight Drive": "Drive", "Slog Sweep": "Sweep", "Paddle Sweep": "Sweep",
            "Square Cut": "Cut", "Late Cut": "Cut", "Upper Cut": "Cut",
            "Lofted Legside": "Lofted", "Lofted Offside": "Lofted",
            "Pull": "Pull / Hook", "Hook": "Pull / Hook"}


def family_of(shot: str) -> str:
    return FAMILIES.get(shot, shot)


def family_probs(probs, classes=CLASSES) -> list[dict]:
    """Sum the class probabilities within each family, highest first."""
    totals: dict[str, float] = {}
    for c, p in zip(classes, probs):
        totals[family_of(c)] = totals.get(family_of(c), 0.0) + float(p)
    return [{"family": f, "prob": round(p, 4)} for f, p in sorted(totals.items(), key=lambda kv: -kv[1])]


NUM_FRAMES = 15
SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# Frozen image backbones -> pooled feature size. Each checkpoint records which one it was trained with.
BACKBONES = {"efficientnet_v2_s/IMAGENET1K_V1": 1280,          # first models (E1 to E9, report v1)
             "regnet_y_16gf/IMAGENET1K_SWAG_LINEAR_V1": 3024}  # stronger: pretrained on 3.6B images, made for frozen use
BACKBONE = "regnet_y_16gf/IMAGENET1K_SWAG_LINEAR_V1"            # used for new training runs
LEGACY_BACKBONE = "efficientnet_v2_s/IMAGENET1K_V1"             # checkpoints without a 'backbone' entry
FEAT_DIM = BACKBONES[BACKBONE]
POSE_DIM = 43            # 8 angles + 17 landmarks (x, y) + 1 valid flag
POSE3D_DIM = 60          # 8 angles measured in 3D + 17 world landmarks (x, y, z) + 1 valid flag
MIN_VIS = 0.5


# ---------------------------------------------------------------- frames

def sample_frames(path: str, n: int = NUM_FRAMES) -> list[np.ndarray]:
    """n evenly spaced RGB frames at full resolution. Short clips repeat frames (FR-7)."""
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    cap.release()
    if not frames:
        raise ValueError(f"Video has no readable frames: {path}")
    idx = np.linspace(0, len(frames) - 1, n).round().astype(int)
    return [cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB) for i in idx]


def to_tensor(frames: list[np.ndarray], flip: bool = False) -> torch.Tensor:
    """(n, 3, 224, 224) float tensor normalised with ImageNet statistics."""
    out = []
    for f in frames:
        f = cv2.resize(f, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
        if flip:
            f = f[:, ::-1]
        out.append((f.astype(np.float32) / 255.0 - MEAN) / STD)
    return torch.from_numpy(np.stack(out)).permute(0, 3, 1, 2).contiguous()


def batter_box(lm: np.ndarray, w: int, h: int, margin: float = 0.3, min_frames: int = 3):
    """One square box around the batter for the whole clip, from the pose landmarks (n, 33, 3) in pixels.

    Uses frames where at least 8 points are clearly visible; the 10th/90th percentiles of the body edges ignore a
    stray detection, and the margin leaves room for the bat. None (use the full frame) when the body is not found
    in enough frames. The box is fixed, so the movement between frames is kept."""
    boxes = []
    for f in lm:
        v = f[:, 2] >= MIN_VIS
        if v.sum() >= 8:
            boxes.append((f[v, 0].min(), f[v, 1].min(), f[v, 0].max(), f[v, 1].max()))
    if len(boxes) < min_frames:
        return None
    b = np.array(boxes)
    x1, y1 = np.percentile(b[:, 0], 10), np.percentile(b[:, 1], 10)
    x2, y2 = np.percentile(b[:, 2], 90), np.percentile(b[:, 3], 90)
    side = max(x2 - x1, y2 - y1) * (1 + 2 * margin)
    side = min(max(side, 0.25 * min(w, h)), min(w, h))   # not tiny, and never larger than the frame
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    x0 = int(np.clip(cx - side / 2, 0, w - side)); y0 = int(np.clip(cy - side / 2, 0, h - side))
    return x0, y0, x0 + int(side), y0 + int(side)


def crop_frames(frames: list[np.ndarray], box) -> list[np.ndarray]:
    if box is None:
        return frames
    x1, y1, x2, y2 = box
    return [f[y1:y2, x1:x2] for f in frames]


# ---------------------------------------------------------------- pose features

# MediaPipe indices. Pairs are (left, right) so that a horizontal flip can swap them.
POSE_POINTS = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32]
LR_SWAP = {11: 12, 12: 11, 13: 14, 14: 13, 15: 16, 16: 15, 23: 24, 24: 23, 25: 26, 26: 25, 27: 28, 28: 27,
           29: 30, 30: 29, 31: 32, 32: 31}
ANGLE_TRIPLES = [(11, 13, 15), (12, 14, 16), (13, 11, 23), (14, 12, 24),   # elbows, shoulders
                 (11, 23, 25), (12, 24, 26), (23, 25, 27), (24, 26, 28)]   # hips, knees


def _angle(a, b, c):
    ba, bc = a - b, c - b
    cos = ba @ bc / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def landmarks_to_array(lms, w: int, h: int) -> np.ndarray:
    """MediaPipe landmark list -> (33, 3) array of pixel x, pixel y, visibility. None -> all zeros."""
    if lms is None:
        return np.zeros((33, 3), np.float32)
    return np.array([[p.x * w, p.y * h, p.visibility] for p in lms], np.float32)


def pose_features_3d(world: np.ndarray, vis: np.ndarray) -> np.ndarray:
    """(33, 3) world landmarks in metres (hip-centred, from MediaPipe) and (33,) image visibilities ->
    POSE3D_DIM vector. Angles are measured in 3D, so they do not change with the camera's direction.
    Coordinates are centred on the hip midpoint and divided by the 3D shoulder width. Hidden joints stay 0;
    the last value is 1 if the frame is usable."""
    seen = vis >= MIN_VIS
    feat = np.zeros(POSE3D_DIM, np.float32)
    if not (seen[11] and seen[12] and (seen[23] or seen[24])):
        return feat
    hips = [i for i in (23, 24) if seen[i]]
    centre = world[hips].mean(0)
    scale = np.linalg.norm(world[11] - world[12]) + 1e-6
    for k, (a, b, c) in enumerate(ANGLE_TRIPLES):
        if seen[a] and seen[b] and seen[c]:
            ba, bc = world[a] - world[b], world[c] - world[b]
            cos = ba @ bc / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
            feat[k] = np.degrees(np.arccos(np.clip(cos, -1, 1))) / 180.0
    for k, i in enumerate(POSE_POINTS):
        if seen[i]:
            feat[8 + 3 * k: 11 + 3 * k] = np.clip((world[i] - centre) / scale, -5, 5)
    feat[-1] = 1.0
    return feat


def mirror_world(world: np.ndarray, vis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """3D landmarks and visibilities of the horizontally flipped clip: negate x and swap left/right."""
    w2 = world.copy(); w2[:, 0] = -w2[:, 0]
    out_w, out_v = w2.copy(), vis.copy()
    for a, b in LR_SWAP.items():
        out_w[a], out_v[a] = w2[b], vis[b]
    return out_w, out_v


def view_ratio(lm: np.ndarray) -> float | None:
    """Camera view of a clip from its 2D landmarks (frames, 33, 3): median shoulder width divided by torso
    length. Small = side-on, large = front-on (same rule as the app's quality check)."""
    r = []
    for f in lm:
        seen = f[:, 2] >= MIN_VIS
        if seen[11] and seen[12] and (seen[23] or seen[24]):
            hips = [i for i in (23, 24) if seen[i]]
            torso = np.linalg.norm(f[[11, 12], :2].mean(0) - f[hips, :2].mean(0)) + 1e-6
            r.append(abs(f[11, 0] - f[12, 0]) / torso)
    return float(np.median(r)) if r else None


def view_bucket(ratio: float | None) -> str:
    return "unknown" if ratio is None else "side-on" if ratio < 0.35 else "angled" if ratio < 0.65 else "front-on"


def mirror_landmarks(arr: np.ndarray, w: int) -> np.ndarray:
    """Landmarks of the horizontally flipped image: mirror x and swap left/right points."""
    out = arr.copy()
    out[:, 0] = w - arr[:, 0]
    swapped = out.copy()
    for a, b in LR_SWAP.items():
        swapped[a] = out[b]
    return swapped


def pose_features(arr: np.ndarray) -> np.ndarray:
    """(33, 3) landmarks of one frame -> POSE_DIM vector.

    Angles are scaled to 0..1. Coordinates are centred on the hip midpoint and divided by the
    shoulder width, so the vector does not depend on where the batter stands or how large they appear.
    Joints below the visibility threshold are left at 0; the last value is 1 if the frame is usable.
    """
    vis = arr[:, 2] >= MIN_VIS
    feat = np.zeros(POSE_DIM, np.float32)
    if not (vis[11] and vis[12] and (vis[23] or vis[24])):
        return feat
    xy = arr[:, :2]
    hips = [i for i in (23, 24) if vis[i]]
    centre = xy[hips].mean(0)
    scale = np.linalg.norm(xy[11] - xy[12]) + 1e-6
    for k, (a, b, c) in enumerate(ANGLE_TRIPLES):
        if vis[a] and vis[b] and vis[c]:
            feat[k] = _angle(xy[a], xy[b], xy[c]) / 180.0
    for k, i in enumerate(POSE_POINTS):
        if vis[i]:
            feat[8 + 2 * k: 10 + 2 * k] = np.clip((xy[i] - centre) / scale, -5, 5)
    feat[-1] = 1.0
    return feat


def fill_missing(seq: np.ndarray) -> np.ndarray:
    """Carry the last usable frame forward over frames where no pose was found."""
    out = seq.copy()
    last = None
    for t in range(len(out)):
        if out[t, -1] > 0:
            last = out[t]
        elif last is not None:
            out[t, :-1] = last[:-1]
    return out


# ---------------------------------------------------------------- models

class Attention(nn.Module):
    """Additive attention over GRU outputs; the weights are the key-frame timeline."""

    def __init__(self, hidden: int):
        super().__init__()
        self.score = nn.Sequential(nn.Linear(hidden, 64), nn.Tanh(), nn.Linear(64, 1))

    def forward(self, h):                      # h: (B, T, H)
        a = torch.softmax(self.score(h).squeeze(-1), dim=1)
        return (a.unsqueeze(-1) * h).sum(1), a


class VideoHead(nn.Module):
    """E1: per-frame EfficientNetV2-S features -> GRU(128) -> attention -> classes."""

    def __init__(self, n_classes=len(BASE_CLASSES), hidden=128, in_dim=FEAT_DIM, dropout=0.3):
        super().__init__()
        self.drop_in = nn.Dropout(0.2)
        self.gru = nn.GRU(in_dim, hidden, batch_first=True)
        self.att = Attention(hidden)
        self.out_dim = hidden
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden, n_classes))

    def encode(self, x):
        h, _ = self.gru(self.drop_in(x))
        return self.att(h)

    def forward(self, x, pose=None):
        c, a = self.encode(x)
        return self.head(c), a


class PoseNet(nn.Module):
    """E2: per-frame pose features -> GRU(64) -> attention -> classes."""

    def __init__(self, n_classes=len(BASE_CLASSES), hidden=64, in_dim=POSE_DIM, dropout=0.3):
        super().__init__()
        self.gru = nn.GRU(in_dim, hidden, batch_first=True)
        self.att = Attention(hidden)
        self.out_dim = hidden
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden, n_classes))

    def encode(self, p):
        h, _ = self.gru(p)
        return self.att(h)

    def forward(self, x, pose=None):
        c, a = self.encode(pose if pose is not None else x)
        return self.head(c), a


class FusionNet(nn.Module):
    """E3: late fusion of the video and pose summaries -> MLP (192 -> 128 -> classes)."""

    def __init__(self, n_classes=len(BASE_CLASSES), pose_dim=POSE_DIM, feat_dim=FEAT_DIM):
        super().__init__()
        self.video = VideoHead(n_classes, in_dim=feat_dim)
        self.pose = PoseNet(n_classes, in_dim=pose_dim)
        self.head = nn.Sequential(nn.Linear(self.video.out_dim + self.pose.out_dim, 128), nn.ReLU(),
                                  nn.Dropout(0.3), nn.Linear(128, n_classes))

    def forward(self, x, pose):
        cv, av = self.video.encode(x)
        cp, _ = self.pose.encode(pose)
        return self.head(torch.cat([cv, cp], 1)), av


def build_model(kind: str, feat_dim: int = FEAT_DIM, n_classes: int = len(BASE_CLASSES)) -> nn.Module:
    """video, pose and fusion (E1 to E3); pose3d and fusion3d use 3D pose features (E9).
    feat_dim is the backbone's feature size (see BACKBONES); n_classes the number of shots trained."""
    n = n_classes
    return {"video": lambda: VideoHead(n, in_dim=feat_dim), "pose": lambda: PoseNet(n),
            "fusion": lambda: FusionNet(n, feat_dim=feat_dim),
            "pose3d": lambda: PoseNet(n, in_dim=POSE3D_DIM),
            "fusion3d": lambda: FusionNet(n, pose_dim=POSE3D_DIM, feat_dim=feat_dim)}[kind]()


def uses_3d(kind: str) -> bool:
    return kind.endswith("3d")


FT_SUFFIX = "+ft"            # backbone name suffix: last blocks fine-tuned on cricket frames (weights in FT_FILE)
FT_FILE = "backbone_ft.pt"


def feat_dim_of(name: str) -> int:
    return BACKBONES[name.split("+")[0]]


def build_backbone(name: str = BACKBONE, ft_weights=None):
    """Backbone without its classifier: image -> feat_dim_of(name)-d vector. Returns (model, last_conv_block).
    A name ending in FT_SUFFIX needs ft_weights (path to FT_FILE), the fine-tuned state dict."""
    import torchvision.models as tvm
    base = name.split("+")[0]
    if name.endswith(FT_SUFFIX):
        net, last = build_backbone(base)
        if ft_weights is None:
            raise FileNotFoundError(f"{name} needs its fine-tuned weights ({FT_FILE})")
        state = torch.load(ft_weights, map_location="cpu")
        net.load_state_dict({k: v.float() for k, v in state.items()})
        return net.eval(), last
    name = base
    if name.startswith("efficientnet_v2_s"):
        net = tvm.efficientnet_v2_s(weights=tvm.EfficientNet_V2_S_Weights.IMAGENET1K_V1)
        net.classifier = nn.Identity()
        last = net.features[-1]
    elif name.startswith("regnet_y_16gf"):
        net = tvm.regnet_y_16gf(weights=tvm.RegNet_Y_16GF_Weights.IMAGENET1K_SWAG_LINEAR_V1)
        net.fc = nn.Identity()
        last = net.trunk_output
    else:
        raise ValueError(f"Unknown backbone: {name}")
    net.eval()
    return net, last


def unfreeze_last_blocks(net: nn.Module, name: str = BACKBONE) -> list:
    """For fine-tuning: freeze the backbone except its last two stages; returns the trainable parameters.
    BatchNorm statistics stay frozen (call net.eval() while training), which is stable with small batches."""
    for q in net.parameters():
        q.requires_grad = False
    if name.startswith("regnet_y_16gf"):
        last = [net.trunk_output.block3, net.trunk_output.block4]
    elif name.startswith("efficientnet_v2_s"):
        last = [net.features[-2], net.features[-1]]
    else:
        raise ValueError(f"Unknown backbone: {name}")
    params = [q for m in last for q in m.parameters()]
    for q in params:
        q.requires_grad = True
    return params


class TemperatureScaler(nn.Module):
    """One learned temperature T > 0; logits / T gives calibrated probabilities (Guo et al., 2017)."""

    def __init__(self):
        super().__init__()
        self.log_t = nn.Parameter(torch.zeros(1))

    def forward(self, logits):
        return logits / self.log_t.exp()

    def fit(self, logits, labels, steps=300):
        opt = torch.optim.LBFGS([self.log_t], lr=0.05, max_iter=steps)
        nll = nn.CrossEntropyLoss()

        def closure():
            opt.zero_grad()
            loss = nll(self(logits), labels)
            loss.backward()
            return loss

        opt.step(closure)
        return float(self.log_t.detach().exp())


# ---------------------------------------------------------------- metrics

def expected_calibration_error(probs: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    conf, pred = probs.max(1), probs.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs((pred[m] == labels[m]).mean() - conf[m].mean())
    return float(ece)


def cosine_warmup(step, total, warmup):
    if step < warmup:
        return (step + 1) / warmup
    return 0.5 * (1 + math.cos(math.pi * (step - warmup) / max(1, total - warmup)))
