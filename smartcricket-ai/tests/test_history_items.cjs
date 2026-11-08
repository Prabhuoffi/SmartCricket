const { test } = require('node:test');
const assert = require('node:assert/strict');
const { combine, search } = require('../frontend/js/history-items.js');

test('live captures and analyses share one newest-first history', () => {
  const analyses = [{ id: 1, created_at: '2026-11-06T10:00:00Z', original_name: 'nets.mp4', mode: 'video' }];
  const sessions = [{ id: 2, created_at: '2026-11-07T10:00:00Z', title: 'Hook shadow practice', day: '2026-11-07' }];
  const items = combine(analyses, sessions);
  assert.deepEqual(items.map(item => item.kind), ['live', 'analysis']);
  assert.deepEqual(search(items, 'hook').map(item => item.kind), ['live']);
  assert.deepEqual(search(items, 'nets').map(item => item.kind), ['analysis']);
});
