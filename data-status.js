/* Display source age without ever changing the pipeline timestamp. */
(function () {
  'use strict';
  const status = document.getElementById('freshnessStatus');
  function updateAge() {
    const en = document.body.classList.contains('lang-en');
    try {
      const data = JSON.parse(document.getElementById('market-data-status').textContent);
      const generated = Date.parse(data.generated_at);
      const now = Date.now();
      const dates = Object.values(data.core_dates || {}).map(d => Date.parse(d + 'T00:00:00Z'));
      const unknown = !Number.isFinite(generated) || !dates.length || dates.some(d => !Number.isFinite(d));
      const stale = unknown || now - generated > 96 * 3600000 || now - Math.min(...dates) > 8 * 86400000;
      const partial = (data.failed || []).length > 0;
      status.textContent = unknown ? (en ? 'Date unavailable' : '日期暫缺') : stale ? (en ? 'Stale daily data' : '日線資料已過期') : partial ? (en ? 'Partial refresh' : '部分資料未更新') : (en ? 'Daily data' : '日線資料');
      status.dataset.state = unknown ? 'unknown' : stale ? 'stale' : partial ? 'partial' : 'current';
      document.querySelectorAll('.asset-age').forEach(el => {
        const date = Date.parse(el.dataset.asOf + 'T00:00:00Z');
        const retained = el.dataset.fetchState === 'retained';
        const missing = el.dataset.fetchState === 'unavailable' || !Number.isFinite(date);
        const old = stale || now - date > 8 * 86400000;
        el.textContent = missing ? (en ? '· unavailable' : '· 暫缺') : retained ? (en ? '· retained, refresh failed' : '· 沿用舊資料，本次抓取失敗') : old ? (en ? '· stale' : '· 已過期') : '';
      });
    } catch (_) {
      status.textContent = en ? 'Date unavailable' : '日期暫缺';
      status.dataset.state = 'unknown';
    }
  }
  updateAge();
  document.getElementById('langToggle').addEventListener('click', updateAge);
  setInterval(updateAge, 60000);
})();
