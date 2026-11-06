# Synthetic demo showcase

Implemented on 5 November 2026. Sign in as a player and choose **Demo showcase**, or open `/app/showcase.html`.

The showcase adds a separate presentation workspace with five fictional scenarios and 70 synthetic practice-day records. It reads a bundled fixture and never reads or writes player captures, practice goals, training history, model checkpoints, or evaluation results. The static fixture contains no private player data; the player menu follows the app's existing sign-in and role navigation.

| Scenario | What it demonstrates |
|---|---|
| Same setup, closer to a personal number | Eight shared joints and a fictional knee angle of 148° → 141°; signed change −7°. A chosen 140° target has distances 8° → 1°. |
| Same setup, farther from a personal number | Practice activity alongside a knee angle of 148° → 155°, farther from the same target. |
| Camera and movement phase mismatch | Descriptive deltas remain visible with explicit exploratory-comparison warnings. |
| Low visibility and missing measurements | Six excluded joints, two shared joints, and no target distance when the focus joint is unavailable. |
| Recovery days and honest activity totals | Five rest days contain no planned drills; the goal has no numeric target. |

Every displayed value is invented. A closer personal target, angle delta, matching setup check, or completed drill does not establish better technique, causation, real player progress, or classifier accuracy. The showcase must not be used as training data or held-out evaluation evidence.

## Presentation and exports

Switch scenarios to demonstrate different feature states. Download the selected scenario as CSV or JSON, or use **Print demo report**. The page, printed report, JSON, and every CSV record retain synthetic-data provenance. CSV includes measurements, exclusions, warnings, goal context, and daily activity; JSON includes the original selected scenario and computed comparison/activity summaries.

The calculation uses only finite 0–180° angles with visibility ≥0.5 in both fictional captures. Signed change is retest minus baseline. Activity adherence is completed planned drills divided by planned drills; rest days have no planned drills. Neither calculation is a model-performance or batting-skill metric.

The local app server serves all showcase logic and data. No external model, API, LLM, chart library, or internet connection is needed for its calculations or exports; the shared stylesheet falls back to system fonts when web fonts are unavailable. The app server must remain running. This does not add a service worker or make the whole app available without its server.

## Fixture and verification

The fixture is `frontend/data/showcase.json`. Rebuild it deterministically with:

```sh
.venv/bin/python scripts/build_showcase.py
node --test tests/test_showcase.cjs
```

`scripts/build_showcase.py` uses fixed fictional dates and values, never accesses a database, and never overwrites measured results. Tests cover provenance, scenario counts, signed deltas, target distances, camera mismatch, visibility/missing-angle exclusions, rest-day denominators, and export labeling/escaping.

All **7 focused Node tests passed**, and the complete JavaScript suite passed **25 tests** after integration. Real headless Chrome also checked all five scenario states, actual CSV/JSON download buttons, print-mode provenance, and zero backend API requests. Desktop 1440px and mobile 390px views had equal client/scroll widths with no unexpected JavaScript exceptions. Browser checks used an isolated temporary profile and static frontend server with a fictional localStorage session; no real user account, backend database, trained model, or LLM was involved. Web fonts were blocked to check the local calculations and fallback layout. The shared topbar skips its real XP/status fetch on the showcase page.

See the [desktop screenshot](verification/showcase-desktop.png), [mobile screenshot](verification/showcase-mobile.png), and [browser check record](verification/showcase-browser-checks.json). These are feature and presentation checks, not classifier-accuracy validation.
