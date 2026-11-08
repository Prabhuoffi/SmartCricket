# Player streaks and demo activity

Updated 6 November 2026.

The admin roster previously rendered a zero-day streak as a dash. The demo histories ended on 3 November or earlier, so none had a current streak on 6 November. Historical activity and a good seven-day completion rate do not by themselves keep a streak current.

The roster now shows **current days** and **best days** explicitly. Zero is shown as `0 days`; an unavailable value remains distinct from zero. Streaks count consecutive days containing a capture, check-in, completed drill or saved live session. Yesterday's run remains current until the end of today.

The admin API includes `best_streak` and `demo_activity`. Last active now includes practice check-ins, completed drills and saved live sessions as well as analyses. Weekly active-player totals use that activity timestamp. Upload-volume charts still count uploads.

## Demo refresh

The requested sample activity was added to 27 known demonstration accounts after a PostgreSQL backup. On 6 November their current streaks ranged from 2 to 28 days. The operation added 93 missing check-ins, 267 labeled demo drills and 92 quiz examples. Existing rows, recordings, analysis values, accounts and passwords were preserved. The remaining player was not modified.

Stored drill reasons and the API's `demo_activity` flag identify the generated practice. Repeated source labels are omitted from the compact roster. These streaks and XP are demonstration activity, not real-player training evidence or classifier results.

The refresh is additive and manual. It does not generate activity each time the page opens. Preview or refresh later from `smartcricket-ai`:

```sh
.venv/bin/python scripts/refresh_demo_streaks.py
.venv/bin/python scripts/refresh_demo_streaks.py --apply
```

Only the exact known demo email/name pairs with the player role qualify. Existing check-ins, recovery decisions, plans and quiz answers are retained. Repeating the refresh on the same day adds no duplicate rows. A backup is required before applying changes, with a change record beside it in the ignored `data/backups/` directory.

Backup for this refresh: `data/backups/before-demo-streaks-20261106T171207-fb2d78e9.dump`. Database backups are private and are not tracked by Git.

## Verification

The complete Python suite passed **162 tests**; the JavaScript suite passed **28 tests**. Focused tests cover current/best streaks, practice-only last activity, demo identity restrictions, recovery preservation, additive refresh, repeat runs, and visible zero/unavailable states. The existing Starlette TestClient deprecation warning remains.

Browser evidence is recorded separately in [players-streaks-browser.json](verification/players-streaks-browser.json), with [desktop](verification/players-streaks-desktop.png) and [mobile](verification/players-streaks-mobile.png) screenshots.

The subsequent [roster and player-sheet update](player-sheet.md) records the current layout and interactions; the screenshots above show the initial streak fix.
