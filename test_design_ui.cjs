const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { initTabs, initMenu, initTheme } = require('./design-ui.js');
const html = fs.readFileSync(__dirname + '/index.html', 'utf8');
const css = fs.readFileSync(__dirname + '/design-refresh.css', 'utf8');

function element(initial = []) {
  const classes = new Set(initial);
  return {
    attrs: {}, handlers: {}, dataset: {}, style: {},
    classList: {
      contains: name => classes.has(name),
      toggle(name, value = !classes.has(name)) { value ? classes.add(name) : classes.delete(name); return value; },
    },
    setAttribute(key, value) { this.attrs[key] = value; },
    getAttribute(key) { return this.attrs[key]; },
    addEventListener(event, handler) { this.handlers[event] = handler; },
    focus() { this.focused = true; },
  };
}

for (const config of [
  { selector: '.tab-btn', key: 'tab', prefix: 'panel-', ids: ['us', 'tw', 'tech', 'metals', 'energy'] },
  { selector: '.etf-tab-btn', key: 'etfTab', prefix: 'etf-panel-', ids: ['us-etf', 'tw-etf'] },
]) test(config.selector + ' supports keyboard selection and accessible panel state', () => {
  const list = element();
  const panels = config.ids.map(() => element());
  const tabs = config.ids.map((id, i) => Object.assign(element(i === 0 ? ['active'] : []), {dataset: {[config.key]: id}, parentElement: list}));
  const section = {
    querySelectorAll: () => tabs,
    querySelector: selector => panels[config.ids.indexOf(selector.slice(config.prefix.length + 1))],
  };
  initTabs(section, config.selector, config.key, config.prefix, 'Markets');
  function selected(index) {
    tabs.forEach((tab, i) => {
      assert.equal(tab.attrs['aria-selected'], String(i === index));
      assert.equal(tab.tabIndex, i === index ? 0 : -1);
      assert.equal(panels[i].hidden, i !== index);
      assert.equal(panels[i].attrs['aria-labelledby'], tab.id);
    });
  }
  selected(0);
  const last = tabs.length - 1;
  tabs[last].handlers.click(); selected(last);
  function key(i, name) { tabs[i].handlers.keydown({key: name, preventDefault() {}}); }
  key(last, 'ArrowRight'); selected(0);
  key(0, 'ArrowLeft'); selected(last);
  key(last, 'Home'); selected(0);
  key(0, 'End'); selected(last);
  assert.equal(tabs[last].focused, true);
  assert.equal(list.attrs.role, 'tablist');
});

test('chapter menu closes with Escape, outside click, link selection and focus exit', () => {
  const menu = element(), button = element(), nav = element(), link = element(), doc = element();
  menu.querySelectorAll = () => [link];
  nav.contains = target => target === button || target === link;
  doc.getElementById = id => ({navLinks: menu, hamburger: button, navbar: nav})[id];
  initMenu(doc);
  const open = () => { button.handlers.click(); assert.equal(button.attrs['aria-expanded'], 'true'); };
  const closed = () => { assert.equal(button.attrs['aria-expanded'], 'false'); assert.equal(menu.classList.contains('open'), false); };
  open(); doc.handlers.keydown({key: 'Escape', preventDefault() {}}); closed();
  assert.equal(button.focused, true);
  open(); doc.handlers.click({target: {}}); closed();
  open(); link.handlers.click(); closed();
  open(); nav.handlers.focusout({relatedTarget: {}}); closed();
});

for (const blocked of [false, true]) test('theme and language remain usable with storage ' + (blocked ? 'blocked' : 'enabled'), () => {
  const button = element(), language = element(), meta = element();
  const doc = {body: element(['lang-zh']), documentElement: element(),
    getElementById: id => id === 'themeToggle' ? button : language, querySelector: () => meta};
  let stored = 'light';
  const win = {localStorage: {
    getItem() { if (blocked) throw new Error('blocked'); return stored; },
    setItem(key, value) { if (blocked) throw new Error('blocked'); stored = value; },
  }};
  initTheme(doc, win);
  assert.equal(doc.body.classList.contains('light-mode'), !blocked);
  button.handlers.click();
  assert.equal(doc.body.classList.contains('light-mode'), blocked);
  assert.equal(doc.documentElement.style.colorScheme, blocked ? 'light' : 'dark');
  doc.body.classList.toggle('lang-zh', false);
  language.handlers.click();
  assert.equal(doc.documentElement.lang, 'en');
  assert.match(button.attrs['aria-label'], /^Switch to/);
});

test('design keeps update anchors, chart containers, corrected author and honest newsletter status', () => {
  assert.match(html, /<main id="mainContent" tabindex="-1">/);
  assert.match(html, /Ke Lin &nbsp;\|&nbsp; 林格/);
  assert.doesNotMatch(html, /柯林|id="ctaForm"|已加入！/);
  for (const id of ['heroDate', 'protoTag', 'fear-greed-value', 'sp500-price', 'twii-price', 'gold-price', 'oil-price', 'freshnessTime']) {
    assert.equal((html.match(new RegExp('id="' + id + '"', 'g')) || []).length, 1, id);
  }
  assert.equal((html.match(/class="tw-etf-chart"/g) || []).length, 5);
  assert.equal((html.match(/class="market-price-chart"/g) || []).length, 23);
  assert.match(css, /\.reading-meta[\s\S]*color: var\(--text-secondary\)/);
  assert.match(css, /prefers-reduced-motion: reduce/);
  assert.doesNotMatch(html + css, /transition:\s*all\b/);
});

test('normal text, accent and data direction tokens meet 4.5:1 on both themes', () => {
  function luminance(hex) {
    const rgb = hex.match(/\w\w/g).map(x => parseInt(x, 16) / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4);
    return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
  }
  for (const [colors, backgrounds] of [
    [['edf2f7', 'aab8c9', 'dfb766', '66d3a1', 'ff8c99'], ['101c2e', '17263b', '132135']],
    [['17263b', '52647b', '805b20', '146d47', 'b72f46'], ['f3f6fa', 'ffffff', 'eaf0f6']],
  ]) for (const fg of colors) for (const bg of backgrounds) {
    const a = luminance(fg), b = luminance(bg);
    assert.ok((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5, `${fg} on ${bg}`);
  }
});
