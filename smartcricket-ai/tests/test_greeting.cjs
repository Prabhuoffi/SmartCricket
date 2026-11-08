const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the shared function used by both Dashboard and Training without
// executing unrelated browser/session setup from the legacy global helper file.
const source = fs.readFileSync(path.join(__dirname, '../frontend/js/api.js'), 'utf8');
const declaration = source.match(/function greeting\([\s\S]*?\n}/)?.[0];
assert.ok(declaration, 'Shared greeting function must exist');
const greeting = vm.runInNewContext(`(${declaration})`, { Date });

test('greetings include a night period and switch at the exact local-hour boundaries', () => {
  const cases = [[0, 0, 'Good night'], [4, 59, 'Good night'], [5, 0, 'Good morning'],
    [11, 59, 'Good morning'], [12, 0, 'Good afternoon'], [16, 59, 'Good afternoon'],
    [17, 0, 'Good evening'], [20, 59, 'Good evening'], [21, 0, 'Good night'],
    [23, 5, 'Good night'], [23, 59, 'Good night']];
  for (const [hour, minute, expected] of cases) {
    assert.equal(greeting(new Date(2026, 10, 6, hour, minute)), expected, `${hour}:${minute}`);
  }
});

test('the browser local hour is used and the default clock is read on each call', () => {
  assert.equal(greeting({ getHours: () => 23, getUTCHours: () => 17 }), 'Good night');
  let hour = 20;
  const currentGreeting = vm.runInNewContext(`(${declaration})`, { Date: class { getHours() { return hour; } } });
  assert.equal(currentGreeting(), 'Good evening');
  hour = 21;
  assert.equal(currentGreeting(), 'Good night');
  hour = 5;
  assert.equal(currentGreeting(), 'Good morning');
});
