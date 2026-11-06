const { test } = require('node:test');
const assert = require('node:assert/strict');
const { metric, percent, decimal, chartPercent, bestF1 } = require('../frontend/js/models.js');

test('unavailable metrics remain missing in tables and charts instead of becoming zero', () => {
  for (const value of [null, undefined, NaN, Infinity, -1, 1.1, true, '0.8']) {
    assert.equal(metric(value), null);
    assert.equal(percent(value), '–');
    assert.equal(decimal(value), '–');
    assert.equal(chartPercent(value), null);
  }
  assert.equal(percent(0), '0.00%');
  assert.equal(decimal(0), '0.0000');
  assert.equal(chartPercent(.8), 80);
});

test('highest macro-F1 only uses measured finite scores and preserves the real percentages', () => {
  assert.equal(bestF1([]), null);
  assert.equal(bestF1([{ macro_f1: null }, {}]), null);
  assert.equal(bestF1([{ macro_f1: 0 }, { macro_f1: null }]), 0);
  assert.equal(bestF1([{ macro_f1: .47 }, { macro_f1: .6224 }, { macro_f1: NaN }]), .6224);
  assert.equal(percent(.6393), '63.93%');
});
