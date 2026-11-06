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
| Guided sessions | Dashboard next-step recommendations, a shared capture → understand → practise → track path, editable check-ins, and recovery-aware live training |
| Personal practice goals | Save a baseline, focus joint, optional angle target and review date; carry the goal into Training and retest uploads; compare shared visible joints and selected video frames; download a comparison PDF |
| Demo showcase | Five explicitly synthetic scenarios and 70 fictional practice days; explore goals, signed angle changes, capture warnings and recovery activity; export labeled CSV/JSON or print |

See [the product flow and implementation review](docs/flow-review.md) for the changes, validation evidence, and remaining verification limits.

The [5 November project revision](docs/project-enhancement.md) adds the demo showcase, fixes future training model selection, and provides revised PPT, editable report, speaker guide and PDFs in [deliverables](../deliverables/README.md). The showcase uses invented examples; existing recorded accuracy is unchanged. Sign in as a player and choose **Demo showcase**. See [the demo guide](docs/demo-showcase.md).

## How it flows

```
Landing page -> Sign in -> role
  Player: Dashboard -> Training (check-in, drills, quiz) -> Photo / Video analysis -> result page
          (skeleton, angles, coach, PDF, compare with reference) -> History -> Progress (levels, weekly report)
          Results feed the next day's drills.
  Admin:  Overview (stats, setup checklist) -> All players -> Model results (import training results)
          -> Reference clips -> Users
```

The dashboard recommends the next action from saved measurements and today's training status. Check-in confirms the daily plan before the interface enables drills. Players can update their check-in later; a rest check-in switches to recovery while preserving completed history. Old live-drill links explain that the drill is unavailable instead of silently starting free practice.

**Practice goals:** Open a report and choose **Set a goal or compare**, or use **Practice goals** in the sidebar. Choose a baseline and save a personal focus. Use **Practise** and **Capture retest** to keep the goal through the session. Match the capture setup, compare, then explicitly save the retest to the goal. See [the feature guide](docs/practice-goals.md).

## Roles (the single source of truth)

| | Player | Admin |
|---|---|---|
| Pages | dashboard, training, live, progress, image, video, history, analysis, clip, practice, showcase | admin (overview), players, models, references, users |
| Server | everything under `/api/image`, `/api/video/analyse`, `/api/train`, `/api/coach`, `/api/history`, `/api/dashboard`, `/api/reports`, `/api/practice` (403 for admins) | everything under `/api/admin` (403 for players) |
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

Future notebook runs select the model kind by mean **validation** macro-F1 and the seed by validation score before test evaluation. Current saved research artifacts contain one run per model; they are not fresh results from the stronger training path. Demo fixture data and synthetic dry-run results must never be imported as research accuracy.

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
node --test tests/*.cjs             # journey, goal context and comparison UI state tests (Node.js)
python training/dry_run.py         # runs every notebook cell on a tiny synthetic dataset
```

Pytest uses a temporary database and temporary upload/output/model directories. Existing MediaPipe `.task` assets are copied into that test directory; tests do not reset `data/test.db` or use your installed classifier checkpoints.

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
| `backend/app/practice.py` | Personal baseline/retest comparison rules and capture-condition checks |
| `backend/app/practice_preview.py` | Protected previews, including skeletons from saved clip landmarks |
| `backend/app/practice_report.py` | Comparison PDF with the same selected measurements and capture checks |
| `frontend/practice.html` | Saved practice goals, photo/video comparison, targets and reports |
| `frontend/showcase.html` | Isolated synthetic demonstration of comparison and practice scenarios |
| `scripts/build_showcase.py` | Deterministically rebuild the labeled synthetic scenario fixture without database access |
| `scripts/build_project_documents.py` | Rebuild revised editable documents and demo data samples; optional LibreOffice PDF export |
| `frontend/js/dropdown.js` | Reusable searchable dropdowns, keyboard controls, native form validation and dynamic option updates; see [the component guide](docs/dropdowns.md) |
| `backend/app/routers/` | image, video, analyses, dashboard, reports, coach, train, admin |
| `frontend/` | HTML, CSS and vanilla JavaScript pages |
| `training/` | Shared code, Colab notebook and its builder, dry run |
| `tests/` | Tests named after the test-case IDs in Chapter 7 of the report |

## Data and image credits

CricShot10k (Dihan et al., IEEE Access 2026) is for non-commercial research use only; the copyright of the videos
remains with their owners. `tests/samples/batter.jpg`: Acabashi, Wikimedia Commons, CC BY-SA 4.0.
