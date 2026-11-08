const { test } = require('node:test');
const assert = require('node:assert/strict');
const guides = require('../frontend/shot-guides.json');
const { match, frame } = require('../frontend/js/shot-guide.js');

test('spoken front foot and hook questions select the intended guide', () => {
  assert.equal(match('How do I play a front foot shot?', guides)?.name, 'Front foot drive');
  assert.equal(match('Show me the hook shot', guides)?.name, 'Hook shot');
  assert.equal(match('Teach me a reverse sweep', guides)?.name, 'Reverse sweep');
  assert.equal(match('stop the camera', guides), null);
});

test('every named guide has three steps and an action frame', () => {
  for (const guide of guides) {
    assert.equal(guide.steps.length, 3, guide.name);
    assert.ok(frame(guide.family, 1).includes('<svg'), guide.name);
  }
});

test('all model shot names have an illustrated guide', () => {
  const shots = ['Cover Drive', 'Defensive', 'Down The Wicket', 'Flick', 'Hook',
    'Late Cut', 'Lofted Legside', 'Lofted Offside', 'Pull', 'Reverse Sweep',
    'Scoop', 'Square Cut', 'Straight Drive', 'Sweep', 'Upper Cut', 'Slog Sweep',
    'Paddle Sweep', 'Switch Hit', 'Leg Glance', 'Leave'];
  for (const shot of shots) assert.ok(match(shot, guides), shot);
});
