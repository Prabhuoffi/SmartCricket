"""Generates SmartCricket_Train.ipynb. The notebook embeds sc_common.py so Colab needs no other files.

Run:  python training/build_notebook.py
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
common = (HERE / "sc_common.py").read_text()

cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")})


def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": text.strip("\n")})


md("""
# SmartCricket AI: training the shot classifiers (E1 to E3, E9) and the robustness study (E10)

This notebook trains the five shot models described in the project report and evaluates them:

| Experiment | Model | Input |
|---|---|---|
| **E1** | Video only | EfficientNetV2-S features of 15 frames, GRU-128 + attention |
| **E2** | Pose only | MediaPipe joint angles and landmarks of 15 frames, GRU-64 + attention |
| **E3** | Video + pose | Both streams, late fusion |
| **E9a** | Pose only, 3D | 3D joint angles and world landmarks of 15 frames (view-independent), GRU-64 + attention |
| **E9b** | Video + pose, 3D | Video stream with the 3D pose stream, late fusion |

It also produces the results for **E4** (confusion matrix), **E5** (calibration), **E6** (pose reliability),
timings for **E8**, and **E10**: accuracy by camera view and image sharpness, the 2D-versus-3D angle gap per view,
and McNemar significance tests between models.

**Before you start:** `Runtime -> Change runtime type -> T4 GPU`, then `Runtime -> Run all`.

**How long:** about 2 to 3 hours on a free T4, most of it reading videos once. Every expensive step saves its
output to your Google Drive (`MyDrive/SmartCricket/`), so if Colab disconnects, just press **Run all** again and it
continues where it stopped.

**At the end** you get `smartcricket_models.zip` (trained weights) and `results/` (tables and charts for Chapter 8).
""")

md("## 1. Setup")
code("""
!nvidia-smi --query-gpu=name,memory.total --format=csv
!pip -q install mediapipe gdown
import os, sys, time, json, glob, shutil, subprocess, random
from pathlib import Path
from google.colab import drive
for attempt in range(3):   # the Drive connection sometimes fails after reopening Colab: retry
    try:
        drive.mount('/content/drive', force_remount=attempt > 0, timeout_ms=300000)
        break
    except Exception as e:
        print('Drive mount failed, retrying...', e); time.sleep(10)
else:
    raise SystemExit('Google Drive did not connect. Runtime -> Disconnect and delete runtime, then run this cell again and allow access.')
OUT = Path('/content/drive/MyDrive/SmartCricket'); OUT.mkdir(parents=True, exist_ok=True)
for d in ['cache', 'results', 'models']: (OUT / d).mkdir(exist_ok=True)
print('Outputs will be saved in', OUT)
""")

md("## 2. Shared code\nThe same file is used by the web app, so clips are prepared identically in training and in the app.")
code("%%writefile sc_common.py\n" + common)

md("## 3. Settings")
code("""
import numpy as np, pandas as pd, torch, cv2
import sc_common as sc

# Public dataset folder from the CricShot10k authors (github.com/Dihan69/CricShot10k)
DATASET_DRIVE_FOLDER = 'https://drive.google.com/drive/folders/13dQHHW8v9gt_jIssQ5PTrJToWGUXvZey'
# If the automatic download fails, open the link above, choose 'Add shortcut to Drive', and set this path:
DATASET_IN_MY_DRIVE = None    # e.g. '/content/drive/MyDrive/CricShot10k'

RAW = Path('/content/raw'); VIDEOS = Path('/content/videos')
FAST = True                   # True: 1 training run per model, up to 25 epochs (about 10-15 min of training).
                              # False: 3 runs per model with mean ± spread, as reported in the paper (about 30-60 min).
                              # Everything is cached, so you can switch to False later and rerun in about half an hour.
SEEDS = [1] if FAST else [1, 2, 3]
EPOCHS, PATIENCE = (25, 4) if FAST else (40, 6)
SPLIT = (0.70, 0.15, 0.15)
SHARD = 500                   # clips per cache file on Drive
POSE_MODEL = 'full'           # MediaPipe model for video frames: 'lite', 'full' or 'heavy'
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print('Device:', DEVICE, '| classes:', len(sc.CLASSES))
""")

md("## 4. Download and unpack CricShot10k\nThe dataset is for non-commercial research use only; the copyright of the videos stays with their owners.")
code("""
def unpack(archive, dest):
    a = str(archive).lower()
    dest.mkdir(parents=True, exist_ok=True)
    if a.endswith('.zip') or a.endswith('.tar') or a.endswith('.tar.gz') or a.endswith('.tgz'):
        shutil.unpack_archive(str(archive), str(dest))
    elif a.endswith('.rar'):
        subprocess.run(['unrar', 'x', '-o+', '-inul', str(archive), str(dest) + '/'], check=True)
    elif a.endswith('.7z'):
        subprocess.run(['7z', 'x', '-y', f'-o{dest}', str(archive)], check=True, stdout=subprocess.DEVNULL)

VIDEO_EXT = ('.mp4', '.avi', '.mov', '.mkv')

