# Project enhancement and evidence review

Completed 5 November 2026. The requested scope is feature growth with clearly labeled demo data and revised project documents. Accuracy is reported only from existing recorded artifacts.

## Implemented changes

- Added a player **Demo showcase** page at `/app/showcase.html`: five scenarios, 70 fictional practice days, baseline/retest angles, personal-target distance, visibility exclusions, capture warnings, recovery-aware adherence, CSV/JSON downloads and printable reports.
- Kept the demo fixture and calculations separate from stored player history and model results. Its navigation follows the existing player interface; it makes no backend API calls and does not display real account XP.
- Added cases where a target gets farther away, capture conditions disagree, measurements are unavailable, and recovery days have no planned drills. A numeric angle change is never presented as verified skill improvement.
- Fixed future notebook selection: choose the model kind using mean validation macro-F1, then the seed using validation evidence, before evaluating the test set. The chosen model is reused for analysis/export and future summaries record selection provenance. Regenerated all three notebooks.
- Labeled future demo-account seed sessions and drills explicitly. Copied analyses retain source values and receive source provenance; randomized latency is disclosed. The seeder was not run, and existing records were not relabeled.
- Created a revised 31-slide PPT, editable project report, editable speaker guide, PDF versions, and labeled CSV/JSON samples in [deliverables](../../deliverables/README.md). Original PPT/PDF files remain unchanged.

See [the showcase feature guide](demo-showcase.md) and [the existing personal-goal workflow](practice-goals.md).

## Accuracy and provenance

| Existing recorded metric | Value |
|---|---:|
| Local video Top-1 | 56.17% |
| Local video + 2D pose Top-1 | 63.93% |
| Local fusion gain | 7.76 percentage points |
| Local fusion macro-F1 | 62.24% |
| Local fusion Top-3 | 89.60% |
| Recorded test clips | 1,289 |
| Stored runs | One seed per model |

These values come from `data/results/summary.json` and the existing CSVs. Checkpoint metadata is consistent with the recorded temperatures and histories, but this revision did not reproduce training or test inference. The supplied base paper reports 89% Top-1 under its own setup; the project does not establish higher accuracy than the paper. Top-3 must not be called Top-1 accuracy.

Two issues need source-data review before a formal reproducibility claim:

1. `split_counts.csv` totals 10,091 clips, while the paper states 10,086. Full clip/split manifests are unavailable here.
2. `E10_significance.csv` has paired-test “only first right / only second right” counts inconsistent with the model ordering and accuracy direction. Raw paired predictions are unavailable, so the revised documents omit a directional significance claim.

Current training source includes stronger features, crops and optional fine-tuning. Installed checkpoints still use the legacy EfficientNet-V2-S backbone. No new accuracy is attributed to those prepared training changes. Synthetic showcase data and moving-circle dry-run clips are not real training or test evidence.

## Verification performed

- `.venv/bin/python -m pytest -q`: **157 passed** in 41.18 seconds. One existing Starlette TestClient deprecation warning remains.
- `node --test tests/*.cjs`: **25 passed**, including seven new showcase tests.
- A targeted selection test deliberately makes validation and test rankings disagree, then checks that selection follows validation. Demo-clone tests check provenance while preserving source timestamps, angles, confidence and summary.
- Headless Chrome checked all five showcase states, real CSV/JSON download buttons, printed provenance, and desktop 1440px/mobile 390px layouts. Scroll width equaled viewport width. There were zero backend API requests and zero unexpected script exceptions in the final showcase checks.
- Browser evidence uses an isolated static frontend server and temporary profile with a fictional localStorage session. It does not prove backend authentication, classifier accuracy, external LLM quality or sporting improvement. The test server and browser were stopped.
- Generated editable documents were reopened programmatically; LibreOffice exported the PDF versions. PDF text and rendered page samples were checked for unsupported claims, missing content and layout problems.

Screenshots: [demo workspace](verification/showcase-desktop-viewport.png), [comparison](verification/showcase-comparison-viewport.png), [mobile](verification/showcase-mobile.png). The [browser check record](verification/showcase-browser-checks.json) describes the isolated context.

## Rebuilding artifacts

From `smartcricket-ai`:

```sh
.venv/bin/python scripts/build_showcase.py
.venv/bin/python -m pip install -r requirements-docs.txt
.venv/bin/python scripts/build_project_documents.py --pdf
```

The document libraries are optional and separate from runtime requirements. PDF export needs LibreOffice's `soffice` command. The builder reads the original presentation as a design template, saved metrics and the demo fixture. It writes only revised artifacts in `deliverables/`; original documents, checkpoints, results and databases remain untouched.

To pursue genuine accuracy improvement, first reconcile the source data and freeze leakage-aware splits. Train on genuine labels, augment training only, choose all models on validation, then save held-out predictions and repeat prespecified seeds. Update the numerical claims only after those measurements exist.
