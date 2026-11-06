"""Checks the shared training code before it is run on Colab (UT-01, UT-02, UT-04, UT-09, UT-10)."""
import json
import re
from pathlib import Path
from types import SimpleNamespace as P

import cv2
import numpy as np
import pytest
import torch

from training import sc_common as sc

ROOT = Path(__file__).resolve().parents[1]


def make_clip(path, n_frames, w=320, h=180):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))
    for i in range(n_frames):
        f = np.zeros((h, w, 3), np.uint8)
        cv2.putText(f, str(i), (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)
        f[:, :, 2] = i * 8  # frame number also encoded in the red channel
        vw.write(f)
    vw.release()


def test_sample_frames_even(tmp_path):  # UT-01
    make_clip(tmp_path / "a.mp4", 30)
    fr = sc.sample_frames(tmp_path / "a.mp4")
    assert len(fr) == 15 and fr[0].shape == (180, 320, 3)
    reds = [int(f[:, :, 0].mean() / 8 + 0.5) for f in fr]  # RGB order: red is channel 0
    assert reds[0] <= 1 and abs(reds[-1] - 29) <= 1 and reds == sorted(reds)  # mp4 is lossy


def test_sample_frames_short_clip_repeats(tmp_path):  # UT-02
    make_clip(tmp_path / "b.mp4", 8)
    assert len(sc.sample_frames(tmp_path / "b.mp4")) == 15


def test_sample_frames_unreadable(tmp_path):  # UT-03
    (tmp_path / "bad.mp4").write_bytes(b"not a video")
    with pytest.raises(ValueError):
        sc.sample_frames(tmp_path / "bad.mp4")


def test_to_tensor_and_flip():  # UT-04
    f = np.zeros((100, 200, 3), np.uint8)
    f[:, :100] = 255
    x, xf = sc.to_tensor([f] * 15), sc.to_tensor([f] * 15, flip=True)
    assert x.shape == (15, 3, 224, 224)
    assert torch.allclose(x[..., :, :50], xf[..., :, -50:].flip(-1))


def landmarks(seed=0):
    rng = np.random.default_rng(seed)
    arr = np.zeros((33, 3), np.float32)
    arr[:, 0] = rng.uniform(100, 300, 33)
    arr[:, 1] = rng.uniform(50, 400, 33)
    arr[:, 2] = 0.9
    return arr


def test_pose_features_shape_and_range():
    f = sc.pose_features(landmarks())
    assert f.shape == (sc.POSE_DIM,) and f[-1] == 1.0
    assert (f[:8] >= 0).all() and (f[:8] <= 1).all()


def test_pose_features_invariant_to_position_and_scale():
    a = landmarks()
    b = a.copy()
    b[:, :2] = b[:, :2] * 2.5 + 40
    assert np.allclose(sc.pose_features(a), sc.pose_features(b), atol=1e-5)


def test_mirror_swaps_left_right_angles():
    a = landmarks(1)
    f, fm = sc.pose_features(a), sc.pose_features(sc.mirror_landmarks(a, 400))
    # angle pairs (left, right) swap places after mirroring
    for l, r in [(0, 1), (2, 3), (4, 5), (6, 7)]:
        assert abs(f[l] - fm[r]) < 1e-5 and abs(f[r] - fm[l]) < 1e-5


def test_hidden_joint_not_measured():
    a = landmarks(2)
    a[25, 2] = 0.2  # left knee hidden
    f = sc.pose_features(a)
    assert f[6] == 0.0 and f[7] > 0  # left knee angle missing, right knee present


def test_no_person_gives_zero_and_fill_missing():
    seq = np.stack([sc.pose_features(landmarks(3)), sc.pose_features(np.zeros((33, 3), np.float32))])
    assert seq[1, -1] == 0
    filled = sc.fill_missing(seq)
    assert np.allclose(filled[1, :-1], seq[0, :-1]) and filled[1, -1] == 0


@pytest.mark.parametrize("kind", ["video", "pose", "fusion"])
def test_models_forward(kind):  # UT-09
    m = sc.build_model(kind)
    logits, att = m(torch.randn(4, 15, sc.FEAT_DIM), torch.randn(4, 15, sc.POSE_DIM))
    assert logits.shape == (4, 15) and att.shape == (4, 15)
    assert torch.allclose(att.sum(1), torch.ones(4), atol=1e-5)


def test_models_learn_quickly():
    """A tiny synthetic task the models must fit: catches broken wiring before Colab time is spent."""
    torch.manual_seed(0)
    y = torch.randint(0, 15, (256,))
    x = torch.randn(256, 15, sc.FEAT_DIM) * 0.1
    x[torch.arange(256), :, y] += 2.0
    p = torch.randn(256, 15, sc.POSE_DIM)
    m = sc.build_model("fusion")
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    for _ in range(60):
        loss = torch.nn.functional.cross_entropy(m(x, p)[0], y)
        opt.zero_grad(); loss.backward(); opt.step()
    m.eval()
    assert (m(x, p)[0].argmax(1) == y).float().mean() > 0.9


def test_temperature_scaling_reduces_overconfidence():  # UT-10
    torch.manual_seed(0)
    y = torch.randint(0, 15, (2000,))
    logits = torch.randn(2000, 15)
    logits[torch.arange(2000), y] += 1.5
    logits *= 4  # over-confident
    probs = torch.softmax(logits, 1).numpy()
    T = sc.TemperatureScaler().fit(logits, y)
    cal = torch.softmax(logits / T, 1).numpy()
    assert T > 1
    assert sc.expected_calibration_error(cal, y.numpy()) < sc.expected_calibration_error(probs, y.numpy())


@pytest.mark.parametrize("name", ["SmartCricket_Train.ipynb", "SmartCricket_Train_Fast.ipynb",
                                 "SmartCricket_Train_FineTune.ipynb"])
def test_notebook_cells_compile(name):
    nb = json.loads((ROOT / "training" / name).read_text())
    common = (ROOT / "training" / "sc_common.py").read_text()
    for i, c in enumerate(nb["cells"]):
        if c["cell_type"] != "code":
            continue
        src = c["source"]
        if src.startswith("%%writefile"):
            assert src.split("\n", 1)[1].strip() == common.strip(), "notebook copy of sc_common.py is out of date"
            continue
        src = "\n".join("pass" if re.match(r"\s*!", l) else l for l in src.split("\n"))
        compile(src, f"cell{i}", "exec")


@pytest.mark.parametrize("name", ["SmartCricket_Train.ipynb", "SmartCricket_Train_Fast.ipynb",
                                 "SmartCricket_Train_FineTune.ipynb"])
def test_notebook_selects_on_validation_before_test_evaluation(name):
    """A tempting test winner must never override the validation winner."""
    nb = json.loads((ROOT / "training" / name).read_text())
    sources = [cell["source"] for cell in nb["cells"] if cell["cell_type"] == "code"]
    selection = next(src for src in sources if src.startswith("# Select the model before test evaluation"))
    evaluation = next(src for src in sources if "p_cal = torch.softmax" in src)
    assert sources.index(selection) < sources.index(evaluation)
    runs = {
        ("video", 1): {"val_f1": 0.80, "test_macro_f1": 0.40},
        ("video", 2): {"val_f1": 0.76, "test_macro_f1": 0.45},
        ("fusion", 1): {"val_f1": 0.90, "test_macro_f1": 0.99},
        ("fusion", 2): {"val_f1": 0.50, "test_macro_f1": 0.98},
    }
    context = {"np": np, "KINDS": ["video", "fusion"], "SEEDS": [1, 2], "runs": runs}
    exec(selection, context)
    # Mean validation performance chooses video despite fusion's best individual
    # validation run and much higher test scores.
    assert (context["best_kind"], context["best_seed"]) == ("video", 1)
    for run in runs.values():
        run["test_macro_f1"] = 1 - run["test_macro_f1"]
    exec(selection, context)
    assert (context["best_kind"], context["best_seed"]) == ("video", 1)
    runs[("fusion", 2)]["val_f1"] = 0.95
    exec(selection, context)
    assert (context["best_kind"], context["best_seed"]) == ("fusion", 2)