# Once every clip has been processed, the raw videos are not needed any more: the training reads only the
# small cached files in MyDrive/SmartCricket/cache. Then the 15-40 minute download is skipped completely.
def caches_complete():
    split_csv = OUT / 'splits.csv'
    if not split_csv.exists():
        return False
    n = len(pd.read_csv(split_csv)); shards = (n + SHARD - 1) // SHARD
    vid = all((OUT / 'cache' / f'video_{s:03d}.npz').exists() for s in range(shards))
    pose = all((OUT / 'cache' / f'pose_{s:03d}.npz').exists() and 'world' in np.load(OUT / 'cache' / f'pose_{s:03d}.npz').files
               for s in range(shards))
    return vid and pose
HAVE_CACHE = caches_complete()

def needed_folders():
    # Top-level dataset folders (one per shot archive) that still have clips without saved video or pose
    # features. Only these are downloaded again; None means "unknown, download everything".
    split_csv = OUT / 'splits.csv'
    if not split_csv.exists():
        return None
    rels = pd.read_csv(split_csv)['rel'].tolist(); shards = (len(rels) + SHARD - 1) // SHARD
    need = set()
    for s_ in range(shards):
        v = OUT / 'cache' / f'video_{s_:03d}.npz'; p_ = OUT / 'cache' / f'pose_{s_:03d}.npz'
        done = v.exists() and p_.exists() and 'world' in np.load(p_).files
        if not done:
            need |= {Path(r).parts[0] for r in rels[s_ * SHARD:(s_ + 1) * SHARD]}
    return need
NEED = None if HAVE_CACHE else needed_folders()
if NEED is not None:
    print('Still to process, from these dataset folders:', sorted(NEED))
if HAVE_CACHE:
    print('All clips are already processed and saved in Drive: skipping the dataset download.')
elif not any(VIDEOS.rglob('*.mp4')):
    if DATASET_IN_MY_DRIVE:
        src = Path(DATASET_IN_MY_DRIVE)
    else:
        RAW.mkdir(exist_ok=True)
        import gdown
        files = None
        if NEED:   # list the shared folder first, then fetch only the archives that are still needed
            try:
                listing = gdown.download_folder(DATASET_DRIVE_FOLDER, output=str(RAW), quiet=True, remaining_ok=True, skip_download=True)
                files = [f for f in listing if Path(f.path).name.split('.')[0] in NEED or Path(f.path).parts[0] in NEED]
                print(f'Downloading {len(files)} of {len(listing)} files (only the folders still needed)')
            except Exception as e:
                print('Could not list the folder, downloading everything:', e); files = None
        if files:
            for f in files:
                target = RAW / f.path; target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    gdown.download(id=f.id, output=str(target), quiet=False)
        else:
            gdown.download_folder(DATASET_DRIVE_FOLDER, output=str(RAW), quiet=False, remaining_ok=True)
        src = RAW
    archives = [p for p in src.rglob('*') if p.suffix.lower() in ('.zip', '.rar', '.7z', '.tar', '.gz', '.tgz')]
    print(len(archives), 'archives found')
    for a in archives:
        unpack(a, VIDEOS / a.name.split('.')[0])
        print('unpacked', a.name)
    for v in src.rglob('*'):            # videos that were not inside an archive
        if v.suffix.lower() in VIDEO_EXT:
            t = VIDEOS / v.parent.name / v.name; t.parent.mkdir(parents=True, exist_ok=True); shutil.copy(v, t)
print(sum(1 for p in VIDEOS.rglob('*') if p.suffix.lower() in VIDEO_EXT), 'video files ready')
""")

md("## 5. Index the clips and make the train / validation / test split\n"
   "The authors do not publish split lists, so we make a stratified 70/15/15 split with a fixed seed and save it. "
   "If file names show which match a clip came from, clips of one match are kept in the same split to avoid leakage.")
code("""
import re
from sklearn.model_selection import train_test_split, StratifiedGroupKFold
norm = lambda s: re.sub(r'[^a-z]', '', s.lower())
CLASS_KEYS = {norm(c): i for i, c in enumerate(sc.CLASSES)}

def class_of(path):
    for part in reversed(path.parts):
        k = norm(part)
        for key, i in CLASS_KEYS.items():
            if k == key or k.startswith(key) or key.startswith(k) and len(k) > 3:
                return i
    return None

split_file = OUT / 'splits.csv'
if split_file.exists():
    df = pd.read_csv(split_file)
    df['path'] = df['rel'].map(lambda r: str(VIDEOS / r))
    print('Loaded saved split:', split_file)
