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

nb = json.loads((HERE / "SmartCricket_Train.ipynb").read_text())
cells = [c["source"] for c in nb["cells"] if c["cell_type"] == "code"]

REPLACE = {
    "!nvidia-smi --query-gpu=name,memory.total --format=csv\n": "",
    "!pip -q install mediapipe gdown\n": "",
    "from google.colab import drive\ndrive.mount('/content/drive')\n": "",
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
}

g = {"__name__": "__main__", "display": print}
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
