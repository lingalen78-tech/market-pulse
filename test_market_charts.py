import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import market_charts as charts
import update_market_data as m
from test_market_data import assets, history, NOW, TEMPLATE


class GlobalChartTests(unittest.TestCase):
    def test_all_chart_views_have_valid_unique_svg_and_source(self):
        data = assets()
        output = m.update_html(TEMPLATE, data, 40, NOW)
        m.validate_output(output, data, 40)
        self.assertEqual(output.count('class="market-price-chart"'), 23)
        for key, spec in charts.CHARTS.items():
            self.assertEqual(output.count(f'id="market-title-{key}"'), 1)
            self.assertIn(f'data-chart-key="{key}" data-chart-state="current"', output)
            self.assertNotIn(f'"{spec["tv"]}"', output)
        self.assertEqual(m.update_html(output, data, 40, NOW), output)

    def test_units_do_not_confuse_index_corn_or_treasury(self):
        data = assets()
        self.assertIn('US cents/bu', charts.render_chart('corn', data['ZC=F']))
        self.assertIn('price pts (not yield)', charts.render_chart('treasury', data['ZN=F']))
        self.assertIn('pts', charts.render_chart('ftse', data['^FTSE']))
        self.assertIn('Futures daily bars; rolls may cause gaps', charts.render_chart('wti', data['CL=F']))

    def test_flat_series_has_no_nan_or_infinity(self):
        data = assets()['^FTSE']
        data['price'] = 100
        for point in data['history']:
            point['close'] = 100
        output = charts.render_chart('ftse', data)
        self.assertIn('<svg', output)
        self.assertNotRegex(output, r'\b(?:nan|inf)\b')

    def test_invalid_cached_history_never_draws(self):
        original = assets()['^FTSE']
        for issue in ('nan', 'duplicate', 'date', 'price', 'short', 'pct'):
            data = copy.deepcopy(original)
            if issue == 'nan': data['history'][0]['close'] = float('nan')
            if issue == 'duplicate': data['history'][1]['date'] = data['history'][0]['date']
            if issue == 'date': data['as_of'] = '2026-11-04'
            if issue == 'price': data['price'] *= 2
            if issue == 'short': data['history'] = data['history'][-1:]
            if issue == 'pct': data['pct'] = float('nan')
            with self.subTest(issue=issue):
                output = charts.render_chart('ftse', data)
                self.assertNotIn('<svg', output)
                self.assertIn('data-chart-state="unavailable"', output)

    def test_missing_marker_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'marker pair'):
            charts.update_charts(TEMPLATE.replace('<!-- MARKET_CHART_ftse_START -->', ''), assets(), [])

    def test_optional_failure_preserves_curve_date_and_warning(self):
        data = assets()
        cached = copy.deepcopy(data['^FTSE'])
        data['^FTSE'] = None
        data['^HSI'] = None
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'index.html'
            snapshot = Path(temp) / 'data.json'
            index.write_text(TEMPLATE, encoding='utf-8')
            snapshot.write_text(json.dumps({'assets': {'^FTSE': cached}}), encoding='utf-8')
            with patch.object(m, 'fetch_all', return_value=data), patch.object(m, 'INDEX_HTML', str(index)), patch.object(m, 'SNAPSHOT_PATH', snapshot), patch.object(m, 'utc_now', return_value=NOW):
                m.main()
            saved = json.loads(snapshot.read_text(encoding='utf-8'))
            output = index.read_text(encoding='utf-8')
            self.assertEqual(saved['assets']['^FTSE'], cached)
            self.assertIn('data-chart-key="ftse" data-chart-state="retained"', output)
            self.assertIn('retained, refresh failed', output)
            self.assertIn('data-chart-key="hangseng" data-chart-state="unavailable"', output)

    def test_wrong_provider_identity_is_rejected(self):
        with patch.dict(m.SYMBOLS, {'^FTSE': 'FTSE'}, clear=True), patch.object(m.yf, 'Ticker') as ticker, patch.object(m, 'utc_now', return_value=NOW), patch.object(m.time, 'sleep'):
            ticker.return_value.history.return_value = history()
            ticker.return_value.history_metadata = {'symbol': '^FTSE', 'instrumentType': 'ETF'}
            self.assertIsNone(m.fetch_all()['^FTSE'])

    def test_futures_fetch_is_not_equity_adjusted(self):
        with patch.dict(m.SYMBOLS, {'ZC=F': 'Corn'}, clear=True), patch.object(m.yf, 'Ticker') as ticker, patch.object(m, 'utc_now', return_value=NOW):
            ticker.return_value.history.return_value = history()
            ticker.return_value.history_metadata = {'symbol': 'ZC=F', 'instrumentType': 'FUTURE', 'currency': 'USX'}
            result = m.fetch_all()['ZC=F']
            self.assertEqual(result['currency'], 'USX')
            self.assertFalse(ticker.return_value.history.call_args.kwargs['auto_adjust'])

    def test_wrong_corn_currency_is_rejected(self):
        with patch.dict(m.SYMBOLS, {'ZC=F': 'Corn'}, clear=True), patch.object(m.yf, 'Ticker') as ticker, patch.object(m, 'utc_now', return_value=NOW), patch.object(m.time, 'sleep'):
            ticker.return_value.history.return_value = history()
            ticker.return_value.history_metadata = {'symbol': 'ZC=F', 'instrumentType': 'FUTURE', 'currency': 'USD'}
            self.assertIsNone(m.fetch_all()['ZC=F'])


if __name__ == '__main__':
    unittest.main()