else:
    rows = []
    for p in sorted(VIDEOS.rglob('*')):
        if p.suffix.lower() in VIDEO_EXT:
            c = class_of(p.relative_to(VIDEOS))
            if c is not None:
                rows.append({'rel': str(p.relative_to(VIDEOS)), 'label': c})
    df = pd.DataFrame(rows)
    # group = file name without its trailing clip number, e.g. 'match12_shot_034' -> 'match12_shot'
    df['group'] = df['rel'].map(lambda r: re.sub(r'[_\\- ]?\\d+$', '', Path(r).stem))
    n_groups = df['group'].nunique()
    if 20 < n_groups < len(df) * 0.8:
        print(f'Found {n_groups} source groups: keeping each group in one split')
        sgk = StratifiedGroupKFold(n_splits=7, shuffle=True, random_state=42)
        folds = list(sgk.split(df, df['label'], df['group']))
        test_idx, val_idx = folds[0][1], folds[1][1]
        df['split'] = 'train'; df.loc[val_idx, 'split'] = 'val'; df.loc[test_idx, 'split'] = 'test'
    else:
        print('No source grouping in file names: plain stratified split')
        tr, rest = train_test_split(df.index, test_size=SPLIT[1] + SPLIT[2], stratify=df['label'], random_state=42)
        va, te = train_test_split(rest, test_size=SPLIT[2] / (SPLIT[1] + SPLIT[2]), stratify=df.loc[rest, 'label'], random_state=42)
        df['split'] = 'train'; df.loc[va, 'split'] = 'val'; df.loc[te, 'split'] = 'test'
    df[['rel', 'label', 'group', 'split']].to_csv(split_file, index=False)
    df['path'] = df['rel'].map(lambda r: str(VIDEOS / r))

counts = pd.crosstab(df['label'].map(lambda i: sc.CLASSES[i]), df['split'])[['train', 'val', 'test']]
counts.loc['Total'] = counts.sum()
display(counts)
counts.to_csv(OUT / 'results' / 'split_counts.csv')
assert len(df) > 9000, 'Fewer clips than expected: check the download step'
""")

code("""
# Look at one clip: the 15 frames the models will see (only when the videos are on this machine)
import matplotlib.pyplot as plt
ex = df.sample(1, random_state=0).iloc[0]
if Path(ex.path).exists():
    fr = sc.sample_frames(ex.path)
    fig, ax = plt.subplots(3, 5, figsize=(15, 5.6))
    for a, f, i in zip(ax.flat, fr, range(15)): a.imshow(cv2.resize(f, (224, 224))); a.set_title(f'frame {i+1}', fontsize=9); a.axis('off')
    fig.suptitle(f'{sc.CLASSES[ex.label]}  ({Path(ex.rel).name})'); plt.tight_layout()
    plt.savefig(OUT / 'results' / 'sample_frames.png', dpi=110); plt.show()
else:
    print('Videos were not downloaded this time (everything is cached), so the sample picture is skipped.')
""")

md("## 6. Video features (GPU, once)\nEach of the 15 frames goes through EfficientNetV2-S (ImageNet weights, frozen). "
   "Training clips are also processed mirrored, for flip augmentation. Saved in shards on Drive.")
code("""
from torch.utils.data import Dataset, DataLoader
backbone, _ = sc.build_backbone()
backbone = backbone.to(DEVICE).to(memory_format=torch.channels_last).eval()

class Clips(Dataset):
    def __init__(self, rows): self.rows = rows
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        r = self.rows[i]
        try:
            fr = sc.sample_frames(r['path']); ok = True
        except Exception:
            fr = [np.zeros((sc.SIZE, sc.SIZE, 3), np.uint8)] * sc.NUM_FRAMES; ok = False
        return sc.to_tensor(fr), sc.to_tensor(fr, flip=True), ok

rows = df.to_dict('records')
n_shards = (len(rows) + SHARD - 1) // SHARD
t0 = time.time()
for s in range(n_shards):
    f = OUT / 'cache' / f'video_{s:03d}.npz'
    if f.exists(): continue
    part = rows[s * SHARD:(s + 1) * SHARD]
    feats, flips, oks = [], [], []
    dl = DataLoader(Clips(part), batch_size=8, num_workers=2, multiprocessing_context='fork')
    with torch.no_grad(), torch.autocast('cuda', dtype=torch.float16, enabled=DEVICE == 'cuda'):
        for x, xf, ok in dl:
            B = x.shape[0]
            both = torch.cat([x, xf]).flatten(0, 1).to(DEVICE, non_blocking=True).to(memory_format=torch.channels_last)
            out = backbone(both).float().view(2, B, sc.NUM_FRAMES, -1).cpu().numpy().astype(np.float16)
            feats.append(out[0]); flips.append(out[1]); oks.append(ok.numpy())
    np.savez(f, feat=np.concatenate(feats), flip=np.concatenate(flips), ok=np.concatenate(oks))
    print(f'shard {s+1}/{n_shards} saved  ({(time.time()-t0)/60:.1f} min)')
V = [np.load(OUT / 'cache' / f'video_{s:03d}.npz') for s in range(n_shards)]
FEAT = np.concatenate([v['feat'] for v in V]); FEAT_FLIP = np.concatenate([v['flip'] for v in V])
OK = np.concatenate([v['ok'] for v in V])
print('video features', FEAT.shape, '| unreadable clips:', int((~OK).sum()))
""")

md("## 7. Pose landmarks (CPU, once)\nMediaPipe Pose on the full-resolution frames. Runs in parallel on the CPU cores. Saved in shards on Drive.")
code("""
import urllib.request, multiprocessing
from concurrent.futures import ProcessPoolExecutor
MODEL_FILE = f'/content/pose_{POSE_MODEL}.task'
if not os.path.exists(MODEL_FILE):
    urllib.request.urlretrieve(f'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_{POSE_MODEL}/float16/latest/pose_landmarker_{POSE_MODEL}.task', MODEL_FILE)

