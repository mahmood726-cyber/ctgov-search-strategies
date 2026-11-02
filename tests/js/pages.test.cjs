'use strict';
// Regression tests for the three browser pages (node --test tests/js/).
// Each page's own inline script is run in a Node vm with a minimal document and a stub fetch, and the page's
// own entry points are called. Both copies of each page (repository root and e156-submission/assets) are tested.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '..', '..');
const COPIES = ['', 'e156-submission/assets'];

function el(id) {
  return { id, value: '', innerHTML: '', textContent: '', disabled: false, style: {}, dataset: {}, scrollTop: 0,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    addEventListener() {}, setAttribute() {}, querySelectorAll() { return []; }, querySelector() { return null; }, appendChild() {} };
}
function load(rel, fetchImpl) {
  const html = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  const ids = new Set([...html.matchAll(/\bid\s*=\s*"([^"]+)"/g)].map((m) => m[1]));
  const els = new Map();
  const document = { getElementById(id) { if (!ids.has(id)) return null; if (!els.has(id)) els.set(id, el(id)); return els.get(id); },
    querySelectorAll() { return []; }, querySelector() { return null; }, addEventListener() {}, createElement: el, body: el('body') };
  const sb = { document, console: { log() {}, warn() {}, error() {} }, alert() {}, confirm: () => false,
    setTimeout: (f) => setImmediate(f), clearTimeout() {}, setInterval() { return 0; }, performance: { now: () => 0 },
    localStorage: { getItem() { return null; }, setItem() {} }, navigator: {}, location: { href: '' },
    loadPyodide: () => new Promise(() => {}), fetch: fetchImpl, Response, URL, encodeURIComponent };
  sb.window = sb; sb.addEventListener = () => {};
  const ctx = vm.createContext(sb);
  for (const m of html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/gi)) if (!/\bsrc=/.test(m[1])) vm.runInContext(m[2], ctx);
  return { ctx, document };
}
const study = (id, aliases) => ({ protocolSection: { identificationModule: { nctId: id, nctIdAliases: aliases || [], briefTitle: 't' + id } } });
const ok = (obj) => new Response(JSON.stringify(obj), { status: 200 });
// stub registry: NCT00000010 exists, NCT00000020 is an alias of NCT00000021, NCT00000030 only appears as another
// study's secondary ID (the lookup returns NCT00000031), NCT00000040 triggers HTTP 429, others: no study
function registry(url) {
  const id = (url.match(/query\.id=(NCT\d+)/) || [])[1];
  if (id === 'NCT00000040') return new Response('Too Many Requests', { status: 429 });
  if (id === 'NCT00000010') return ok({ studies: [study('NCT00000010')], totalCount: 1 });
  if (id === 'NCT00000020') return ok({ studies: [study('NCT00000021', ['NCT00000020'])], totalCount: 1 });
  if (id === 'NCT00000030') return ok({ studies: [study('NCT00000031')], totalCount: 1 });
  if (id) return ok({ studies: [], totalCount: 0 });
  return ok({ studies: [study('NCT00000099')], totalCount: 1234 });
}
const cards = (h) => Object.fromEntries([...h.matchAll(/class="value"[^>]*>([\s\S]*?)<\/div>\s*<div class="label">([\s\S]*?)<\/div>/g)]
  .map((m) => [m[2].replace(/<[^>]+>/g, '').trim(), m[1].replace(/<[^>]+>/g, '').trim()]));

