const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync(__dirname + '/index.html', 'utf8');

function fadeInProgram() {
  const start = html.indexOf('  // ── Fade in on scroll ──');
  const end = html.indexOf('\n})();', start);
  assert.notEqual(start, -1, 'fade-in program exists');
  assert.notEqual(end, -1, 'fade-in program has a closing IIFE');
  return html.slice(start, end);
}

function classList() {
  const values = new Set();
  return { add: value => values.add(value), has: value => values.has(value) };
}

function runFadeIn({ Observer, exposeObserver = true } = {}) {
  const elements = Array.from({ length: 3 }, () => ({ classList: classList() }));
  const root = { classList: classList() };
  const window = {};
  if (exposeObserver) window.IntersectionObserver = Observer;
  const context = { window, document: { querySelectorAll: () => elements, documentElement: root }, IntersectionObserver: Observer };
  vm.runInNewContext(`(function(){${fadeInProgram()}\n})();`, context);
  return { elements, root };
}

test('fade-in stays visible when IntersectionObserver is unavailable', () => {
  const { elements, root } = runFadeIn({ exposeObserver: false });
  assert.equal(root.classList.has('js'), false);
  assert.ok(elements.every(el => el.classList.has('visible')));
});

test('fade-in remains visible when observer construction or observe fails', () => {
  for (const Observer of [
    class { constructor() { throw new Error('unsupported'); } },
    class { observe() { throw new Error('observe failed'); } },
  ]) {
    const { elements, root } = runFadeIn({ Observer });
    assert.equal(root.classList.has('js'), false);
    assert.ok(elements.every(el => el.classList.has('visible')));
  }
});

test('fade-in enables hiding only after every observer registration succeeds and reveals intersections', () => {
  let callback;
  const observed = [];
  class Observer {
    constructor(next) { callback = next; }
    observe(element) { observed.push(element); }
    unobserve(element) { observed.splice(observed.indexOf(element), 1); }
  }
  const { elements, root } = runFadeIn({ Observer });
  assert.equal(root.classList.has('js'), true);
  assert.equal(observed.length, elements.length);
  callback([{ isIntersecting: true, target: elements[0] }]);
  assert.equal(elements[0].classList.has('visible'), true);
});

test('reduced motion overrides the JavaScript fade transition and displacement', () => {
  const reducedMotion = html.match(/@media \(prefers-reduced-motion: reduce\) \{\s*\.js \.fade-in \{([^}]+)\}/)?.[1];
  assert.ok(reducedMotion, 'reduced-motion fade-in rule exists');
  assert.match(reducedMotion, /opacity:\s*1/);
  assert.match(reducedMotion, /transform:\s*translateY\(0\)/);
  assert.match(reducedMotion, /transition:\s*none/);
});