def pose_worker(paths):
    import mediapipe as mp
    from mediapipe.tasks import python as mpt
    from mediapipe.tasks.python import vision
    import sc_common as sc, numpy as np
    import cv2
    det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mpt.BaseOptions(model_asset_path=MODEL_FILE), running_mode=vision.RunningMode.IMAGE, num_poses=1))
    out = np.zeros((len(paths), sc.NUM_FRAMES, 33, 3), np.float32); sizes = np.zeros((len(paths), 2), np.int32)
    world = np.zeros((len(paths), sc.NUM_FRAMES, 33, 3), np.float32)   # 3D landmarks in metres (E9)
    qual = np.zeros((len(paths), 3), np.float32)                         # sharpness, brightness, contrast (E10)
    for k, p in enumerate(paths):
        try:
            frames = sc.sample_frames(p)
        except Exception:
            continue
        h, w = frames[0].shape[:2]; sizes[k] = (w, h)
        stats = []
        for t, f in enumerate(frames):
            r = det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(f)))
            out[k, t] = sc.landmarks_to_array(r.pose_landmarks[0] if r.pose_landmarks else None, w, h)
            if r.pose_world_landmarks:
                world[k, t] = [[q.x, q.y, q.z] for q in r.pose_world_landmarks[0]]
            if t % 5 == 0:   # same image measures as the app's input quality check
                g = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY)
                if g.shape[1] > 640: g = cv2.resize(g, (640, int(g.shape[0] * 640 / g.shape[1])), interpolation=cv2.INTER_AREA)
                stats.append((cv2.Laplacian(g, cv2.CV_64F).var(), g.mean(), g.std()))
        qual[k] = np.median(stats, 0)
    det.close()
    return out, sizes, world, qual

workers = os.cpu_count() or 2
t0 = time.time()
for s in range(n_shards):
    f = OUT / 'cache' / f'pose_{s:03d}.npz'
    if f.exists() and 'world' in np.load(f).files: continue   # older shards without 3D are redone
    paths = [r['path'] for r in rows[s * SHARD:(s + 1) * SHARD]]
    chunks = [paths[i::workers] for i in range(workers)]
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context('fork')) as ex:
        res = list(ex.map(pose_worker, chunks))
    lm = np.zeros((len(paths), sc.NUM_FRAMES, 33, 3), np.float32); sz = np.zeros((len(paths), 2), np.int32)
    wd = np.zeros_like(lm); ql = np.zeros((len(paths), 3), np.float32)
    for i in range(workers):
        lm[i::workers], sz[i::workers], wd[i::workers], ql[i::workers] = res[i]
    np.savez_compressed(f, lm=lm, size=sz, world=wd, qual=ql)
    print(f'shard {s+1}/{n_shards} saved  ({(time.time()-t0)/60:.1f} min)')
P = [np.load(OUT / 'cache' / f'pose_{s:03d}.npz') for s in range(n_shards)]
LM = np.concatenate([p['lm'] for p in P]); SIZES = np.concatenate([p['size'] for p in P])
WORLD = np.concatenate([p['world'] for p in P]); QUAL = np.concatenate([p['qual'] for p in P])

def seq_features(lm, w, flip=False):
    return sc.fill_missing(np.stack([sc.pose_features(sc.mirror_landmarks(f, w) if flip else f) for f in lm]))
POSE = np.stack([seq_features(LM[i], SIZES[i, 0]) for i in range(len(LM))]).astype(np.float32)
POSE_FLIP = np.stack([seq_features(LM[i], SIZES[i, 0], True) for i in range(len(LM))]).astype(np.float32)
usable = POSE[:, :, -1].mean()
print('pose features', POSE.shape, f'| frames with a usable pose: {usable:.1%}')

# E9: the same pose in 3D (MediaPipe world landmarks, metres), which does not depend on the camera's direction
def seq_features_3d(world, lm, flip=False):
    feats = []
    for wt, lt in zip(world, lm):
        w3, v = (sc.mirror_world(wt, lt[:, 2]) if flip else (wt, lt[:, 2]))
        feats.append(sc.pose_features_3d(w3, v))
    return sc.fill_missing(np.stack(feats))
POSE3D = np.stack([seq_features_3d(WORLD[i], LM[i]) for i in range(len(LM))]).astype(np.float32)
POSE3D_FLIP = np.stack([seq_features_3d(WORLD[i], LM[i], True) for i in range(len(LM))]).astype(np.float32)
print('3D pose features', POSE3D.shape)

