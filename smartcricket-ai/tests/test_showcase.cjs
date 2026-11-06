const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const demo = require('../frontend/js/showcase.js');
const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, '../frontend/data/showcase.json'), 'utf8'));
const copy = value => JSON.parse(JSON.stringify(value));

test('bundled scenarios are explicitly synthetic and contain no evaluation metrics', () => {
  assert.equal(demo.validateFixture(fixture), fixture);
  assert.equal(fixture.scenarios.length, 10);
  assert.equal(fixture.scenarios.flatMap(s => s.sessions).length, 140);
  for (const scenario of fixture.scenarios) {
    assert.equal(scenario.synthetic, true);
    assert.match(scenario.provenance, /SYNTHETIC/);
    assert.equal(scenario.sessions.length, 14);
  }
  assert.doesNotMatch(JSON.stringify(fixture), /"(?:accuracy|macro_f1|top1|top3|confidence|ece_after)"/);
  const unlabeled = copy(fixture);
  unlabeled.scenarios[0].synthetic = false;
  assert.throws(() => demo.validateFixture(unlabeled), /provenance/);
});

test('signed deltas and target distances describe the selected fictional values exactly', () => {
  const result = demo.comparison(fixture.scenarios[0]);
  assert.equal(result.shared.length, 8);
  assert.equal(result.exploratory, false);
  assert.deepEqual(result.shared.find(r => r.joint === 'left_knee'),
    { joint: 'left_knee', baseline_deg: 148, retest_deg: 141, change_deg: -7 });
  assert.deepEqual(result.target, { joint: 'left_knee', target_deg: 140, baseline_distance_deg: 8, retest_distance_deg: 1 });
  const farther = demo.comparison(fixture.scenarios[1]);
  assert.equal(farther.target.retest_distance_deg, 15);
  assert.equal(farther.shared.find(r => r.joint === 'left_knee').change_deg, 7);
});

test('capture mismatch retains descriptive numbers and makes comparison exploratory', () => {
  const result = demo.comparison(fixture.scenarios[2]);
  assert.equal(result.shared.length, 8);
  assert.equal(result.exploratory, true);
  assert.match(result.warnings.join(' '), /Camera view/);
  assert.match(result.warnings.join(' '), /Movement phase/);
  assert.match(result.warnings.join(' '), /not confirmed/);
});

test('low visibility and missing or invalid angles are excluded rather than filled in', () => {
  const result = demo.comparison(fixture.scenarios[3]);
  assert.equal(result.shared.length, 2);
  assert.equal(result.excluded.length, 6);
  assert.equal(result.target, null);
  assert.equal(result.exploratory, true);
  for (const value of [null, {}, { deg: null, visibility: 1 }, { deg: -1, visibility: 1 },
    { deg: 181, visibility: 1 }, { deg: Infinity, visibility: 1 }, { deg: 90, visibility: NaN },
    { deg: 90, visibility: 1.1 }, { deg: 90, visibility: .49 }, { deg: 90 }]) {
    assert.equal(demo.measurement(value).valid, false);
  }
  assert.equal(demo.measurement({ deg: 0, visibility: .5 }).valid, true);
  assert.equal(demo.measurement({ deg: 180, visibility: 1 }).valid, true);
});

test('activity uses completed planned drills with no invented rest-day penalty', () => {
  const sessions = [
    { check_in: 'Ready', planned: 3, completed: 2 },
    { check_in: 'Rest', planned: 0, completed: 0 },
    { check_in: 'Ready', planned: 3, completed: 3 },
  ];
  assert.deepEqual(demo.activity(sessions), { days: 3, rest_days: 1, planned_drills: 6, completed_drills: 5, adherence_pct: 83.3 });
  assert.equal(demo.activity([sessions[1]]).adherence_pct, null);
  assert.throws(() => demo.activity([{ check_in: 'Rest', planned: 3, completed: 0 }]), /Invalid/);
  assert.throws(() => demo.activity([{ check_in: 'Ready', planned: 2, completed: 3 }]), /Invalid/);
  const recovery = demo.comparison(fixture.scenarios[4]);
  assert.equal(recovery.target, null);
  assert.equal(demo.activity(fixture.scenarios[4].sessions).rest_days, 5);
});

test('JSON and every CSV record preserve synthetic provenance and interpretation', () => {
  const scenario = fixture.scenarios[0];
  const exported = demo.report(scenario);
  assert.equal(exported.synthetic, true);
  assert.match(exported.provenance, /SYNTHETIC/);
  assert.match(exported.interpretation, /do not establish better technique/);
  const csv = demo.csv(scenario);
  const lines = csv.trim().split('\r\n');
  for (const line of lines.slice(1)) {
    assert.ok(line.startsWith('"true","SYNTHETIC DEMONSTRATION DATA'));
  }
  assert.match(csv, /"148","141","-7"/);
  assert.match(csv, /"goal"/);
  assert.match(csv, /"activity_total"/);
  assert.throws(() => demo.report({ ...scenario, synthetic: false }), /Only labeled synthetic/);
});

test('CSV escapes quotes and text formulas without changing signed numeric deltas', () => {
  const scenario = copy(fixture.scenarios[0]);
  scenario.title = '=HYPERLINK("example")';
  scenario.goal.title = 'Comma, quote " and newline\ntext';
  const csv = demo.csv(scenario);
  assert.ok(csv.includes('"\'=HYPERLINK(""example"")"'));
  assert.ok(csv.includes('"Comma, quote "" and newline\ntext"'));
  assert.ok(csv.includes('"-7"'));
});

test('expanded scenarios keep joint choice, rest, unchanged values and phase context distinct', () => {
  const scenario = id => fixture.scenarios.find(s => s.id === id);
  const left = demo.comparison(scenario('left-handed-focus'));
  assert.equal(left.target.joint, 'right_knee');
  assert.equal(left.target.retest_distance_deg, 1);
  const rest = demo.activity(scenario('all-rest').sessions);
  assert.equal(rest.rest_days, 14);
  assert.equal(rest.adherence_pct, null);
  assert.equal(rest.planned_drills, 0);
  assert.ok(demo.comparison(scenario('unchanged-measurements')).shared.every(row => row.change_deg === 0));
  const video = scenario('video-frames');
  assert.equal(video.baseline.mode, 'video');
  assert.notEqual(video.baseline.selected_frame, video.retest.selected_frame);
  assert.equal(demo.comparison(video).exploratory, false);
  assert.match(demo.comparison(scenario('different-shot')).warnings.join(' '), /Stated shot/);
});
