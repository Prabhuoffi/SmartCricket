# SmartCricket AI

Explainable multimodal cricket shot analysis and virtual coaching (M.E. CSE final-year project).

| Part | What it does |
|---|---|
| Photo analysis | MediaPipe pose (33 points), 8 joint angles with visibility rule, animated skeleton |
| Video analysis | Works at once as **movement analysis** (skeleton on 15 frames, joint angles over time, frame of most movement, joint ranges). With the trained models installed it also gives the shot type (15 classes) with calibrated confidence, top-3, Grad-CAM heatmaps and the attention timeline |
| Reference comparison | DTW alignment of joint angles against an admin-provided reference clip |
| AI coach | OpenAI or Gemini, grounded on stored numbers only, with a number check |
| Live mirror | Camera drills in the browser (MediaPipe JS, nothing uploaded): live skeleton and angles, reps and holds counted, drill ticked automatically |
| Input quality | Sharpness, light, batter size, whole body, camera view and other people checked on every upload, with tips |
| Training coach | Daily three-drill plan from the player's own photos and clips, check-in with soreness safety rule, quiz, XP, streaks, five levels, weekly report |
| Platform | Player and admin roles, history, dashboard, CSV and one-click PDF reports, admin console |

## How it flows

```
Landing page -> Sign in -> role
  Player: Dashboard -> Training (check-in, drills, quiz) -> Photo / Video analysis -> result page
          (skeleton, angles, coach, PDF, compare with reference) -> History -> Progress (levels, weekly report)
          Results feed the next day's drills.
  Admin:  Overview (stats, setup checklist) -> All players -> Model results (import training results)
          -> Reference clips -> Users
```

## Roles (the single source of truth)

| | Player | Admin |
|---|---|---|
| Pages | dashboard, training, live, progress, image, video, history, analysis, clip | admin (overview), players, models, references, users |
| Server | everything under `/api/image`, `/api/video/analyse`, `/api/train`, `/api/coach`, `/api/history`, `/api/dashboard`, `/api/reports` (403 for admins) | everything under `/api/admin` (403 for players) |
| How it is given | anyone who registers | email listed in `ADMIN_EMAILS` in `.env` |

The server is the real gate (`current_player` / `current_admin` in `backend/app/auth.py`); the page lists in
`frontend/js/api.js` (`PLAYER_LINKS`, `ADMIN_LINKS`) only decide menus and redirects. Change both together.

## 1. Run the web app on your Mac

```bash
cd smartcricket-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
createdb smartcricket            # PostgreSQL must be running
cp .env.example .env             # set JWT_SECRET, ADMIN_EMAILS, LLM_API_KEY
uvicorn backend.app.main:app --reload --reload-dir backend --port 8000
```

Open http://localhost:8000. Photo analysis works straight away. Video analysis needs the trained models (step 2).

## 2. Train the video models (Google Colab)

1. Open `training/SmartCricket_Train.ipynb` in Google Colab (File -> Upload notebook).
2. `Runtime -> Change runtime type -> T4 GPU`, then `Runtime -> Run all`. Allow Google Drive access when asked.
3. It downloads CricShot10k, caches features to `MyDrive/SmartCricket/`, trains E1 (video), E2 (pose) and
   E3 (video + pose) with three seeds each, and evaluates them. About 2 to 3 hours; if Colab disconnects,
   press **Run all** again and it continues from the cache.
4. Two zip files download at the end:
   - `smartcricket_models.zip` -> unzip into `models/` (gives `video.pt`, `pose.pt`, `fusion.pt`), restart the server.
   - `smartcricket_results.zip` -> tables and charts for Chapter 8; upload its `summary.json` on the Admin page.

`training/sc_common.py` is shared by the notebook and the app, so clips are prepared the same way in both.
After editing it, rebuild the notebook with `python training/build_notebook.py`.

## 3. Administrator

Put your email in `ADMIN_EMAILS` in `.env` and sign in again. The admin console has five pages: Overview
(usage and a setup checklist), All players (level, streak, plan completion), Model results (import
`results/summary.json`), Reference clips (one clean example per shot) and Users. Admin accounts do not analyse
or train; use a player account for that.

## 4. AI coach

| Provider | Settings in `.env` |
|---|---|
| OpenAI | `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`, `LLM_API_KEY=sk-...` |
| Gemini | `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-3.8-flash`, `LLM_API_KEY=...` |

## 5. Tests

```bash
pytest -q                          # unit, API and video tests (SQLite, no PostgreSQL needed)
python training/dry_run.py         # runs every notebook cell on a tiny synthetic dataset
```

## Layout

| Path | What it is |
|---|---|
| `backend/app/main.py` | FastAPI app, routers, static front end |
| `backend/app/auth.py` | Accounts, bcrypt, JWT, admin role |
| `backend/app/storage.py` | Upload checks: type, size, readable (400 / 413 / 422) |
| `backend/app/pose.py` | Photo posture analysis |
| `backend/app/video.py` | Video pipeline: frames, pose, classifier, temperature, Grad-CAM, attention |
| `backend/app/dtw.py` | Dynamic Time Warping comparison |
| `backend/app/coach.py` | Grounded AI coach |
| `backend/app/trainer.py` | Training coach: drills, check-in, XP, streaks, levels, quiz, weekly report |
| `backend/app/routers/` | image, video, analyses, dashboard, reports, coach, train, admin |
| `frontend/` | HTML, CSS and vanilla JavaScript pages |
| `training/` | Shared code, Colab notebook and its builder, dry run |
| `tests/` | Tests named after the test-case IDs in Chapter 7 of the report |

## Data and image credits

CricShot10k (Dihan et al., IEEE Access 2026) is for non-commercial research use only; the copyright of the videos
remains with their owners. `tests/samples/batter.jpg`: Acabashi, Wikimedia Commons, CC BY-SA 4.0.
