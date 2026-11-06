# Personal practice goals and before-and-after comparison

Implemented locally on 4 November 2026. Open `/app/practice.html` after signing in with a player account.

The feature connects **baseline → personal goal → practice → retest → measured comparison**. It uses the player's own earlier capture alongside the existing administrator-provided reference comparisons.

## Using the feature

1. Analyse a photo or clip, then choose **Set a goal or compare** at the end of the report. You can also choose an existing baseline on **Practice goals**.
2. Name your goal and choose a joint measured in the baseline. Optionally add a personal angle target, practice notes, and review date. The target is chosen by the player; the app does not present an ideal batting angle.
3. Choose **Practise** to open Training with the goal visible. Daily check-in and recovery guidance still apply. Saving a goal does not automatically rewrite the daily plan or award XP.
4. Choose **Capture retest**. The upload page reminds you to match the camera position, shot, body side, and movement phase. A successful upload opens beside the baseline. For multi-shot videos, choose the individual detected stroke to compare.
5. Select a newer analysis of the same type. For clips, choose a frame in each clip that shows the same movement phase. Frames are not automatically aligned; the displayed numbers use exactly those selected frames.
6. Confirm the matching setup if applicable and choose **Compare measurements**. Review shared visible joints, signed angle changes, excluded joints, and recording-condition checks.
7. Choose **Save retest to this goal** to retain the pair and frame selections. Download the PDF or mark the goal complete when you consider your practice objective fulfilled. Completion is a manual workflow status, not a verified skill rating. Goals can be reopened, archived, or deleted.

## What the comparison means

- Change is **retest minus baseline**, in degrees. For example, `148° → 139°` is `−9°`.
- Only joints with valid measurements in both selected captures receive a delta. Low-visibility, missing, non-finite, and out-of-range values are excluded.
- Comparisons remain exploratory when setup is unconfirmed, fewer than four joints are shared, quality is poor or unavailable, camera-view categories differ, or confident shot predictions conflict. These checks are heuristics; matching categories and player confirmation cannot prove identical capture conditions.
- A chosen numeric target can show the distance of each measurement from that target. Neither a smaller angle nor a smaller target distance establishes better batting technique or proves that practice caused a change.
- “Newer” refers to when the analysis was saved, not a recording timestamp extracted from the camera file. Players must choose the correct chronological captures.
- Video previews use saved skeleton images when available. Classified clips without those images get an overlay reconstructed from their stored landmarks, without repeating model inference. Older clips without pose landmarks show the available frame.

## Persistence and access

The additive `practice_goals` table is created through the app's existing startup `create_all` mechanism. Existing analysis and training tables are retained. Restart the backend if it is running without automatic reload.

All `/api/practice` routes require a player session. The baseline, retest, goal, previews, and comparison PDF use ownership checks. Deleting a goal leaves its media in History. Deleting a linked capture clears the goal's evidence/frame references and setup confirmation while preserving its title, notes, and manual status; the interface explains that the capture is unavailable.

API routes:

| Route | Purpose |
|---|---|
| `GET /api/practice/goals` | Owned goals and supported joints |
| `POST /api/practice/goals` | Save a baseline goal |
| `PATCH /api/practice/goals/{id}` | Update goal fields, retest, selected frames, confirmation, or status |
| `DELETE /api/practice/goals/{id}` | Remove the goal |
| `GET /api/practice/compare` | Compare an owned baseline and retest |
| `GET /api/practice/compare/pdf` | Download the same comparison as a PDF, optionally with goal context |
| `GET /api/practice/captures/{id}/preview` | Protected preview for a photo or selected clip frame |

Comparison queries accept `baseline_id`, `retest_id`, optional zero-based `baseline_frame` and `retest_frame`, and `same_setup`. The PDF additionally accepts `goal_id`, whose owned baseline must match the comparison.

## Verification

- **119 Python tests passed**, including 39 new comparison/goal/report tests. These cover shared visibility, valid angle ranges, selected frames, chronology, quality conditions, ownership, manual completion, evidence deletion, classified-clip overlay reconstruction, and exact PDF numbers.
- **12 JavaScript tests passed** for journey states, goal context through uploads, candidate selection, visibility filtering, frame validation, and query parameters.
- Real Chrome exercised an actual photo baseline → saved goal → Training → photo retest upload → comparison → explicit save → PDF download → reload → completion/reopen/archive. Real clip uploads were compared at frames 1 and 15, with their stored angles checked independently.
- The browser also checked ownership denial, invalid pairs/frames, and deleted evidence states. Tested mobile views had exactly `390px` client width and scroll width, with no unexpected script exceptions or console errors in the normal journey.
- Test application data and browser profiles are temporary and separate from the player's existing database and uploads. Browser inference used movement mode, while the classified-clip preview fallback is covered with synthetic stored landmarks. External LLM and physical webcam behavior are outside these feature checks.

The comparison PDF contains the selected capture previews, shared joint values, signed deltas, condition checks, exclusions, and optional personal target. It repeats the interpretation limits so a downloaded report retains the context of the screen.

Screenshots: [photo comparison on desktop](verification/practice-comparison-desktop.png), [comparison checks on mobile](verification/practice-comparison-mobile.png), and [selected video frames](verification/practice-video-desktop.png). All show an isolated test account and sample captures.
