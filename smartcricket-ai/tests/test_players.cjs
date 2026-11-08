const test = require('node:test');
const assert = require('node:assert/strict');
const { visiblePlayers, captureBreakdown, activityStats } = require('../frontend/js/players.js');

test('roster search matches name or email and preserves the original player order', () => {
  const rows = [{ id: 1, name: 'Rohan Iyer', email: 'rohan@example.com', analyses: 3 },
    { id: 2, name: 'Meera', email: 'academy@example.com', analyses: 8 }];
  assert.deepEqual(visiblePlayers(rows, ' IYER ').map(p => p.id), [1]);
  assert.deepEqual(visiblePlayers(rows, 'academy').map(p => p.id), [2]);
  assert.deepEqual(visiblePlayers(rows, '', 'analyses').map(p => p.id), [2, 1]);
  assert.deepEqual(rows.map(p => p.id), [1, 2]);
});

test('streak and plan sorting keeps zero visible and unavailable values last in both directions', () => {
  const rows = [{ id: 1, name: 'No plan', plan_pct: null, streak: 0 },
    { id: 2, name: 'Partial', plan_pct: 40, streak: 2 },
    { id: 3, name: 'Complete', plan_pct: 100, streak: 8 }];
  assert.deepEqual(visiblePlayers(rows, '', 'plan_pct', 1).map(p => p.id), [2, 3, 1]);
  assert.deepEqual(visiblePlayers(rows, '', 'plan_pct', -1).map(p => p.id), [3, 2, 1]);
  assert.deepEqual(visiblePlayers(rows, '', 'streak', 1).map(p => p.id), [1, 2, 3]);
});

test('detail-sheet photo and video shares use capture counts and handle an empty account', () => {
  assert.deepEqual(captureBreakdown({ photos: 3, videos: 1 }),
    { photos: 3, videos: 1, total: 4, photo_share: 75, video_share: 25 });
  assert.deepEqual(captureBreakdown({ photos: null, videos: 0 }),
    { photos: 0, videos: 0, total: 0, photo_share: 0, video_share: 0 });
});

test('summary distinguishes recent practice, inactive accounts and unavailable plans', () => {
  const now = Date.parse('2026-11-06T16:00:00Z');
  const rows = [{ last_active: '2026-11-06T15:00:00Z', plan_pct: 80 },
    { last_active: '2026-10-25T15:00:00Z', plan_pct: null },
    { last_active: null, plan_pct: 0 }, { last_active: 'invalid', plan_pct: '100' }];
  assert.deepEqual(activityStats(rows, now), { total: 4, active: 1, on_plan: 1, inactive: 3 });
});
