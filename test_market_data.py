"""Offline regression tests for the published market-data contract."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import update_market_data as m

NOW = dt.datetime(2026, 11, 5, 22, tzinfo=dt.timezone.utc)
TEMPLATE = Path(__file__).with_name('index.html').read_text(encoding='utf-8')


def history(count=220):
    dates = pd.bdate_range(end='2026-11-05', periods=count, tz='America/New_York')
    prices = np.linspace(100, 125, count) + np.sin(np.arange(count))
    return pd.DataFrame({'Close': prices, 'High': prices + 1, 'Low': prices - 1}, index=dates)


def assets():
    return {s: m.analyze_history(history(), s, NOW) for s in m.SYMBOLS}


class MarketDataTests(unittest.TestCase):
    def test_200_valid_bars_required(self):
        with self.assertRaisesRegex(ValueError, '200 required'):
            m.analyze_history(history(199), 'SPY', NOW)

    def test_bad_closes_are_removed(self):
        h = history()
        h.iloc[-1, 0] = np.nan
        h.iloc[-2, 0] = np.inf
        a = m.analyze_history(h, '0050.TW', NOW)
        self.assertEqual(a['as_of'], '2026-11-03')
        self.assertEqual(len(a['history']), 66)
        self.assertTrue(all(np.isfinite(x['close']) for x in a['history']))

    def test_stale_and_future_bars_rejected(self):
        for now in (NOW + dt.timedelta(days=10), NOW - dt.timedelta(days=1)):
            with self.assertRaisesRegex(ValueError, 'bar date'):
                m.analyze_history(history(), 'SPY', now)

    def test_flat_rsi_is_neutral(self):
        self.assertEqual(m.calculate_rsi(pd.Series([100.] * 220)), 50.)

    def test_retries_then_success(self):
        with patch.dict(m.SYMBOLS, {'SPY': 'SPY'}, clear=True), patch.object(m.yf, 'Ticker') as ticker, patch.object(m, 'utc_now', return_value=NOW), patch.object(m.time, 'sleep'):
            ticker.return_value.history.side_effect = [RuntimeError('timeout'), history()]
            ticker.return_value.history_metadata = {'symbol': 'SPY', 'instrumentType': 'ETF', 'currency': 'USD'}
            self.assertIsNotNone(m.fetch_all()['SPY'])
            self.assertEqual(ticker.return_value.history.call_count, 2)

    def test_retries_exhausted(self):
        with patch.dict(m.SYMBOLS, {'SPY': 'SPY'}, clear=True), patch.object(m.yf, 'Ticker') as ticker, patch.object(m.time, 'sleep'):
            ticker.return_value.history.side_effect = RuntimeError('timeout')
            self.assertIsNone(m.fetch_all()['SPY'])
            self.assertEqual(ticker.return_value.history.call_count, 3)

    def test_core_failure_does_not_write(self):
        data = assets()
        data['SPY'] = None
        with patch.object(m, 'fetch_all', return_value=data), patch.object(m, 'atomic_write') as write:
            with self.assertRaises(SystemExit):
                m.main()
            write.assert_not_called()

    def test_all_signal_cards_and_chart_dates(self):
        data = assets()
        html = m.update_html(TEMPLATE, data, 40, NOW)
        m.validate_output(html, data, 40)
        self.assertEqual(html.count('class="tw-etf-chart" role="img"'), 5)
        for ticker in m.ETF_SYMBOLS.values():
            for kind in ('trend', 'rsi', 'ma'):
                self.assertEqual(html.count(f'id="etf-{ticker}-{kind}"'), 1)
        self.assertIn('id="fear-greed-label-en" data-lang-en>Fear<', html)
        self.assertIn('Market Pulse sentiment 40/100 (Fear)', html)
        self.assertIn('"symbol": "AMEX:SPY"', html)
        self.assertNotIn('"SPX|1D"', html)
        self.assertNotIn('5,380', html)
        self.assertNotIn('proto.innerHTML', html)
        self.assertEqual(m.update_html(html, data, 40, NOW), html)

    def test_missing_target_aborts(self):
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            m.update_html(TEMPLATE.replace('id="etf-SPY-rsi"', 'id="wrong"'), assets(), 40, NOW)

    def test_optional_source_cache_and_first_failure(self):
        data = assets()
        cached = data['0050.TW'].copy()
        cached['as_of'] = '2026-10-20'
        data['0050.TW'] = None
        data['00929.TW'] = None
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'index.html'
            snapshot = Path(temp) / 'data.json'
            index.write_text(TEMPLATE, encoding='utf-8')
            snapshot.write_text(json.dumps({'assets': {'0050.TW': cached}}), encoding='utf-8')
            with patch.object(m, 'fetch_all', return_value=data), patch.object(m, 'INDEX_HTML', str(index)), patch.object(m, 'SNAPSHOT_PATH', snapshot), patch.object(m, 'utc_now', return_value=NOW):
                m.main()
            html = index.read_text(encoding='utf-8')
            saved = json.loads(snapshot.read_text(encoding='utf-8'))
            self.assertEqual(saved['assets']['0050.TW']['as_of'], '2026-10-20')
            self.assertIn('data-as-of="2026-10-20" data-fetch-state="retained"', html)
            self.assertIn('data-fetch-state="unavailable"', html)
            self.assertIn('Chart data unavailable', html)
            self.assertEqual(saved['failed'], ['0050.TW', '00929.TW'])


if __name__ == '__main__':
    unittest.main()
