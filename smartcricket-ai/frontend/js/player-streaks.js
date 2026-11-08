(function (root) {
  "use strict";
  const count = value => Number.isInteger(value) && value >= 0 ? value : null;
  const label = value => `${value} day${value === 1 ? "" : "s"}`;
  function presentation(player) {
    const current = count(player.streak), best = count(player.best_streak);
    return {
      current: current === null ? "Unavailable" : label(current),
      best: best === null ? "" : best === 0 ? "No practice yet" : `Best: ${label(best)}`,
      active: current !== null && current > 0,
    };
  }
  root.PlayerStreaks = { presentation };
  if (typeof module !== "undefined" && module.exports) module.exports = root.PlayerStreaks;
})(typeof window !== "undefined" ? window : globalThis);