# E10: camera view of each clip (side-on, angled, front-on), from the 2D landmarks
VIEW_B = np.array([sc.view_bucket(sc.view_ratio(LM[i])) for i in range(len(LM))])
print('camera views:', dict(zip(*np.unique(VIEW_B, return_counts=True))))
""")

md("### E6: pose reliability\nHow often each key joint is clearly visible across all sampled frames.")
code("""
joints = {'Nose': 0, 'Left shoulder': 11, 'Right shoulder': 12, 'Left elbow': 13, 'Right elbow': 14, 'Left wrist': 15,
          'Right wrist': 16, 'Left hip': 23, 'Right hip': 24, 'Left knee': 25, 'Right knee': 26, 'Left ankle': 27, 'Right ankle': 28}
vis = LM[OK][:, :, :, 2] >= sc.MIN_VIS
e6 = pd.DataFrame({'joint': list(joints), 'visible_%': [round(100 * vis[:, :, i].mean(), 1) for i in joints.values()]})
ang = POSE[OK][:, :, :8] * 180; valid = ang > 0
stab = [round(float(np.nanmean([np.std(a[v]) for a, v in zip(ang[:, :, k], valid[:, :, k]) if v.sum() > 3])), 1) for k in range(8)]
e6_angles = pd.DataFrame({'angle': ['Left elbow', 'Right elbow', 'Left shoulder', 'Right shoulder', 'Left hip', 'Right hip', 'Left knee', 'Right knee'],
                          'frame-to-frame std (deg)': stab})
display(e6); display(e6_angles)
e6.to_csv(OUT / 'results' / 'E6_visibility.csv', index=False); e6_angles.to_csv(OUT / 'results' / 'E6_angle_stability.csv', index=False)
""")

md("## 8. Training\nSame settings for all five models: AdamW, class-weighted cross-entropy with label smoothing 0.05, "
   "cosine learning rate with warm-up, early stopping on validation macro-F1 (patience 6), up to 40 epochs. "
   "Horizontal flip is applied to training clips only.")
code("""
from sklearn.metrics import f1_score, precision_score, recall_score, accuracy_score, confusion_matrix, top_k_accuracy_score
idx = {k: np.where((df['split'] == k).values & OK)[0] for k in ['train', 'val', 'test']}
y_all = df['label'].values
counts_tr = np.bincount(y_all[idx['train']], minlength=len(sc.CLASSES))
class_w = torch.tensor(len(idx['train']) / (len(sc.CLASSES) * counts_tr), dtype=torch.float32, device=DEVICE)
print({k: len(v) for k, v in idx.items()})

FEAT_T, FEATF_T = torch.from_numpy(FEAT), torch.from_numpy(FEAT_FLIP)
POSES = {'2d': (torch.from_numpy(POSE), torch.from_numpy(POSE_FLIP)),
         '3d': (torch.from_numpy(POSE3D), torch.from_numpy(POSE3D_FLIP))}
Y_T = torch.from_numpy(y_all).long()
KINDS = ['video', 'pose', 'fusion', 'pose3d', 'fusion3d']
NAMES = {'video': 'E1 Video only', 'pose': 'E2 Pose only (2D)', 'fusion': 'E3 Video + pose (2D)',
         'pose3d': 'E9a Pose only (3D)', 'fusion3d': 'E9b Video + pose (3D)'}
space = lambda kind: '3d' if sc.uses_3d(kind) else '2d'

def batches(ids, bs, train, sp='2d'):
    P_T, PF_T = POSES[sp]
    ids = np.random.permutation(ids) if train else ids
    for i in range(0, len(ids), bs):
        b = torch.from_numpy(ids[i:i + bs])
        x, p = FEAT_T[b].float(), P_T[b]
        if train:
            m = torch.rand(len(b)) < 0.5
            x[m], p[m] = FEATF_T[b][m].float(), PF_T[b][m]
        yield x.to(DEVICE), p.to(DEVICE), Y_T[b].to(DEVICE)

@torch.no_grad()
def predict(model, ids, sp='2d'):
    model.eval(); logits = []
    for x, p, _ in batches(ids, 256, False, sp):
        logits.append(model(x, p)[0].float().cpu())
    return torch.cat(logits)

