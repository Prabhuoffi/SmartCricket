const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalize, nextEnabled, placement } = require('../frontend/js/dropdown.js');

test('keyboard navigation skips disabled choices and handles empty or wholly disabled results', () => {
  const options = [{ disabled: true }, { disabled: false }, { disabled: true }, { disabled: false }];
  assert.equal(nextEnabled(options, -1, 1, false), 1);
  assert.equal(nextEnabled(options, options.length, -1, false), 3);
  assert.equal(nextEnabled(options, 1, 1, true), 3);
  assert.equal(nextEnabled(options, 3, 1, true), 1);
  assert.equal(nextEnabled(options, 1, -1, false), -1);
  assert.equal(nextEnabled([{ disabled: true }], 0, 1, true), -1);
  assert.equal(nextEnabled([], -1, 1, false), -1);
});

test('search ignores case, accent marks and extra spacing without changing displayed labels', () => {
  assert.equal(normalize('  Rétest\n  CAPTURE  '), 'retest capture');
  assert.equal(normalize('Front-foot drill #364'), 'front-foot drill #364');
  assert.equal(normalize(null), '');
});

test('popup fits a narrow viewport and flips above a trigger near the bottom', () => {
  const viewport = { width: 390, height: 844, left: 0, top: 0 };
  const below = placement({ left: 24, top: 150, bottom: 196, width: 342 }, viewport, 600);
  assert.deepEqual(below, { left: 24, top: 202, width: 342, height: 360, above: false });
  const above = placement({ left: 310, top: 700, bottom: 746, width: 450 }, viewport, 360);
  assert.deepEqual(above, { left: 12, top: 334, width: 366, height: 360, above: true });
});

test('popup uses the visible viewport when a mobile keyboard reduces its available height', () => {
  const viewport = { width: 390, height: 290, left: 0, top: 180 };
  const popup = placement({ left: 24, top: 360, bottom: 406, width: 342 }, viewport, 360);
  assert.equal(popup.above, true);
  assert.equal(popup.height, 162);
  assert.equal(popup.top, 192);
  assert.ok(popup.top >= viewport.top + 12);
  assert.ok(popup.top + popup.height <= viewport.top + viewport.height - 12);
});
