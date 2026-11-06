"""Behavior regressions for indicator math and the reader-facing data contract."""
import re
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from html.parser import HTMLParser
import pandas as pd
import update_market_data as m
from test_market_data import assets, NOW, TEMPLATE


class TextById(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.stack, self.values = [], {}
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        if tag not in ('br', 'meta', 'link', 'img', 'input', 'hr'):
            self.stack.append((tag, dict(attrs).get('id')))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, value):
        for _, eid in self.stack:
            if eid:
                self.values[eid] = self.values.get(eid, '') + value


class IntegrityTests(unittest.TestCase):
    def test_wilder_smoothing_uses_prior_average_not_rolling_window(self):
        # Seed gains/losses = 2/3, 1/3. After two updates: 26/27, 10/27.
        self.assertAlmostEqual(m.calculate_rsi(pd.Series([10., 11, 12, 11, 10, 12]), 3), 72.22222222)

    def test_rsi_insufficient_history_is_not_invented_neutral(self):
        with self.assertRaises(ValueError):
            m.calculate_rsi(pd.Series([10.] * 14))

    def test_rsi_extreme_and_flat_sequences(self):
        for seq, want in [(range(1, 40), 100.), (range(40, 1, -1), 0.), ([20.] * 40, 50.)]:
            self.assertEqual(m.calculate_rsi(pd.Series(seq)), want)

    def test_equal_moving_averages_are_neutral_not_bullish(self):
        _, _, signal = m.get_signals(dict(price=100, ma50=100, ma200=100, rsi=50))
        self.assertEqual(signal['cls'], 'neutral')

    def test_oversold_is_a_description_not_a_buy_direction(self):
        _, rsi, _ = m.get_signals(dict(price=80, ma50=100, ma200=110, rsi=20))
        self.assertEqual(rsi['cls'], 'neutral')
        self.assertIn('Oversold', rsi['en'])

    def test_sentiment_requires_all_three_inputs(self):
        with self.assertRaises(ValueError):
            m.calc_fear_greed({'SPY': dict(rsi=50, price=100, ma200=100)})

    def test_sentiment_equal_weights_and_clipping(self):
        # RSI=50 -> 50; VIX=25 -> 50; price 10% above SMA -> 100.
        self.assertEqual(m.calc_fear_greed({'SPY': dict(rsi=50, price=110, ma200=100), '^VIX': dict(price=25)}), 67)
        self.assertEqual(m.calc_fear_greed({'SPY': dict(rsi=100, price=200, ma200=100), '^VIX': dict(price=0)}), 100)

    def test_snapshot_change_identifies_daily_period(self):
        output = TextById(m.update_html(TEMPLATE, assets(), 40, NOW)).values
        for key in ('sp500-change', 'twii-change', 'gold-change', 'oil-change'):
            self.assertIn('1D', output[key])

    def test_sentiment_inputs_are_visible_and_from_same_snapshot(self):
        data = assets()
        data['^VIX']['price'] = 25.0
        output = TextById(m.update_html(TEMPLATE, data, 40, NOW)).values
        self.assertIn('sentiment-inputs', list(output))
        self.assertIn('25.00', output['sentiment-inputs'])
        self.assertIn('1/3', output['sentiment-inputs'])
        self.assertIn('2026-11-05', output['sentiment-inputs'])

    def test_taiwan_chart_reports_actual_window_not_calendar_three_months(self):
        chart = m.render_tw_etf_chart('0050', [{'date': '2026-07-31', 'close': 100}, {'date': '2026-11-06', 'close': 90}])
        self.assertIn('2026-07-31', chart)
        self.assertIn('2026-11-06', chart)
        self.assertIn('Window', chart)
        self.assertIn('-10.00%', chart)
        self.assertNotIn('3M ', chart)

    def test_generated_dashboard_values_do_not_retain_old_direction_arrows(self):
        data = assets()
        data['CL=F'].update(ma50=150, ma200=100)
        output = TextById(m.update_html(TEMPLATE, data, 40, NOW)).values
        self.assertNotIn('↓', output['panel-energy'])
        self.assertNotIn('▼', output['panel-energy'])

    def test_validation_blocks_uncomputed_directional_badges(self):
        data = assets()
        output = m.update_html(TEMPLATE, data, 40, NOW)
        with self.assertRaisesRegex(ValueError, 'uncomputed'):
            m.validate_output(output + '<span class="trend-badge bullish">Bullish</span>', data, 40)

    def test_old_simple_rsi_cache_is_not_published_as_wilder(self):
        data = assets()
        cached = dict(data['0050.TW'])
        cached.pop('rsi_method')
        data['0050.TW'] = None
        with tempfile.TemporaryDirectory() as temp:
            index, snapshot = Path(temp) / 'index.html', Path(temp) / 'data.json'
            index.write_text(TEMPLATE, encoding='utf-8')
            snapshot.write_text(json.dumps({'assets': {'0050.TW': cached}}), encoding='utf-8')
            with patch.object(m, 'fetch_all', return_value=data), patch.object(m, 'INDEX_HTML', str(index)), patch.object(m, 'SNAPSHOT_PATH', snapshot), patch.object(m, 'utc_now', return_value=NOW):
                m.main()
            self.assertIsNone(json.loads(snapshot.read_text(encoding='utf-8'))['assets']['0050.TW'])


if __name__ == '__main__':
    unittest.main()