def train(kind, seed, epochs=40, patience=6, lr=1e-3, bs=64):
    sp = space(kind)
    torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)
    model = sc.build_model(kind).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    steps = epochs * ((len(idx['train']) + bs - 1) // bs); step = 0
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: sc.cosine_warmup(s, steps, steps // 20))
    loss_fn = torch.nn.CrossEntropyLoss(weight=class_w, label_smoothing=0.05)
    best, best_state, wait, hist = -1, None, 0, []
    for ep in range(epochs):
        model.train(); tl = 0
        for x, p, y in batches(idx['train'], bs, True, sp):
            loss = loss_fn(model(x, p)[0], y)
            opt.zero_grad(); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0); opt.step(); sched.step()
            tl += loss.item() * len(y)
        vl = predict(model, idx['val'], sp); vf1 = f1_score(y_all[idx['val']], vl.argmax(1), average='macro')
        hist.append({'epoch': ep + 1, 'train_loss': tl / len(idx['train']), 'val_macro_f1': vf1})
        if vf1 > best:
            best, wait = vf1, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            wait += 1
            if wait >= patience: break
    model.load_state_dict(best_state)
    return model, best, pd.DataFrame(hist)
""")

code("""
runs = {}
for kind in KINDS:
    for seed in SEEDS:
        t0 = time.time()
        model, vf1, hist = train(kind, seed, epochs=EPOCHS, patience=PATIENCE)
        runs[(kind, seed)] = {'model': model, 'val_f1': vf1, 'hist': hist}
        hist.to_csv(OUT / 'results' / f'history_{kind}_seed{seed}.csv', index=False)
        print(f'{kind:6s} seed {seed}: best val macro-F1 {vf1:.4f}  ({len(hist)} epochs, {time.time()-t0:.0f} s)')
""")

md("## 9. Evaluation on the test split (E1 to E3, E5)\nTemperature scaling is fitted on the validation split only, then applied to the test split.")
code("""
rows_out = []
for (kind, seed), r in runs.items():
    m = r['model']
    vl, tl = predict(m, idx['val'], space(kind)), predict(m, idx['test'], space(kind))
    scaler = sc.TemperatureScaler(); T = scaler.fit(vl, Y_T[idx['val']])
    yt = y_all[idx['test']]
    p_raw = torch.softmax(tl, 1).numpy(); p_cal = torch.softmax(tl / T, 1).numpy(); pred = p_cal.argmax(1)
    r.update(T=T, test_probs=p_cal)
    rows_out.append({'model': kind, 'seed': seed, 'top1': accuracy_score(yt, pred), 'top3': top_k_accuracy_score(yt, p_cal, k=3, labels=range(15)),
                     'macro_f1': f1_score(yt, pred, average='macro'), 'precision': precision_score(yt, pred, average='macro', zero_division=0),
                     'recall': recall_score(yt, pred, average='macro'), 'temperature': T,
                     'ece_before': sc.expected_calibration_error(p_raw, yt), 'ece_after': sc.expected_calibration_error(p_cal, yt)})
res = pd.DataFrame(rows_out)
res.to_csv(OUT / 'results' / 'test_results_all_seeds.csv', index=False)
summary = res.groupby('model').agg(['mean', 'std']).drop(columns='seed').reindex(KINDS)
pct = ['top1', 'top3', 'macro_f1', 'precision', 'recall']
fmt = (lambda k, c: f"{summary.loc[k, (c, 'mean')]*100:.2f}") if len(SEEDS) == 1 else \
      (lambda k, c: f"{summary.loc[k, (c, 'mean')]*100:.2f} ± {summary.loc[k, (c, 'std')]*100:.2f}")
table = pd.DataFrame({c: [fmt(k, c) for k in summary.index] for c in pct}, index=summary.index)
table['ECE before'] = [f"{summary.loc[k, ('ece_before', 'mean')]:.4f}" for k in summary.index]
table['ECE after'] = [f"{summary.loc[k, ('ece_after', 'mean')]:.4f}" for k in summary.index]
table['T'] = [f"{summary.loc[k, ('temperature', 'mean')]:.3f}" for k in summary.index]
table.index = [NAMES[k] for k in summary.index]
display(table)
table.to_csv(OUT / 'results' / 'Table_8_2_classification.csv')
""")

md("## 10. Per-class results and confusion matrix (E4)")
code("""
best_kind = summary[('macro_f1', 'mean')].idxmax()
best_seed = max(SEEDS, key=lambda s: runs[(best_kind, s)]['val_f1'])   # chosen on validation, not test
best = runs[(best_kind, best_seed)]
yt = y_all[idx['test']]; pred = best['test_probs'].argmax(1)
per = pd.DataFrame({'shot': sc.CLASSES,
                    'precision': precision_score(yt, pred, average=None, labels=range(15), zero_division=0).round(4),
                    'recall': recall_score(yt, pred, average=None, labels=range(15)).round(4),
                    'f1': f1_score(yt, pred, average=None, labels=range(15)).round(4),
                    'test clips': np.bincount(yt, minlength=15)})
display(per); per.to_csv(OUT / 'results' / 'Table_8_3_per_class.csv', index=False)

cm = confusion_matrix(yt, pred, labels=range(15)); cmn = cm / cm.sum(1, keepdims=True)
fig, ax = plt.subplots(figsize=(10, 8.5))
im = ax.imshow(cmn, cmap='Blues', vmin=0, vmax=1)
ax.set_xticks(range(15), sc.CLASSES, rotation=60, ha='right', fontsize=9); ax.set_yticks(range(15), sc.CLASSES, fontsize=9)
for i in range(15):
    for j in range(15):
        if cm[i, j]: ax.text(j, i, cm[i, j], ha='center', va='center', fontsize=7, color='white' if cmn[i, j] > .5 else 'black')
ax.set_xlabel('Predicted shot'); ax.set_ylabel('True shot')
ax.set_title(f'Confusion matrix, {best_kind} model (seed {best_seed}), test split'); fig.colorbar(im, fraction=.04)
plt.tight_layout(); plt.savefig(OUT / 'results' / 'Fig_confusion_matrix.png', dpi=150); plt.show()
off = cm.copy(); np.fill_diagonal(off, 0); i, j = np.unravel_index(off.argmax(), off.shape)
print(f'Most confused: {sc.CLASSES[i]} -> {sc.CLASSES[j]} ({off[i, j]} clips, {off[i, j]/cm[i].sum():.1%} of {sc.CLASSES[i]})')
""")

code("""
# E5 reliability diagram for the best model, before and after temperature scaling
m = best['model']; tl = predict(m, idx['test'], space(best_kind))
fig, axs = plt.subplots(1, 2, figsize=(10, 4.4))
for ax, (name, pr) in zip(axs, [('Before scaling', torch.softmax(tl, 1).numpy()), (f"After scaling (T = {best['T']:.2f})", best['test_probs'])]):
    conf, ok = pr.max(1), pr.argmax(1) == yt; edges = np.linspace(0, 1, 11); mids, accs = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (conf > lo) & (conf <= hi)
        if sel.any(): mids.append((lo + hi) / 2); accs.append(ok[sel].mean())
    ax.bar(mids, accs, width=.09, color='#2563eb', alpha=.85, label='accuracy'); ax.plot([0, 1], [0, 1], 'k--', lw=1, label='perfect calibration')
    ax.set_title(f'{name}\\nECE = {sc.expected_calibration_error(pr, yt):.4f}'); ax.set_xlabel('confidence'); ax.set_ylabel('accuracy'); ax.legend(loc='upper left')
plt.tight_layout(); plt.savefig(OUT / 'results' / 'Fig_reliability.png', dpi=150); plt.show()
""")

md("## 11. Speed of the full pipeline (for Table 8.6)\nTime per clip from video file to prediction: reading frames, EfficientNet features, pose and the classifier.")
code("""
import mediapipe as mp
from mediapipe.tasks import python as mpt
from mediapipe.tasks.python import vision
det = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(base_options=mpt.BaseOptions(model_asset_path=MODEL_FILE), running_mode=vision.RunningMode.IMAGE))
clips = [p for p in df.iloc[idx['test'][:30]]['path'].tolist() if Path(p).exists()]
def timed(device):
    bb = backbone.to(device).float(); heads = {k: runs[(k, SEEDS[0])]['model'].to(device).eval() for k in ['video', 'fusion']}
    t = {'read_frames': [], 'cnn_features': [], 'pose': [], 'classifier': []}
    for i, pth in enumerate(clips[:20 if device == 'cuda' else 6]):
        a = time.perf_counter(); fr = sc.sample_frames(pth); b = time.perf_counter()
        with torch.no_grad():
            f = bb(sc.to_tensor(fr).to(device)).unsqueeze(0)
            if device == 'cuda': torch.cuda.synchronize()
        c = time.perf_counter()
        h, w = fr[0].shape[:2]
        lm = np.stack([sc.landmarks_to_array((r.pose_landmarks or [None])[0], w, h) for r in (det.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(x))) for x in fr)])
        p = torch.from_numpy(sc.fill_missing(np.stack([sc.pose_features(x) for x in lm]))).unsqueeze(0).to(device)
        d = time.perf_counter()
        with torch.no_grad(): heads['fusion'](f, p)
        e = time.perf_counter()
        if i: [t[k].append(v * 1000) for k, v in zip(t, [b - a, c - b, d - c, e - d])]
    return {k: round(float(np.mean(v)), 1) for k, v in t.items()}
