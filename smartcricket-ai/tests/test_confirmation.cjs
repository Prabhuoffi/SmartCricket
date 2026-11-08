const test = require('node:test');
const assert = require('node:assert/strict');
const { createActionState } = require('../frontend/js/confirmation.js');

test('cancel never calls the destructive action and prevents later submission', async () => {
  let calls = 0; const results = [];
  const state = createActionState({ action: async () => calls++, pending: () => {},
    error: assert.fail, finish: value => results.push(value) });
  assert.equal(state.cancel(), true);
  assert.equal(state.cancel(), false);
  assert.equal(await state.submit(), false);
  assert.equal(calls, 0);
  assert.deepEqual(results, [false]);
});

test('a pending deletion runs once and cannot be dismissed or submitted twice', async () => {
  let complete, calls = 0; const busy = [], results = [];
  const action = new Promise(resolve => { complete = resolve; });
  const state = createActionState({ action: () => { calls++; return action; },
    pending: value => busy.push(value), error: assert.fail, finish: value => results.push(value) });
  const first = state.submit();
  assert.equal(state.busy, true);
  assert.equal(await state.submit(), false);
  assert.equal(state.cancel(), false);
  assert.equal(calls, 1);
  assert.deepEqual(results, []);
  complete();
  assert.equal(await first, true);
  assert.equal(state.busy, false);
  assert.equal(await state.submit(), false);
  assert.deepEqual(results, [true]);
  assert.deepEqual(busy, [true]);
});

test('a failed deletion stays unresolved and can be retried successfully', async () => {
  let calls = 0; const busy = [], errors = [], results = [];
  const state = createActionState({ action: async () => { if (++calls === 1) throw new Error('Network unavailable'); },
    pending: value => busy.push(value), error: error => errors.push(error.message), finish: value => results.push(value) });
  assert.equal(await state.submit(), false);
  assert.equal(state.busy, false);
  assert.deepEqual(results, []);
  assert.deepEqual(errors, ['Network unavailable']);
  assert.deepEqual(busy, [true, false]);
  assert.equal(await state.submit(), true);
  assert.deepEqual(results, [true]);
  assert.equal(calls, 2);
});
