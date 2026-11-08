// Select a frame during sustained wrist travel relative to the torso.
// This is motion tracking for capture, not a cricket shot classifier.
(function (root) {
  function createTracker() {
    let lastAt = null, previous = null, movingFrames = 0, lastCandidateAt = -Infinity;
    function reset() { lastAt = null; previous = null; movingFrames = 0; lastCandidateAt = -Infinity; }
    function update(L, width, height, now, seen) {
      if (![11, 12, 23, 24].every(i => seen(L[i]))) { reset(); return null; }
      const point = i => [L[i].x * width, L[i].y * height];
      const ls = point(11), rs = point(12), lh = point(23), rh = point(24);
      const torso = Math.hypot((ls[0] + rs[0] - lh[0] - rh[0]) / 2,
                               (ls[1] + rs[1] - lh[1] - rh[1]) / 2);
      if (!Number.isFinite(torso) || torso < 1) { reset(); return null; }
      const current = {};
      for (const [side, wrist, shoulder] of [["left", 15, ls], ["right", 16, rs]]) {
        if (seen(L[wrist])) {
          const wp = point(wrist);
          current[side] = [(wp[0] - shoulder[0]) / torso, (wp[1] - shoulder[1]) / torso];
        }
      }
      if (!Object.keys(current).length) { reset(); return null; }
      const before = previous, dt = (now - lastAt) / 1000;
      previous = current; lastAt = now;
      if (!before || dt < .04 || dt > .5) { movingFrames = 0; return null; }
      let speed = 0;
      for (const side of Object.keys(current)) {
        if (!before[side]) continue;
        speed = Math.max(speed, Math.hypot(current[side][0] - before[side][0], current[side][1] - before[side][1]) / dt);
      }
      movingFrames = speed >= .55 ? movingFrames + 1 : Math.max(0, movingFrames - 1);
      const extension = Math.max(...Object.values(current).map(v => Math.hypot(v[0], v[1])));
      if (movingFrames < 2 || extension < .45 || now - lastCandidateAt < 1000) return null;
      lastCandidateAt = now;
      const visible = L.filter(seen).length;
      return visible * 4 + Math.min(speed, 4) * 8 + Math.min(extension, 2) * 6;
    }
    return { update, reset };
  }
  const api = { createTracker };
  root.SCShotMotion = api;
  if (typeof module !== "undefined") module.exports = api;
})(typeof window === "undefined" ? globalThis : window);