if len(clips) >= 8 and not FAST:
    speed = pd.DataFrame({'GPU (ms)': timed('cuda'), 'CPU (ms)': timed('cpu')})
    speed.loc['total per clip'] = speed.sum()
    backbone.to(DEVICE)
    display(speed); speed.to_csv(OUT / 'results' / 'Table_8_6_speed.csv')
else:
    print('Speed test skipped: the videos are not on this machine (everything came from the Drive cache).')
    print('It is optional; the web app measures its own time per clip.')
""")

md("## 12. Robustness and significance (E10)\n"
   "Accuracy by camera view (side-on, angled, front-on) and by image sharpness, for every model, plus how far "
   "2D angles drift from 3D angles in each view. McNemar tests check whether the differences between models "
   "on the same test clips are statistically significant.")
code("""
from scipy.stats import binomtest
test = idx['test']; yt = y_all[test]
views = VIEW_B[test]; sharp_b = np.where(QUAL[test, 0] < 90, 'soft (sharpness < 90)', 'sharp')
best_seed_of = {k: max(SEEDS, key=lambda s: runs[(k, s)]['val_f1']) for k in KINDS}
pred_of = {k: runs[(k, best_seed_of[k])]['test_probs'].argmax(1) for k in KINDS}
rows_r = []
for kind in KINDS:
    for factor, groups in [('camera view', views), ('sharpness', sharp_b)]:
        for g in sorted(set(groups)):
            sel = groups == g
            if sel.sum() >= 20:   # too few clips gives an unstable score
                rows_r.append({'model': NAMES[kind], 'factor': factor, 'group': g, 'clips': int(sel.sum()),
                               'top1': accuracy_score(yt[sel], pred_of[kind][sel]),
                               'macro_f1': f1_score(yt[sel], pred_of[kind][sel], average='macro')})
