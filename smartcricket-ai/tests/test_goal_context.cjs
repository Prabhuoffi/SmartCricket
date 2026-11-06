const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../frontend/js/goal-context.js'), 'utf8');

function setup(search, goals = []) {
  let banner;
  const context = {
    location: { search, reload() {} }, URLSearchParams,
    document: {
      createElement: () => ({ style: {}, setAttribute() {}, innerHTML: '', querySelector: () => ({}) }),
      querySelector: () => ({ after(element) { banner = element; } }),
    },
    api: async () => ({ goals }), esc: String, icon: () => '',
    prettyJoint: value => value.replaceAll('_', ' '), fmtDay: value => value,
    alertHtml: (_, message) => message,
    resultPage: capture => `${capture.mode === 'video' ? 'clip' : 'analysis'}.html?id=${capture.id}`,
  };
  vm.runInNewContext(source, context);
  return { flow: context.PracticeGoalFlow, banner: () => banner };
}

const goal = { id: 4, title: 'Consistent stance', focus_joint: 'left_knee', target_deg: 140,
  baseline: { id: 1, mode: 'image', created_at: '2026-11-04' } };

test('normal captures keep the existing result route', async () => {
  const { flow, banner } = setup('');
  assert.equal((await flow.load('image')).blocked, false);
  assert.equal(banner(), undefined);
  assert.equal(flow.resultUrl({ id: 9, mode: 'video' }, null), 'clip.html?id=9');
});

test('a goal survives the training to retest redirect with selected capture', async () => {
  const { flow, banner } = setup('?goal=4', [goal]);
  const result = await flow.load('image');
  assert.equal(result.blocked, false);
  assert.equal(result.goal.id, 4);
  assert.match(banner().innerHTML, /Consistent stance/);
  assert.equal(flow.resultUrl({ id: 9, mode: 'image' }, result.goal), 'practice.html?goal=4&retest=9');
});

test('invalid, missing and deleted baseline goals cannot silently lose the goal context', async () => {
  for (const [search, goals] of [['?goal=bad', [goal]], ['?goal=4', []], ['?goal=4', [{ ...goal, baseline: null }]]]) {
    const { flow, banner } = setup(search, goals);
    assert.equal((await flow.load('image')).blocked, true);
    assert.match(banner().innerHTML, /Capture without a goal/);
  }
});

test('photo and video retests must use the baseline capture type', async () => {
  const { flow, banner } = setup('?goal=4', [goal]);
  assert.equal((await flow.load('video')).blocked, true);
  assert.match(banner().innerHTML, /image.html\?goal=4/);
});
