# Delete confirmation modal

Implemented 6 November 2026. Photo/video reports, practice goals and reference clips now use the same app-styled confirmation dialog instead of the browser's `confirm()` pop-up.

The modal shows the action, selected item and removal scope. Cancel receives initial focus. Cancel, the close button, Escape and backdrop dismiss the modal without sending a deletion request. Focus returns to the original control when it remains available.

Confirming runs the supplied action once and shows a loading state. Confirmation, cancellation and closing are disabled while that request is pending. Failure keeps the dialog open with a readable error and enables retry. Success closes the dialog before the page's existing success/navigation behavior.

Report Delete buttons stay disabled until the analysis loads, so the modal can identify the selected record. Practice-goal deletion explicitly states that captures and reports remain in History. Existing backend deletion and ownership rules are unchanged.

The component is `frontend/js/confirmation.js`, styled by `frontend/css/confirmation.css`. Callers await `confirmAction({ title, message, itemLabel, confirmLabel, busyLabel, onConfirm })`. The callback must reject on failure; the returned Boolean becomes true only after successful completion.

Verification: **37 JavaScript tests passed**. Real headless Chrome exercised all four delete flows, Cancel, close button, Escape, backdrop, default keyboard focus, focus return, pending-state dismissal protection, duplicate submission, failed request/retry, mobile layout and dark theme. Native browser dialogs and unexpected script exceptions were absent.

Browser checks used synthetic records, a temporary profile and intercepted API responses. No saved user record or media was deleted. See [browser evidence](verification/delete-confirmation-browser.json), [desktop](verification/delete-confirmation-desktop.png), [mobile](verification/delete-confirmation-mobile.png), and [dark theme](verification/delete-confirmation-dark-mobile.png).
