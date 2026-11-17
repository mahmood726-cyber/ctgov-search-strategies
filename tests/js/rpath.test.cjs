'use strict';
// R path on CTGov-Search-Complete-JS.html (both copies): the downloaded / WebR script carries the
// numbers the page computed from the current inputs at full precision, and impossible inputs give
// NOT CHECKED instead of a script.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ROOT = path.resolve(__dirname, '..', '..');
function el(id) {
  return { id, value: '', innerHTML: '', textContent: '', style: {}, setAttribute() {}, removeAttribute() {}, appendChild() {} };
}
function load(rel) {
  const html = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  const ids = new Set([...html.matchAll(/\bid\s*=\s*"([^"]+)"/g)].map((m) => m[1]));
  const els = new Map();
  const document = { getElementById(id) { if (!ids.has(id)) return null; if (!els.has(id)) els.set(id, el(id)); return els.get(id); },
    querySelectorAll() { return []; }, querySelector() { return null; }, addEventListener() {}, createElement: el, body: el('body') };
  const sb = { document, console: { log() {}, warn() {}, error() {} }, setTimeout: (f) => setImmediate(f), clearTimeout() {},
    setInterval() { return 0; }, localStorage: { getItem() { return null; }, setItem() {} }, navigator: {}, location: { href: '' },
    loadPyodide: () => new Promise(() => {}), fetch: async () => { throw new Error('offline'); }, URL, encodeURIComponent };
  sb.window = sb; sb.addEventListener = () => {};
  const ctx = vm.createContext(sb);
  for (const m of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/gi)) if (!/\bsrc=/.test(m[1])) vm.runInContext(m[2], ctx);
  return { ctx, document };
}
for (const dir of ['', 'e156-submission/assets']) {
  const A = path.join(dir, 'CTGov-Search-Complete-JS.html');
  test(`${A}: Wilson R script uses the current inputs and the page's own bounds`, () => {
    const { ctx, document } = load(A);
    document.getElementById('ciSuccesses').value = '37'; document.getElementById('ciTotal').value = '41';
    const b = ctx.rpathScript('ci');
    assert.ok(b.ok);
    const [lo, hi] = ctx.wilsonCI(37, 41);
    assert.ok(b.script.includes('x <- 37; n <- 41'));
    assert.ok(b.script.includes('lower = ' + String(lo) + ', upper = ' + String(hi)));
    assert.match(b.script, /prop\.test\(x, n, correct = FALSE\)/);
  });
  test(`${A}: successes > total gives NOT CHECKED, not a script`, () => {
    const { ctx, document } = load(A);
    document.getElementById('ciSuccesses').value = '9'; document.getElementById('ciTotal').value = '5';
    const b = ctx.rpathScript('ci');
    assert.equal(b.ok, false); assert.match(b.reason, /between 0 and total/);
  });
  test(`${A}: metrics R script carries N/A as NA`, () => {
    const { ctx, document } = load(A);
    document.getElementById('metricTP').value = '0'; document.getElementById('metricFP').value = '4'; document.getElementById('metricFN').value = '0';
    const b = ctx.rpathScript('metrics');
    assert.ok(b.ok);
    assert.ok(b.script.includes('page <- c(recall = NA, precision = 0, F1 = NA, NNS = NA)'), b.script);
  });
}
