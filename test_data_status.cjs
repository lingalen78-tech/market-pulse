const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/data-status.js', 'utf8');

function render(metadata, {en = false, state = 'current', date = '2026-11-05'} = {}) {
  const status = {dataset: {}};
  const asset = {dataset: {asOf: date, fetchState: state}};
  const time = {textContent: '2026-11-05 20:00 UTC'};
  const elements = {'freshnessStatus': status, 'market-data-status': {textContent: JSON.stringify(metadata)}, 'langToggle': {addEventListener() {}}, 'freshnessTime': time};
  vm.runInNewContext(source, {
    document: {body: {classList: {contains: () => en}}, getElementById: id => elements[id], querySelectorAll: () => [asset]},
    Date: {parse: Date.parse, now: () => Date.parse('2026-11-06T06:00:00Z')},
    setInterval() {}
  });
  assert.equal(time.textContent, '2026-11-05 20:00 UTC');
  return {status, asset};
}
const valid = {generated_at: '2026-11-05T20:00:00Z', core_dates: {SPY: '2026-11-05'}, failed: []};
test('current source timestamp stays unchanged', () => assert.equal(render(valid).status.dataset.state, 'current'));
test('old generation is stale even if bar dates look fresh', () => assert.equal(render({...valid, generated_at: '2026-10-01T00:00:00Z'}).status.dataset.state, 'stale'));
test('old source bars are stale even if generated today', () => assert.equal(render({...valid, core_dates: {SPY:'2026-10-01'}}).status.dataset.state, 'stale'));
test('missing dates are unknown', () => assert.equal(render({}).status.dataset.state, 'unknown'));
test('future generation is not shown as current', () => assert.equal(render({...valid, generated_at: '2026-11-07T06:00:00Z'}).status.dataset.state, 'unknown'));
test('impossible future exchange date is not shown as current', () => assert.equal(render({...valid, core_dates: {SPY: '2026-11-09'}}).status.dataset.state, 'unknown'));
test('retained source is visibly identified in English', () => {
  const result = render({...valid, failed: ['0050.TW']}, {en:true, state:'retained'});
  assert.equal(result.status.textContent, 'Partial refresh');
  assert.match(result.asset.textContent, /refresh failed/);
});
test('unavailable source is not called current', () => assert.match(render(valid, {state:'unavailable', date:''}).asset.textContent, /暫缺/));
