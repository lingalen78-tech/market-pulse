"""Self-hosted daily charts for instruments unavailable in TradingView embeds."""
import datetime as dt
import html
import math
import re
from urllib.parse import quote


def chart(symbol, name, unit_zh, unit_en, kind='INDEX', sessions=22, tv=None):
    return dict(symbol=symbol, name=name, unit_zh=unit_zh, unit_en=unit_en,
                kind=kind, sessions=sessions, tv=tv)


CHARTS = {
    'ftse': chart('^FTSE', 'FTSE 100', '點', 'pts', tv='TVC:UKX'),
    'cac': chart('^FCHI', 'CAC 40', '點', 'pts', tv='TVC:CAC40'),
    'stoxx': chart('^STOXX50E', 'Euro Stoxx 50', '點', 'pts', tv='TVC:SX5E'),
    'smi': chart('^SSMI', 'SMI', '點', 'pts', tv='TVC:SMI'),
    'nikkei': chart('^N225', 'Nikkei 225', '點', 'pts', tv='TVC:NI225'),
    'hangseng': chart('^HSI', 'Hang Seng', '點', 'pts', tv='TVC:HSI'),
    'kospi': chart('^KS11', 'KOSPI', '點', 'pts', tv='TVC:KOSPI'),
    'sti': chart('^STI', 'Straits Times Index', '點', 'pts', tv='TVC:STI'),
    'nifty': chart('^NSEI', 'Nifty 50', '點', 'pts', tv='TVC:NIFTY'),
    'asx': chart('^AXJO', 'S&P/ASX 200', '點', 'pts', tv='TVC:AS51'),
    'es': chart('ES=F', 'S&P 500 E-mini Futures', '點', 'pts', 'FUTURE', tv='CME_MINI:ES1!'),
    'nq': chart('NQ=F', 'Nasdaq 100 E-mini Futures', '點', 'pts', 'FUTURE', tv='CME_MINI:NQ1!'),
    'wti': chart('CL=F', 'WTI Crude Oil Futures', '美元／桶', 'USD/bbl', 'FUTURE', tv='NYMEX:CL1!'),
    'gold': chart('GC=F', 'Gold Futures', '美元／盎司', 'USD/oz', 'FUTURE', tv='COMEX:GC1!'),
    'corn': chart('ZC=F', 'Corn Futures', '美分／英斗', 'US cents/bu', 'FUTURE', tv='CBOT:ZC1!'),
    'treasury': chart('ZN=F', '10-Year T-Note Futures', '價格點（非殖利率）', 'price pts (not yield)', 'FUTURE', tv='CBOT:ZN1!'),
    'taiex': chart('^TWII', 'TAIEX', '點', 'pts', sessions=66, tv='TVC:TWII'),
    'us-spy': chart('SPY', 'SPY ETF', '美元', 'USD', 'ETF', 66),
    'us-dow': chart('^DJI', 'Dow Jones', '點', 'pts', sessions=66),
    'us-nasdaq': chart('^IXIC', 'Nasdaq Composite', '點', 'pts', sessions=66),
    'energy-wti': chart('CL=F', 'WTI Futures', '美元／桶', 'USD/bbl', 'FUTURE', 66),
    'energy-brent': chart('BZ=F', 'Brent Futures', '美元／桶', 'USD/bbl', 'FUTURE', 66),
    'energy-gas': chart('NG=F', 'Natural Gas Futures', '美元／MMBtu', 'USD/MMBtu', 'FUTURE', 66),
}
SOURCE_SPECS = {c['symbol']: c for c in CHARTS.values()}
CHART_GROUPS = {'us': ('us-spy', 'us-dow', 'us-nasdaq'),
                'energy': ('energy-wti', 'energy-brent', 'energy-gas')}