rob = pd.DataFrame(rows_r)
rob_table = rob.pivot_table(index=['factor', 'group', 'clips'], columns='model', values='macro_f1').round(4)
display(rob_table); rob.to_csv(OUT / 'results' / 'E10_robustness.csv', index=False)

# chart: macro-F1 per camera view for each model
vr = rob[rob.factor == 'camera view']
order = [g for g in ['side-on', 'angled', 'front-on'] if g in set(vr.group)]
fig, ax = plt.subplots(figsize=(9, 4.4)); wbar = 0.8 / len(KINDS)
for i, kind in enumerate(KINDS):
    vals = [vr[(vr.model == NAMES[kind]) & (vr.group == g)].macro_f1.mean() for g in order]
    ax.bar(np.arange(len(order)) + i * wbar, vals, wbar, label=NAMES[kind])
ax.set_xticks(np.arange(len(order)) + wbar * (len(KINDS) - 1) / 2, order); ax.set_ylabel('macro-F1 (test)'); ax.set_ylim(0, 1)
ax.set_title('E10: accuracy by camera view'); ax.legend(fontsize=8, ncol=2); plt.tight_layout()
plt.savefig(OUT / 'results' / 'Fig_E10_view_robustness.png', dpi=150); plt.show()

# how much the 2D (picture) angles differ from the 3D (body) angles in each camera view
a2, a3 = POSE[test][:, :, :8] * 180, POSE3D[test][:, :, :8] * 180
both = (a2 > 0) & (a3 > 0)
gap = np.array([np.abs(a2[i][both[i]] - a3[i][both[i]]).mean() if both[i].any() else np.nan for i in range(len(test))])
gap_t = pd.DataFrame({'view': views, 'gap': gap}).groupby('view').gap.agg(['mean', 'median', 'count']).round(1)
display(gap_t); gap_t.to_csv(OUT / 'results' / 'E10_angle_gap_2d_vs_3d.csv')

# McNemar's exact test on the same test clips: are two models' errors significantly different?
def mcnemar(a, b):
    ra, rb = pred_of[a] == yt, pred_of[b] == yt
    n01, n10 = int((ra & ~rb).sum()), int((~ra & rb).sum())
    p = binomtest(min(n01, n10), n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
    return {'comparison': f'{NAMES[b]} vs {NAMES[a]}', 'only_first_right': n01, 'only_second_right': n10, 'p_value': p,
            'significant_at_0.05': p < 0.05}
sig_rows = [mcnemar(a, b) for a, b in [('video', 'fusion'), ('video', 'fusion3d'), ('fusion', 'fusion3d'), ('pose', 'pose3d')]]
sig = pd.DataFrame(sig_rows); display(sig); sig.to_csv(OUT / 'results' / 'E10_significance.csv', index=False)
""")

md("## 13. Export the trained models for the web app")
code("""
export = OUT / 'models'
for kind in KINDS:
    s = max(SEEDS, key=lambda s: runs[(kind, s)]['val_f1'])
    r = runs[(kind, s)]
    torch.save({'kind': kind, 'state_dict': {k: v.cpu() for k, v in r['model'].state_dict().items()}, 'temperature': r['T'],
                'classes': sc.CLASSES, 'num_frames': sc.NUM_FRAMES, 'size': sc.SIZE, 'pose_model': POSE_MODEL,
                'backbone': 'efficientnet_v2_s/IMAGENET1K_V1', 'seed': s, 'val_macro_f1': r['val_f1']}, export / f'{kind}.pt')
shutil.copy('sc_common.py', export / 'sc_common.py')
json.dump({'best_model': best_kind, 'results': rows_out, 'robustness': rows_r, 'significance': sig_rows},
          open(OUT / 'results' / 'summary.json', 'w'), indent=1, default=float)
shutil.make_archive('/content/smartcricket_models', 'zip', export)
shutil.make_archive('/content/smartcricket_results', 'zip', OUT / 'results')
from google.colab import files
files.download('/content/smartcricket_models.zip'); files.download('/content/smartcricket_results.zip')
print('Done. Copies are also in', OUT)
""")

md("""
## Next steps
1. Unzip `smartcricket_models.zip` into the `models/` folder of the `smartcricket-ai` project on your Mac
   (you should see `video.pt`, `pose.pt`, `fusion.pt`).
2. Share `smartcricket_results.zip` (or `results/summary.json`) so the numbers can go into Chapter 8 of the report.
3. Video mode in the app can then be switched on.
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []},
                                   "kernelspec": {"display_name": "Python 3", "name": "python3"},
                                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
out = HERE / "SmartCricket_Train.ipynb"
out.write_text(json.dumps(nb, indent=1))
print("wrote", out, len(cells), "cells")
