const { test } = require('node:test');
const assert = require('node:assert/strict');
const { nextStep, hasMeasurements } = require('../frontend/js/journey.js');

const photo = { id: 12, mode: 'image', summary: { detected: true }, angles: { left_knee: { deg: 0 } } };
const state = values => ({ today: { checked_in: true, drills_total: 3, drills_done: 0, quiz_done: false, ...values } });

test('first session and failed captures lead to capture', () => {
  assert.equal(nextStep([], state({})).key, 'capture');
  assert.equal(nextStep([{ mode: 'image', summary: { detected: false } }], state({})).label, 'Retake a photo');
  assert.equal(hasMeasurements({ ...photo, angles: { left_knee: { deg: null } } }), false);
  assert.equal(hasMeasurements(photo), true);
  assert.equal(hasMeasurements({ mode: 'video', summary: { tracked_frames: 4 } }), true);
  assert.equal(hasMeasurements({ mode: 'video', summary: { tracked_frames: 0 } }), false);
});

test('recovery takes priority over capture and unfinished practice', () => {
  assert.equal(nextStep([], state({ rest_day: true })).key, 'recovery');
  assert.equal(nextStep([photo], state({ rest_day: true, drills_done: 1 })).key, 'recovery');
});

test('saved results progress through check-in, practice, quiz and review', () => {
  assert.equal(nextStep([photo], state({ checked_in: false })).key, 'checkin');
  assert.equal(nextStep([photo], state({ drills_total: 0 })).key, 'practice');
  assert.equal(nextStep([photo], state({ drills_done: 2 })).key, 'practice');
  assert.equal(nextStep([photo], state({ drills_done: 3 })).key, 'quiz');
  assert.equal(nextStep([photo], state({ drills_done: 3, quiz_done: true })).key, 'progress');
});

test('training failure preserves access to the latest usable report', () => {
  const result = nextStep([{ id: 99, mode: 'image', summary: {} }, photo], null);
  assert.equal(result.key, 'unavailable');
  assert.equal(result.href, 'analysis.html?id=12');
  assert.equal(nextStep([{ id: 13, mode: 'video', summary: { tracked_frames: 2 } }], null).href, 'clip.html?id=13');
});