def history_points(asset, limit):
    """Reject a corrupt cache instead of drawing a plausible but invalid curve."""
    if asset and not math.isfinite(asset['pct']):
        raise ValueError('Invalid daily change')
    points = []
    for item in (asset or {}).get('history', []):
        date = dt.date.fromisoformat(item['date'])
        value = float(item['close'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid chart close')
        if points and date <= points[-1][0]:
            raise ValueError('Chart dates must be increasing and unique')
        points.append((date, value))
    if len(points) < limit:
        raise ValueError(f'Chart requires {limit} valid sessions')
    if points[-1][0].isoformat() != asset['as_of']:
        raise ValueError('Chart and quote dates differ')
    if not math.isclose(points[-1][1], asset['price'], rel_tol=1e-6, abs_tol=0.0001):
        raise ValueError('Chart and quote prices differ')
    return points[-limit:]


def render_chart(key, asset, failed=False):
    spec = CHARTS[key]
    esc = html.escape
    source = f'https://finance.yahoo.com/quote/{quote(spec["symbol"], safe="")}/'
    state = 'retained' if failed and asset else 'current' if asset else 'unavailable'
    try:
        points = history_points(asset, spec['sessions'])
    except (ValueError, TypeError, KeyError):
        return (f'<div class="market-price-chart chart-unavailable" id="market-chart-{key}" data-chart-key="{key}" data-chart-state="unavailable">'
                '<p><span data-lang-zh>圖表資料暫缺，等待下次更新。</span><span data-lang-en>Chart unavailable; awaiting the next update.</span></p>'
                f'<a href="{source}" target="_blank" rel="noopener noreferrer">Yahoo Finance · {esc(spec["symbol"])}</a></div>')
    values = [p[1] for p in points]
    low, high = min(values), max(values)
    padding = max((high - low) * .08, abs(high) * .002, .01)
    bottom, top = low - padding, high + padding
    coords = [(i / (len(points) - 1) * 900, 180 - (v - bottom) / (top - bottom) * 180) for i, v in enumerate(values)]
    line = 'M ' + ' L '.join(f'{x:.2f},{y:.2f}' for x, y in coords)
    area = line + ' L 900,180 L 0,180 Z'
    start, end = points[0][0].isoformat(), points[-1][0].isoformat()
    pct = asset['pct']
    direction = 'up' if pct >= 0 else 'down'
    price = f'{asset["price"]:,.2f}'
    title = esc(f'{spec["name"]}; {start} to {end}; latest {price} {spec["unit_en"]}; daily change {pct:+.2f}%')
    retained = '<span data-lang-zh>· 沿用舊資料，本次抓取失敗</span><span data-lang-en>· retained, refresh failed</span>' if state == 'retained' else ''
    basis_zh = '期貨日線；合約切換可能跳空' if spec['kind'] == 'FUTURE' else '復權日線' if spec['kind'] == 'ETF' else '指數日線'
    basis_en = 'Futures daily bars; rolls may cause gaps' if spec['kind'] == 'FUTURE' else 'Adjusted daily bars' if spec['kind'] == 'ETF' else 'Index daily bars'
    return f'''<div class="market-price-chart" id="market-chart-{key}" data-chart-key="{key}" data-chart-state="{state}">
  <div class="market-price-summary"><strong>{price}</strong><span class="market-price-unit"><span data-lang-zh>{spec['unit_zh']}</span><span data-lang-en>{spec['unit_en']}</span></span><span class="market-price-change {direction}">1D {pct:+.2f}%</span></div>
  <svg viewBox="0 0 900 180" preserveAspectRatio="none" role="img" aria-labelledby="market-title-{key}"><title id="market-title-{key}">{title}</title><line class="market-price-grid" x1="0" y1="90" x2="900" y2="90"/><path class="market-price-area" d="{area}"/><path class="market-price-line" d="{line}"/></svg>
  <div class="market-price-range"><span>{start}</span><span>{end}</span></div>
  <p class="market-price-source"><a href="{source}" target="_blank" rel="noopener noreferrer">Yahoo Finance · {esc(spec['symbol'])}</a><br><span data-lang-zh>{len(points)} 個交易日 · 資料日期 {end}（非即時）</span><span data-lang-en>{len(points)} sessions · Bar date {end} (not live)</span><br><span data-lang-zh>{basis_zh}</span><span data-lang-en>{basis_en}</span><span class="asset-age" data-as-of="{end}" data-fetch-state="{state}">{retained}</span></p>
</div>'''


def update_charts(html_text, data, failed):
    for key, spec in CHARTS.items():
        start, end = f'<!-- MARKET_CHART_{key}_START -->', f'<!-- MARKET_CHART_{key}_END -->'
        markup = render_chart(key, data.get(spec['symbol']), spec['symbol'] in failed)
        html_text, count = re.subn(re.escape(start) + '.*?' + re.escape(end),
                                  lambda _: start + '\n' + markup + '\n' + end, html_text, flags=re.S)
        if count != 1:
            raise ValueError(f'Expected one market chart marker pair: {key}; found {count}')
    return html_text


def validate_charts(html_text, data):
    for key, spec in CHARTS.items():
        if html_text.count(f'id="market-chart-{key}"') != 1:
            raise ValueError(f'Missing or duplicate rendered market chart: {key}')
        if spec['tv'] and f'"{spec["tv"]}"' in html_text:
            raise ValueError(f'Restricted widget still present: {spec["tv"]}')
        if data.get(spec['symbol']):
            history_points(data[spec['symbol']], spec['sessions'])
            block = re.search(rf'<div class="market-price-chart" id="market-chart-{key}".*?<!-- MARKET_CHART_{key}_END -->', html_text, re.S)
            if not block or f'id="market-title-{key}"' not in block[0]:
                raise ValueError(f'Valid data has no rendered SVG: {key}')
