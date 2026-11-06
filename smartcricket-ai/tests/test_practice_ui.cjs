const { test } = require('node:test');
const assert = require('node:assert/strict');
const { retestCandidates, measuredJoints, selectedFrame, queryFor, defaultFrame } = require('../frontend/js/practice.js');

const baseline = { id: 1, mode: 'image', created_at: '2026-11-04T10:00:00+00:00',
  angles: { left_knee: { deg: 145, visibility: .9 }, right_knee: { deg: 139, visibility: .4 }, left_elbow: { deg: null } } };

test('retests match mode, are distinct, and are at least as recent as baseline', () => {
  const history = [baseline, { ...baseline, id: 2, created_at: '2026-11-03T10:00:00+00:00' },
    { ...baseline, id: 3, mode: 'video' }, { ...baseline, id: 4, created_at: '2026-11-04T11:00:00+00:00' }];
  assert.deepEqual(retestCandidates(history, baseline).map(item => item.id), [4]);
  assert.deepEqual(retestCandidates(history, null), []);
});

test('joint choices exclude invisible, absent, non-finite and out-of-range values', () => {
  assert.deepEqual(measuredJoints(baseline, null), { left_knee: 145 });
  const clip = { mode: 'video', summary: { angles_seq: [{ left_knee: 0, right_knee: NaN, left_elbow: 181 }, { right_knee: 140 }] } };
  assert.deepEqual(measuredJoints(clip, 0), { left_knee: 0 });
  assert.deepEqual(measuredJoints(clip, 1), { right_knee: 140 });
  assert.deepEqual(measuredJoints(clip, 99), {});
  assert.deepEqual(measuredJoints({ ...baseline, summary: { detected: false } }, null), {});
  for (const visibility of [true, '1', 1.01, Infinity, NaN])
    assert.deepEqual(measuredJoints({ ...baseline, angles: { left_knee: { deg: 145, visibility } } }, null), {});
  assert.deepEqual(measuredJoints(baseline, null, .95), {});
});

test('video frames are entered one-based and validated instead of silently clamped', () => {
  const clip = { mode: 'video', summary: { frames: 15, key_frame: 9 } };
  assert.equal(selectedFrame(clip, '1'), 0);
  assert.equal(selectedFrame(clip, '15'), 14);
  assert.equal(defaultFrame(clip), 9);
  assert.equal(selectedFrame(baseline, ''), null);
  for (const invalid of ['0', '16', '1.5', '', 'x']) assert.throws(() => selectedFrame(clip, invalid));
});

test('comparison queries preserve zero-based frame zero and explicit setup confirmation', () => {
  const clip = { id: 2, mode: 'video' }, retest = { id: 3, mode: 'video' };
  const query = new URLSearchParams(queryFor(clip, retest, 0, 14, false, 6));
  assert.equal(query.get('baseline_frame'), '0');
  assert.equal(query.get('retest_frame'), '14');
  assert.equal(query.get('same_setup'), 'false');
  assert.equal(query.get('goal_id'), '6');
  assert.equal(new URLSearchParams(queryFor(baseline, { ...baseline, id: 2 }, null, null, true)).has('baseline_frame'), false);
});
