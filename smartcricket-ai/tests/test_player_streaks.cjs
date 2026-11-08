const test = require('node:test');
const assert = require('node:assert/strict');
const { presentation } = require('../frontend/js/player-streaks.js');

test('zero streaks remain visible alongside an earlier personal best', () => {
  assert.deepEqual(presentation({ streak: 0, best_streak: 12 }), {
    current: '0 days', best: 'Best: 12 days', active: false,
  });
  assert.equal(presentation({ streak: 1, best_streak: 1 }).current, '1 day');
  assert.equal(presentation({ streak: 7, best_streak: 9 }).active, true);
});

test('unavailable streaks are distinct from no recorded practice', () => {
  assert.deepEqual(presentation({}), { current: 'Unavailable', best: '', active: false });
  assert.equal(presentation({ streak: 0, best_streak: 0 }).best, 'No practice yet');
  for (const invalid of [null, '8', -1, NaN, Infinity, 1.5]) {
    assert.equal(presentation({ streak: invalid }).current, 'Unavailable');
  }
});
