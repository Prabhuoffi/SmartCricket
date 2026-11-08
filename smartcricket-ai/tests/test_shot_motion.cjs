const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createTracker } = require('../frontend/js/shot-motion.js');

const seen = point => point?.visibility >= .65;
function pose(wristX) {
  const points = Array.from({ length: 33 }, () => ({ x: 0, y: 0, visibility: 0 }));
  for (const [id, x, y] of [[11, .3, .2], [12, .7, .2], [23, .3, .6], [24, .7, .6],
                           [15, wristX, .4], [16, wristX + .4, .4]]) {
    points[id] = { x, y, visibility: 1 };
  }
  return points;
}

test('still poses do not capture; sustained arm movement does', () => {
  const tracker = createTracker();
  assert.equal(tracker.update(pose(.3), 100, 100, 0, seen), null);
  for (let i = 1; i <= 5; i++) {
    assert.equal(tracker.update(pose(.3 + .002 * i), 100, 100, i * 100, seen), null);
  }
  assert.equal(tracker.update(pose(.4), 100, 100, 600, seen), null);
  assert.ok(tracker.update(pose(.5), 100, 100, 700, seen) > 0);
  assert.equal(tracker.update(pose(.6), 100, 100, 800, seen), null);
});

test('losing the body resets motion continuity', () => {
  const tracker = createTracker();
  tracker.update(pose(.3), 100, 100, 0, seen);
  assert.equal(tracker.update(pose(.4), 100, 100, 100, seen), null);
  const lost = pose(.5);
  lost[11].visibility = 0;
  assert.equal(tracker.update(lost, 100, 100, 200, seen), null);
  assert.equal(tracker.update(pose(.6), 100, 100, 300, seen), null);
});
