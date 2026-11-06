/* Progressive UI enhancements. No requests, tracking, or data mutations. */
(function () {
  'use strict';
  function initTabs(section, buttonSelector, dataKey, panelPrefix, label) {
    if (!section) return;
    const tabs = Array.from(section.querySelectorAll(buttonSelector));
    if (!tabs.length) return;
    const list = tabs[0].parentElement;
    list.setAttribute('role', 'tablist');
    list.setAttribute('aria-label', label);
    function select(tab, focus) {
      tabs.forEach(button => {
        const selected = button === tab;
        const panel = section.querySelector('#' + panelPrefix + button.dataset[dataKey]);
        button.classList.toggle('active', selected);
        button.setAttribute('aria-selected', String(selected));
        button.tabIndex = selected ? 0 : -1;
        panel.classList.toggle('active', selected);
        panel.hidden = !selected;
      });
      if (focus) tab.focus();
    }
    tabs.forEach((tab, index) => {
      const panelId = panelPrefix + tab.dataset[dataKey];
      const panel = section.querySelector('#' + panelId);
      tab.id = 'ui-tab-' + tab.dataset[dataKey];
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', panelId);
      panel.setAttribute('role', 'tabpanel');
      panel.setAttribute('aria-labelledby', tab.id);
      panel.tabIndex = 0;
      tab.addEventListener('click', () => select(tab, false));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next !== undefined) { event.preventDefault(); select(tabs[next], true); }
      });
    });
    select(tabs.find(tab => tab.classList.contains('active')) || tabs[0], false);
  }

  function initMenu(doc) {
    const menu = doc.getElementById('navLinks');
    const button = doc.getElementById('hamburger');
    const nav = doc.getElementById('navbar');
    function setOpen(open, restoreFocus = false) {
      menu.classList.toggle('open', open);
      button.setAttribute('aria-expanded', String(open));
      if (restoreFocus) button.focus();
    }
    button.addEventListener('click', () => setOpen(!menu.classList.contains('open')));
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setOpen(false)));
    doc.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.classList.contains('open')) {
        event.preventDefault(); setOpen(false, true);
      }
    });
    doc.addEventListener('click', event => { if (!nav.contains(event.target)) setOpen(false); });
    nav.addEventListener('focusout', event => { if (event.relatedTarget && !nav.contains(event.relatedTarget)) setOpen(false); });
  }

  function initTheme(doc, win) {
    const button = doc.getElementById('themeToggle');
    const language = doc.getElementById('langToggle');
    let saved;
    try { saved = win.localStorage.getItem('mp-theme'); } catch (_) { /* Storage may be disabled. */ }
    function sync() {
      const light = doc.body.classList.contains('light-mode');
      const zh = doc.body.classList.contains('lang-zh');
      const label = zh ? (light ? '切換到深色主題' : '切換到淺色主題') : (light ? 'Switch to dark theme' : 'Switch to light theme');
      doc.documentElement.lang = zh ? 'zh-Hant' : 'en';
      doc.documentElement.style.colorScheme = light ? 'light' : 'dark';
      doc.querySelector('meta[name="theme-color"]').setAttribute('content', light ? '#f3f6fa' : '#101c2e');
      button.textContent = light ? '☾' : '☀';
      button.setAttribute('aria-label', label);
      button.title = label;
      language.setAttribute('aria-label', zh ? 'Switch to English' : '切換到繁體中文');
    }
    doc.body.classList.toggle('light-mode', saved === 'light');
    sync();
    language.addEventListener('click', sync);
    button.addEventListener('click', () => {
      const light = doc.body.classList.toggle('light-mode');
      try { win.localStorage.setItem('mp-theme', light ? 'light' : 'dark'); } catch (_) { /* The toggle still works. */ }
      sync();
    });
  }

  function init(doc, win) {
    initMenu(doc);
    initTheme(doc, win);
    initTabs(doc.getElementById('dashboard'), '.tab-btn', 'tab', 'panel-', '資產分類 / Asset classes');
    initTabs(doc.getElementById('etf'), '.etf-tab-btn', 'etfTab', 'etf-panel-', 'ETF 市場 / ETF markets');
    const charts = doc.querySelectorAll('.tradingview-widget-container, .market-price-chart, .tw-etf-chart').length;
    ['chartCount', 'chartCountEn'].forEach(id => { doc.getElementById(id).textContent = charts; });
    const sections = doc.querySelectorAll('main section[id]:not(#hero)').length;
    ['sectionCount', 'sectionCountEn'].forEach(id => { doc.getElementById(id).textContent = sections; });
    const links = doc.querySelectorAll('.navbar a[href^="#"]');
    function syncLocation() {
      links.forEach(link => {
        if (link.getAttribute('href') === win.location.hash) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }
    win.addEventListener('hashchange', syncLocation);
    syncLocation();
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { initTabs, initMenu, initTheme };
  else init(document, window);
})();
