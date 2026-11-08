# Player roster and details sheet

Updated 6 November 2026. Open `/app/players.html` with an admin account.

The roster has aligned columns, separate primary/secondary values, a concise summary, and no repeated “Demo activity” labels, sample-data paragraph, or long streak/privacy paragraphs. Stored practice provenance is preserved in the existing data and API. Names, measurements, counts and accounts are unchanged.

Click any player row, or focus the player-name button and press Enter, to open a sheet on the right. It shows the selected player's identity, analysis counts, current/best streak, plan completion, level, XP, visibility, most common shot and account dates. The optional “How streaks work” section holds the longer explanation.

The sheet uses the aggregates already returned by the admin overview API. It does not fetch private photos, videos, conversations or analysis files. No new endpoint or database write is involved.

Use the close button, Escape, or the backdrop to dismiss the sheet. Keyboard focus returns to the selected player. The sheet occupies the full width on a phone, scrolls independently, and supports both light and dark themes. The table scrolls horizontally within its card on small screens.

Search and sorting remain available. Sort headers expose their direction to assistive technology. Missing plan/visibility values remain distinct from zero, and loading failures provide a retry action.

Verification: **32 JavaScript tests passed**. Real Chrome checked row and keyboard opening, selected-player data, zero/no-plan values, close button, Escape, backdrop, focus return, empty search, sorting, failed-load retry, and exact desktop/mobile widths. No private-media requests or unexpected script exceptions occurred.

Evidence: [browser checks](verification/player-sheet-browser.json), [clean roster](verification/players-clean-desktop.png), [desktop sheet](verification/player-sheet-desktop.png), [mobile sheet](verification/player-sheet-mobile.png), and [dark theme](verification/player-sheet-dark-mobile.png).
