const test = require('node:test');
const assert = require('node:assert/strict');
const { initLocation } = require('./design-ui.js');

function link(href) {
  return {
    attrs: { href },
    getAttribute(name) { return this.attrs[name]; },
    setAttribute(name, value) { this.attrs[name] = value; },
    removeAttribute(name) { delete this.attrs[name]; },
  };
}

test('navigation current location follows the chapter being read', () => {
  const first = link('#snapshot');
  const second = link('#dashboard');
  const sections = { '#snapshot': { id: 'snapshot', offsetTop: 0 }, '#dashboard': { id: 'dashboard', offsetTop: 600 } };
  const doc = {
    querySelectorAll: () => [first, second],
    querySelector: selector => sections[selector],
  };
  const win = {
    scrollY: 0,
    handlers: {},
    addEventListener(event, handler) { this.handlers[event] = handler; },
  };

  initLocation(doc, win);
  assert.equal(first.attrs['aria-current'], 'location');
  assert.equal(second.attrs['aria-current'], undefined);

  win.scrollY = 650;
  win.handlers.scroll();
  assert.equal(first.attrs['aria-current'], undefined);
  assert.equal(second.attrs['aria-current'], 'location');
});
