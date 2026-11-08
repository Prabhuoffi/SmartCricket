(function (root) {
  "use strict";
  let activeDialog = null;

  function createActionState({ action, pending, error, finish }) {
    let busy = false, settled = false;
    return {
      get busy() { return busy; },
      cancel() {
        if (busy || settled) return false;
        settled = true;
        finish(false);
        return true;
      },
      async submit() {
        if (busy || settled) return false;
        busy = true;
        pending(true);
        try { await action(); }
        catch (failure) {
          busy = false;
          pending(false);
          error(failure);
          return false;
        }
        busy = false;
        settled = true;
        finish(true);
        return true;
      },
    };
  }

  function confirmAction({ title = "Delete item?", message, itemLabel = "", confirmLabel = "Delete",
                           busyLabel = "Deleting…", onConfirm }) {
    if (activeDialog) return Promise.resolve(false);
    if (typeof onConfirm !== "function") throw new TypeError("A confirmation action is required");
    return new Promise(resolve => {
      const trigger = document.activeElement;
      const dialog = document.createElement("dialog");
      dialog.className = "confirmation-modal";
      dialog.setAttribute("role", "alertdialog");
      dialog.setAttribute("aria-labelledby", "confirmation-title");
      dialog.setAttribute("aria-describedby", "confirmation-message confirmation-warning");
      dialog.innerHTML = `<div class="confirmation-content">
        <div class="confirmation-top"><span class="confirmation-icon" aria-hidden="true">${typeof icon === "function" ? icon("trash") : ""}</span><button type="button" class="confirmation-close" aria-label="Cancel deletion">×</button></div>
        <h2 id="confirmation-title"></h2><p id="confirmation-message" class="confirmation-message"></p>
        <div class="confirmation-target" hidden><span>Selected item</span><b></b></div>
        <p id="confirmation-warning" class="confirmation-warning">This cannot be undone.</p>
        <p class="confirmation-error" role="alert" hidden></p>
        <div class="confirmation-actions"><button type="button" class="ghost confirmation-cancel" autofocus>Cancel</button><button type="button" class="confirmation-delete"></button></div>
      </div>`;
      dialog.querySelector("h2").textContent = title;
      dialog.querySelector(".confirmation-message").textContent = message || "This item will be permanently removed.";
      const item = dialog.querySelector(".confirmation-target");
      item.hidden = !itemLabel;
      item.querySelector("b").textContent = itemLabel;
      const cancel = dialog.querySelector(".confirmation-cancel");
      const close = dialog.querySelector(".confirmation-close");
      const confirm = dialog.querySelector(".confirmation-delete");
      const error = dialog.querySelector(".confirmation-error");
      confirm.textContent = confirmLabel;
      activeDialog = dialog;
      document.body.append(dialog);
      document.body.classList.add("confirmation-open");

      const state = createActionState({
        action: onConfirm,
        pending(busy) {
          dialog.setAttribute("aria-busy", String(busy));
          cancel.disabled = close.disabled = confirm.disabled = busy;
          confirm.setAttribute("aria-busy", String(busy));
          confirm.replaceChildren();
          if (busy) {
            error.hidden = true;
            const spinner = document.createElement("span");
            spinner.className = "spinner";
            spinner.setAttribute("aria-hidden", "true");
            confirm.append(spinner);
          }
          confirm.append(document.createTextNode(busy ? busyLabel : confirmLabel));
        },
        error(failure) {
          error.textContent = typeof failure?.message === "string" ? failure.message : "The item could not be removed. Please try again.";
          error.hidden = false;
          confirm.focus();
        },
        finish(confirmed) {
          dialog.close();
          dialog.remove();
          activeDialog = null;
          document.body.classList.remove("confirmation-open");
          resolve(confirmed);
          requestAnimationFrame(() => {
            if (trigger?.isConnected && !trigger.disabled) trigger.focus({ preventScroll: true });
          });
        },
      });
      cancel.addEventListener("click", () => state.cancel());
      close.addEventListener("click", () => state.cancel());
      confirm.addEventListener("click", () => state.submit());
      dialog.addEventListener("cancel", event => { event.preventDefault(); state.cancel(); });
      dialog.addEventListener("close", () => state.cancel());
      dialog.addEventListener("click", event => {
        const rect = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) state.cancel();
      });
      dialog.showModal();
      cancel.focus({ preventScroll: true });
    });
  }

  root.confirmAction = confirmAction;
  root.SCConfirmation = { createActionState };
  if (typeof module !== "undefined" && module.exports) module.exports = root.SCConfirmation;
})(globalThis);
