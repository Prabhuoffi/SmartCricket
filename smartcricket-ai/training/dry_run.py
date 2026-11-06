"""Runs every cell of SmartCricket_Train.ipynb locally on a tiny synthetic dataset.

Colab-only lines (Drive mount, pip, downloads to the browser) are replaced, the GPU timing is skipped,
and the dataset is 15 zip archives of generated clips. It checks that the notebook runs end to end;
the numbers it prints mean nothing.

Run:  .venv/bin/python training/dry_run.py
"""
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
TMP = Path(tempfile.mkdtemp(prefix="sc_dry_"))
sys.path.insert(0, str(HERE))
os.chdir(TMP)

import sc_common as sc  # noqa: E402

# ---- fake dataset: one zip per class, like the real release
src = TMP / "dataset"
src.mkdir()
rng = np.random.default_rng(0)
for ci, cls in enumerate(sc.CLASSES):
    folder = TMP / "tmpclips" / cls
    folder.mkdir(parents=True)
    for k in range(14):
        vw = cv2.VideoWriter(str(folder / f"{cls.lower().replace(' ', '_')}_{k:03d}.mp4"),
                             cv2.VideoWriter_fourcc(*"mp4v"), 25, (320, 180))
        for t in range(25):
            f = np.full((180, 320, 3), 40, np.uint8)
            cv2.circle(f, (40 + ci * 15, 30 + t * 5), 12, (255, 255 - ci * 15, 60), -1)  # class-dependent motion
            f = np.clip(f + rng.integers(0, 20, f.shape), 0, 255).astype(np.uint8)
            vw.write(f)
        vw.release()
    with zipfile.ZipFile(src / f"{cls}.zip", "w") as z:
        for p in folder.iterdir():
            z.write(p, f"{cls}/{p.name}")

# ---- extra clips: one new shot with enough clips (trained) and one with too few (skipped)
for shot, n, ci in (("Switch Hit", 45, 15), ("Leave", 5, 16)):
    folder = TMP / "drive" / "extra_shots" / shot / "match01"
    folder.mkdir(parents=True)
    for k in range(n):
        vw = cv2.VideoWriter(str(folder / f"clip_{k:03d}.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 25, (320, 180))
        for t in range(25):
            f = np.full((180, 320, 3), 40, np.uint8)
            cv2.circle(f, (40 + ci * 15, 30 + t * 5), 12, (255, 255 - ci * 15, 60), -1)
            vw.write(np.clip(f + rng.integers(0, 20, f.shape), 0, 255).astype(np.uint8))
        vw.release()
    if shot == "Switch Hit":   # several sources, so the shot reaches every split
        for k in range(n):
            m = folder.parent / f"match{k % 9:02d}"
            m.mkdir(exist_ok=True)
            (folder / f"clip_{k:03d}.mp4").rename(m / f"clip_{k:03d}.mp4")

NB = sys.argv[1] if len(sys.argv) > 1 else "SmartCricket_Train.ipynb"   # e.g. SmartCricket_Train_FineTune.ipynb
nb = json.loads((HERE / NB).read_text())
cells = [c["source"] for c in nb["cells"] if c["cell_type"] == "code"]

REPLACE = {
    "!nvidia-smi --query-gpu=name,memory.total --format=csv\n": "",
    "!pip -q install mediapipe gdown\n": "",
    "from google.colab import drive\n": "class drive:\n    mount = staticmethod(lambda *a, **k: None)\n",
    "OUT = Path('/content/drive/MyDrive/SmartCricket')": f"OUT = Path('{TMP}/drive')",
    "DATASET_IN_MY_DRIVE = None": f"DATASET_IN_MY_DRIVE = '{src}'",
    "RAW = Path('/content/raw'); VIDEOS = Path('/content/videos')": f"RAW = Path('{TMP}/raw'); VIDEOS = Path('{TMP}/videos')",
    "SHARD = 500": "SHARD = 64",
    "assert len(df) > 9000": "assert len(df) > 150",
    "from google.colab import files\nfiles.download('/content/smartcricket_models.zip'); files.download('/content/smartcricket_results.zip')\n": "",
    "'/content/smartcricket_models'": f"'{TMP}/smartcricket_models'",
    "'/content/smartcricket_results'": f"'{TMP}/smartcricket_results'",
    "MODEL_FILE = f'/content/pose_{POSE_MODEL}.task'": f"MODEL_FILE = f'{TMP}/pose_{{POSE_MODEL}}.task'",
    "speed = pd.DataFrame({'GPU (ms)': timed('cuda'), 'CPU (ms)': timed('cpu')})": "speed = pd.DataFrame({'CPU (ms)': timed('cpu')})",
    "def train(kind, seed, epochs=40, patience=6": "def train(kind, seed, epochs=8, patience=6",
    "plt.show()": "plt.close('all')",
    "DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'":
        "DEVICE = 'mps' if torch.backends.mps.is_available() else 'cpu'",   # Apple GPU: much faster than the CPU
    "FT_EPOCHS, FT_FRAMES = 4, 5": "FT_EPOCHS, FT_FRAMES = 1, 2",
    "MIN_CLIPS = 40": "MIN_CLIPS = 10",   # the fake dataset has 14 clips per shot
    # macOS cannot fork a process that has MediaPipe/PyTorch loaded (Colab's Linux can): run pose in-process
    "    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('fork')) as ex:\n"
    "        res = list(ex.map(pose_worker, chunks))": "    res = list(map(pose_worker, chunks))",
    "num_workers=2, multiprocessing_context='fork'": "num_workers=0",
}

import __main__  # noqa: E402  cells run in __main__, as in Colab, so worker processes can find their functions

g = __main__.__dict__
g["display"] = print
for i, src_code in enumerate(cells):
    if src_code.startswith("%%writefile"):
        shutil.copy(HERE / "sc_common.py", TMP / "sc_common.py")
        continue
    for a, b in REPLACE.items():
        src_code = src_code.replace(a, b)
    assert "!" not in [l.strip()[:1] for l in src_code.splitlines()], f"shell line left in cell {i}"
    print(f"\n===== cell {i} =====")
    exec(compile(src_code, f"cell{i}", "exec"), g)

print("\nDRY RUN OK. Outputs in", TMP)
for p in sorted((TMP / "drive").rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(TMP), f"{p.stat().st_size // 1024} KB")