for (const dir of COPIES) {
  const A = path.join(dir, 'CTGov-Search-Complete-JS.html');
  const B = path.join(dir, 'CTGov-Search-Complete.html');
  const C = path.join(dir, 'CTGov-Strategy-Tester-v3-TruthCert.html');

  test(`${A}: validation checks every ID, not the first 20`, async () => {
    const { ctx, document } = load(A, async (u) => registry(u));
    const ids = Array.from({ length: 25 }, (_, i) => 'NCT' + String(50000000 + i));
    document.getElementById('nctInput').value = ['NCT00000010', ...ids].join('\n');
    await ctx.validateNCTs();
    const c = cards(document.getElementById('validateSummary').innerHTML);
    assert.equal(c.Total, '26'); assert.equal(c.Found, '1'); assert.equal(c['API Recall'], '3.8%');
  });

  test(`${A}: found means this NCT number (or its alias); HTTP errors and malformed IDs stay out of the denominator`, async () => {
    const { ctx, document } = load(A, async (u) => registry(u));
    document.getElementById('nctInput').value = 'NCT00000010\nNCT00000020\nNCT00000030\nNCT00000040\nNCT00000050\nNCT1234567';
    await ctx.validateNCTs();
    const c = cards(document.getElementById('validateSummary').innerHTML);
    assert.equal(c.Total, '5'); assert.equal(c.Found, '2'); assert.equal(c.Errors, '1'); assert.equal(c.Refused, '1');
    assert.equal(c['API Recall'], '50.0%');                       // 2 of the 4 answered
    const t = document.getElementById('validateTable').innerHTML;
    assert.match(t, /NCT00000030<\/td><td>[^<]*<span[^>]*>Not Found/);
    assert.match(t, /NCT00000040<\/td><td>[^<]*<span[^>]*>Error/);
  });

  test(`${A}: Wilson interval uses z = qnorm(0.975)`, () => {
    const { ctx } = load(A, async (u) => registry(u));
    const [lo, hi] = ctx.wilsonCI(50, 100);
    assert.ok(Math.abs(lo - 0.4038315303659957) < 1e-12 && Math.abs(hi - 0.5961684696340044) < 1e-12, `${lo} ${hi}`);
  });

  test(`${A}: search filters build an accepted query and the total is requested`, async () => {
    const urls = []; const { ctx, document } = load(A, async (u) => { urls.push(u); return registry(u); });
    document.getElementById('ctCondition').value = 'asthma';
    document.getElementById('ctStudyType').value = 'INTERVENTIONAL';
    document.getElementById('ctStatus').value = '';
    document.getElementById('ctPhase').value = 'PHASE3,PHASE4';
    await ctx.searchCTGov();
    const u = decodeURIComponent(urls[0]);
    assert.ok(u.includes('query.term=AREA[StudyType]INTERVENTIONAL AND AREA[Phase](PHASE3 OR PHASE4)'), u);
    assert.ok(!u.includes('filter.overallStatus') && !u.includes('filter.phase'), u);
    assert.ok(u.includes('countTotal=true'), u);
    assert.equal(cards(document.getElementById('ctSummary').innerHTML)['Total Studies'], '1,234');
  });

  test(`${A}: metrics with an empty denominator are N/A, not 0`, () => {
    const { ctx, document } = load(A, async (u) => registry(u));
    for (const k of ['metricTP', 'metricFP', 'metricFN']) document.getElementById(k).value = '0';
    ctx.calculateMetrics();
    const c = cards(document.getElementById('metricsResult').innerHTML);
    assert.equal(c.Recall, 'N/A'); assert.equal(c.Precision, 'N/A'); assert.equal(c.F1, 'N/A');
  });

  test(`${B}: validation - errors not counted as Not Found, refused IDs reported, exact match`, async () => {
    const { ctx, document } = load(B, async (u) => registry(u));
    document.getElementById('nctInput').value = 'NCT00000010\nNCT00000020\nNCT00000030\nNCT00000040\nNCT1234567';
    await ctx.validateNCTs();
    const c = cards(document.getElementById('validationSummary').innerHTML);
    assert.equal(c['Total NCT IDs'], '4'); assert.equal(c.Valid, '2'); assert.equal(c['Not Found'], '1');
    assert.equal(c.Errors, '1'); assert.equal(c.Refused, '1'); assert.equal(c['Validation Rate'], '66.7%');
  });

  // The API returns a study for query.id=<NCT> whatever the other query/filter parameters say (checked live on
  // 2 Nov 2026: query.cond=asthma&query.id=NCT03315143 returns that diabetes trial), so '<strategy>&query.id=<NCT>'
  // cannot tell whether the strategy retrieves the trial. This stub behaves the same way.
  function strategyRegistry(u) {
    const url = decodeURIComponent(u);
    const inStrategy = new Set(url.includes('asthma') ? ['NCT00000010'] : []);
    const qid = (url.match(/query\.id=(NCT\d+)/) || [])[1];
    if (qid) return ok({ studies: [study(qid)], totalCount: 1 });
    const ids = ((url.match(/filter\.ids=([^&]+)/) || [])[1] || '').split(',').filter(Boolean);
    const hit = ids.filter((i) => inStrategy.has(i));
    return ok({ studies: hit.map((i) => study(i)), totalCount: hit.length });
  }

  test(`${C}: check recall uses all 10 strategies and every ID, and counts only trials the strategy retrieves`, async () => {
    const seen = []; const { ctx, document } = load(C, async (u) => { seen.push(u); return strategyRegistry(u); });
    document.getElementById('condition').value = 'asthma';
    document.getElementById('nct-input').value = ['NCT00000010', ...Array.from({ length: 11 }, (_, i) => 'NCT' + (60000000 + i))].join('\n');
    await ctx.checkRecall();
    const h = document.getElementById('recall-results').innerHTML;
    const rows = [...h.matchAll(/<tr><td>(S\d+):[^<]*<\/td><td>([^<]*)<\/td>/g)];
    assert.equal(rows.length, 10);
    for (const r of rows) assert.equal(r[2], '1/12');
  });

  test(`${C}: a trial the strategy does not retrieve is not counted as found`, async () => {
    const { ctx, document } = load(C, async (u) => strategyRegistry(u));
    document.getElementById('condition').value = 'type 2 diabetes';
    document.getElementById('nct-input').value = 'NCT00000010\nNCT00000011';
    await ctx.checkRecall();
    const h = document.getElementById('recall-results').innerHTML;
    const rows = [...h.matchAll(/<tr><td>(S\d+):[^<]*<\/td><td>([^<]*)<\/td>/g)];
    assert.equal(rows.length, 10);
    for (const r of rows) assert.equal(r[2], '0/2');
  });
}
