#!/usr/bin/env python3
"""
Market Pulse - Daily Data Update Script
Fetches real market data from Yahoo Finance (yfinance) and updates index.html.
Run from the repo root: python update_market_data.py
"""

import re
import sys
import datetime
import json
import os
import time
from pathlib import Path
import numpy as np
import yfinance as yf
from market_charts import SOURCE_SPECS, history_points, update_charts, validate_charts

INDEX_HTML = "index.html"

SYMBOLS = {
    "SPY":   "S&P 500 ETF",
    "^IXIC": "Nasdaq",
    "^DJI":  "Dow Jones",
    "^TWII": "Taiwan Index",
    "GC=F":  "Gold",
    "CL=F":  "Crude Oil",
    "SI=F":  "Silver",
    "NG=F":  "Natural Gas",
    "AAPL":  "Apple",
    "NVDA":  "NVIDIA",
    "TSM":   "TSMC ADR",
    "MSFT":  "Microsoft",
    "GOOGL": "Alphabet",
    "^VIX":  "VIX",
    "IVV": "iShares Core S&P 500 ETF",
    "VOO": "Vanguard S&P 500 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "QQQ": "Invesco Nasdaq 100 ETF",
    "0050.TW": "Yuanta Taiwan Top 50 ETF",
    "0056.TW": "Yuanta Taiwan High Dividend ETF",
    "00878.TW": "Cathay MSCI Taiwan ESG Sustainability High Dividend ETF",
    "00919.TW": "Capital TIP Taiwan Select High Dividend ETF",
    "00929.TW": "Fuh Hwa Taiwan Technology Dividend Highlight ETF",
}

TW_ETFS = {
    "0050.TW": "0050",
    "0056.TW": "0056",
    "00878.TW": "00878",
    "00919.TW": "00919",
    "00929.TW": "00929",
}

SYMBOLS.update({symbol: spec['name'] for symbol, spec in SOURCE_SPECS.items()})

ETF_SYMBOLS = {**{s: s for s in ("SPY", "IVV", "VOO", "VTI", "QQQ")}, **TW_ETFS}
CORE_SYMBOLS = {"SPY", "^TWII", "GC=F", "CL=F", "^VIX"}
SNAPSHOT_PATH = Path("data/market-data.json")
MAX_ATTEMPTS = 3


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def analyze_history(hist, symbol, now=None):
    now = now or utc_now()
    hist = hist.sort_index()
    hist = hist[~hist.index.duplicated(keep="last")]
    hist = hist[np.isfinite(hist["Close"]) & (hist["Close"] > 0)]
    if len(hist) < 200:
        raise ValueError(f"only {len(hist)} valid sessions; 200 required")
    close = hist["Close"]
    as_of = close.index[-1].date()
    # Use the exchange's calendar date (not the runner's local timezone).
    exchange_today = now.astimezone(hist.index.tz).date() if hist.index.tz else now.date()
    if not 0 <= (exchange_today - as_of).days <= 7:
        raise ValueError(f"invalid or stale bar date: {as_of}")
    tail = hist.tail(20)
    asset = dict(
        name=SYMBOLS[symbol], price=float(close.iloc[-1]),
        pct=float((close.iloc[-1] / close.iloc[-2] - 1) * 100),
        rsi=calculate_rsi(close), ma50=float(close.tail(50).mean()),
        ma200=float(close.tail(200).mean()), support=float(tail["Low"].min()),
        resistance=float(tail["High"].max()), as_of=as_of.isoformat(),
        fetched_at=now.isoformat(),
        history=[{"date": stamp.date().isoformat(), "close": round(float(v), 4)}
                 for stamp, v in close.tail(66).items()] if symbol in TW_ETFS or symbol in SOURCE_SPECS else [],
    )
    if not all(np.isfinite(asset[k]) for k in
               ("price", "pct", "rsi", "ma50", "ma200", "support", "resistance")):
        raise ValueError("non-finite indicator")
    return asset

# ── Data fetching ─────────────────────────────────────────────────────────────

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if not (np.isnan(val) or np.isinf(val)) else 50.0


def fetch_all():
    """Fetch OHLCV + indicators for all symbols. Returns dict keyed by symbol."""
    print("Fetching market data from Yahoo Finance...")
    result = {}
    for symbol in SYMBOLS:
        result[symbol] = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                ticker = yf.Ticker(symbol)
                spec = SOURCE_SPECS.get(symbol)
                adjusted = not spec or spec['kind'] == 'ETF'
                hist = ticker.history(period="2y", auto_adjust=adjusted, timeout=15)
                asset = analyze_history(hist, symbol)
                if spec:
                    meta = ticker.history_metadata
                    if meta.get('symbol') != symbol or meta.get('instrumentType') != spec['kind']:
                        raise ValueError(f"Unexpected source identity for {symbol}")
                    expected_currency = 'USX' if symbol == 'ZC=F' else 'USD' if spec['kind'] in ('FUTURE', 'ETF') else None
                    if expected_currency and meta.get('currency') != expected_currency:
                        raise ValueError(f"Unexpected quote currency for {symbol}: {meta.get('currency')}")
                    asset.update(source_symbol=meta['symbol'], instrument_type=meta['instrumentType'],
                                 currency=meta.get('currency'), price_basis='adjusted' if adjusted else 'unadjusted')
                result[symbol] = asset
                print(f"  {symbol}: {result[symbol]['as_of']} price={result[symbol]['price']:.2f}")
                break
            except Exception as exc:
                print(f"  [WARN] {symbol} attempt {attempt + 1}: {exc}")
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
    return result


# ── Fear & Greed approximation ────────────────────────────────────────────────

def calc_fear_greed(data):
    scores = []
    spy = data.get("SPY")
    vix = data.get("^VIX")

    # RSI of SPY → map 30‥70 → 10‥90
    if spy:
        s = max(0.0, min(100.0, (spy["rsi"] - 30) * 2.0 + 10))
        scores.append(s)

    # VIX: 10 → 90 (greed), 40 → 10 (fear)
    if vix:
        s = max(0.0, min(100.0, 90 - (vix["price"] - 10) * (80 / 30)))
        scores.append(s)

    # SPY vs 200-DMA
    if spy and spy["ma200"]:
        pct_above = (spy["price"] - spy["ma200"]) / spy["ma200"] * 100
        s = max(0.0, min(100.0, 50 + pct_above * 5))
        scores.append(s)

    return int(round(sum(scores) / len(scores))) if scores else 50


def fg_label(score, lang="en"):
    if score >= 75:
        return ("Extreme Greed", "極度貪婪")[lang == "zh"]
    if score >= 55:
        return ("Greed", "貪婪")[lang == "zh"]
    if score >= 45:
        return ("Neutral", "中性")[lang == "zh"]
    if score >= 25:
        return ("Fear", "恐慌")[lang == "zh"]
    return ("Extreme Fear", "極度恐慌")[lang == "zh"]


def score_to_angle(score):
    return int((score / 100) * 180 - 90)


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_price(v):
    if v is None:
        return "N/A"
    if abs(v) >= 10_000:
        return f"{v:,.0f}"
    if abs(v) >= 100:
        return f"{v:,.2f}"
    return f"{v:.2f}"


def fmt_pct(v):
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def change_class(pct):
    return "change up" if (pct or 0) >= 0 else "change down"


# ── Signal logic ──────────────────────────────────────────────────────────────

def get_signals(d):
    """Return (trend, rsi_sig, ma_sig) dicts for a symbol data dict."""
    price, ma50, ma200, rsi = d["price"], d["ma50"], d["ma200"], d["rsi"]

    # Trend
    if price > ma50 and price > ma200:
        trend = dict(cls="bullish", zh="上升趨勢", en="Uptrend")
    elif price < ma50 and price < ma200:
        trend = dict(cls="bearish", zh="下降趨勢", en="Downtrend")
    else:
        trend = dict(cls="neutral", zh="中性整理", en="Sideways")

    # RSI
    ri = int(round(rsi))
    if rsi >= 70:
        rsi_s = dict(cls="bearish", zh=f"超買 {ri}", en=f"Overbought {ri}")
    elif rsi <= 30:
        rsi_s = dict(cls="bullish", zh=f"超賣 {ri}", en=f"Oversold {ri}")
    elif rsi >= 55:
        rsi_s = dict(cls="bullish", zh=f"偏多 {ri}", en=f"Bullish {ri}")
    elif rsi <= 45:
        rsi_s = dict(cls="bearish", zh=f"偏空 {ri}", en=f"Bearish {ri}")
    else:
        rsi_s = dict(cls="neutral", zh=f"中性 {ri}", en=f"Neutral {ri}")

    # MA cross
    if ma50 >= ma200:
        ma_s = dict(cls="bullish", zh="多頭排列", en="Bullish Alignment")
    else:
        ma_s = dict(cls="bearish", zh="空頭排列", en="Bearish Alignment")

    return trend, rsi_s, ma_s


# ── Analysis text generation ──────────────────────────────────────────────────

def gen_chart_analysis(spy, fg_score, lang):
    sentiment = (f"自製市場情緒 {fg_score}/100（{fg_label(fg_score, 'zh')}）。" if lang == "zh"
                 else f"Custom sentiment: {fg_score}/100 ({fg_label(fg_score)}). ")
    return (gen_asset_summary(spy, "SPY (S&P 500 ETF, USD)", lang) + " " + sentiment).strip()


def gen_summary(data, fg_score, lang):
    def dir_zh(sym, up, dn):
        d = data.get(sym)
        return up if d and d["pct"] >= 0 else dn
    def dir_en(sym, up, dn):
        d = data.get(sym)
        return up if d and d["pct"] >= 0 else dn

    if lang == "zh":
        return (f"市場情緒{fg_label(fg_score,'zh')}，"
                f"美股{dir_zh('SPY','上漲','下跌')}、台股{dir_zh('^TWII','上漲','下跌')}，"
                f"金價{dir_zh('GC=F','上揚','走跌')}，原油{dir_zh('CL=F','走升','承壓')}。")
    else:
        return (f"Sentiment: {fg_label(fg_score,'en')}. "
                f"US equities {dir_en('SPY','rally','decline')}, "
                f"TW equities {dir_en('^TWII','rise','fall')}, "
                f"gold {dir_en('GC=F','edges up','edges down')}, "
                f"crude {dir_en('CL=F','gains','slips')}.")


def gen_key_levels(spy, lang):
    if not spy:
        return ("<p>數據暫時無法取得。</p>" if lang == "zh"
                else "<p>Data temporarily unavailable.</p>")
    sup = fmt_price(spy["support"])
    res = fmt_price(spy["resistance"])
    deep = fmt_price(spy["ma200"])
    if lang == "zh":
        return (f'<p><span data-lang-zh>支撐：</span>'
                f'<span class="key-level-support">{sup}</span>（20日低點）'
                f'&nbsp;|&nbsp; '
                f'<span data-lang-zh>阻力：</span>'
                f'<span class="key-level-resistance">{res}</span>（20日高點）</p>'
                f'<p style="margin-top:0.35rem;font-size:0.8rem;opacity:0.8;">'
                f'長期參考：<span class="key-level-support">{deep}</span>（200日均線）</p>')
    else:
        return (f'<p>Support: <span class="key-level-support">{sup}</span> (20-day low)'
                f'&nbsp;|&nbsp; '
                f'Resistance: <span class="key-level-resistance">{res}</span> (20-day high)</p>'
                f'<p style="margin-top:0.35rem;font-size:0.8rem;opacity:0.8;">'
                f'Long-term reference: <span class="key-level-support">{deep}</span> (200-day SMA)</p>')


# ── HTML surgery ──────────────────────────────────────────────────────────────

def replace_inner(html, eid, new_content, tag):
    pattern = rf'(<{tag}[^>]*\bid="{eid}"[^>]*>)(.*?)(</{tag}>)'
    def _repl(m):
        return m.group(1) + new_content + m.group(3)
    updated, count = re.subn(pattern, _repl, html, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected exactly one target: {eid}; found {count}")
    return updated


def replace_span_full(html, eid, css_class, new_content):
    """Replace entire <span id="eid" ...>...</span> including class."""
    pattern = rf'<span[^>]*\bid="{eid}"[^>]*>.*?</span>'
    replacement = f'<span id="{eid}" class="{css_class}">{new_content}</span>'
    updated, count = re.subn(pattern, lambda _: replacement, html, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected exactly one target: {eid}; found {count}")
    return updated


def replace_signal_div(html, eid, sig, css_class="signal-value"):
    """Replace <div id="eid" class="signal-value ...">...</div>."""
    inner = (f'<span data-lang-zh>{sig["zh"]}</span>'
             f'<span data-lang-en>{sig["en"]}</span>')
    replacement = f'<div id="{eid}" class="{css_class} {sig["cls"]}">{inner}</div>'
    pattern = rf'<div\s+id="{eid}"[^>]*>.*?</div>'
    updated, count = re.subn(pattern, lambda _: replacement, html, flags=re.DOTALL)
    if count != 1:
        raise ValueError(f"Expected exactly one signal: {eid}; found {count}")
    return updated


def render_tw_etf_chart(ticker, history):
    """Render a dependency-free three-month SVG sparkline for one Taiwan ETF."""
    points = []
    for item in history or []:
        try:
            value = float(item["close"])
            date = str(item["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if np.isfinite(value):
            points.append((date, value))

    if len(points) < 2:
        return None

    width, height = 300.0, 126.0
    values = [value for _, value in points]
    low, high = min(values), max(values)
    spread = high - low
    if spread == 0:
        spread = max(abs(high) * 0.02, 1.0)
    low -= spread * 0.08
    high += spread * 0.08

    def x_at(index):
        return index / (len(points) - 1) * width

    def y_at(value):
        return (high - value) / (high - low) * height

    coords = [(x_at(i), y_at(value)) for i, (_, value) in enumerate(points)]
    line_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area_path = (f"{line_path} L {coords[-1][0]:.1f},{height:.1f} "
                 f"L {coords[0][0]:.1f},{height:.1f} Z")

    first, latest = values[0], values[-1]
    change = ((latest - first) / first * 100) if first else 0.0
    change_class = "up" if change >= 0 else "down"
    change_text = f"{change:+.2f}%"
    start_date = points[0][0][5:].replace("-", "/")
    end_date = points[-1][0][5:].replace("-", "/")
    gradient_id = f"tw-etf-gradient-{ticker}"

    return f'''      <div id="tw-etf-chart-{ticker}" class="tw-etf-chart" role="img" aria-label="{ticker} three-month price chart; latest NT$ {latest:.2f}; change {change_text}">
        <div class="tw-etf-chart-summary">
          <span class="tw-etf-chart-price">NT$ {latest:.2f}</span>
          <span class="tw-etf-chart-change {change_class}">3M {change_text}</span>
        </div>
        <svg viewBox="0 0 300 126" preserveAspectRatio="none" aria-hidden="true" focusable="false">
          <defs>
            <linearGradient id="{gradient_id}" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--gold)" stop-opacity="0.28"/>
              <stop offset="100%" stop-color="var(--gold)" stop-opacity="0.02"/>
            </linearGradient>
          </defs>
          <line class="tw-etf-chart-grid" x1="0" y1="63" x2="300" y2="63"/>
          <path class="tw-etf-chart-area" d="{area_path}" fill="url(#{gradient_id})"/>
          <path class="tw-etf-chart-line" d="{line_path}"/>
        </svg>
        <div class="tw-etf-chart-range"><span>{start_date}</span><span>{end_date}</span></div>
      </div>'''


def replace_tw_etf_chart(html, ticker, chart_markup):
    """Replace one marker-delimited chart without parsing nested HTML with regex."""
    start = f"<!-- TW_ETF_CHART_{ticker}_START -->"
    end = f"<!-- TW_ETF_CHART_{ticker}_END -->"
    pattern = rf"({re.escape(start)}).*?({re.escape(end)})"
    replacement = f"{start}\n{chart_markup}\n          {end}"
    updated, count = re.subn(pattern, lambda _: replacement, html, flags=re.DOTALL)
    if count != 1:
        print(f"  [WARN] {ticker}: expected one chart marker block, found {count}")
        raise ValueError(f"Missing or duplicate chart markers: {ticker}")
    return updated


def gen_asset_summary(asset, symbol, lang):
    if not asset:
        return "資料暫缺，訊號未更新。" if lang == "zh" else "Data unavailable; signals not updated."
    trend, _, ma = get_signals(asset)
    if lang == "zh":
        return (f"{symbol}｜資料日期 {asset['as_of']}；價格 {fmt_price(asset['price'])}，"
                f"單日變動 {fmt_pct(asset['pct'])}；RSI(14) {asset['rsi']:.1f}。"
                f"{trend['zh']}，{ma['zh']}；SMA50 {fmt_price(asset['ma50'])}，"
                f"SMA200 {fmt_price(asset['ma200'])}。")
    return (f"{symbol} | Bar date {asset['as_of']}; price {fmt_price(asset['price'])}, "
            f"daily change {fmt_pct(asset['pct'])}; RSI(14) {asset['rsi']:.1f}. "
            f"{trend['en']}; {ma['en']}; SMA50 {fmt_price(asset['ma50'])}, "
            f"SMA200 {fmt_price(asset['ma200'])}.")


def update_html(html, data, fg_score, now=None, failed=None):
    now = now or utc_now()
    failed = failed or []
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")

    spy  = data.get("SPY")  or {}
    twii = data.get("^TWII") or {}
    gold = data.get("GC=F")  or {}
    oil  = data.get("CL=F")  or {}

    # ── Gauge ──
    angle = score_to_angle(fg_score)
    html = re.sub(r"(--angle:\s*)-?\d+", rf"\g<1>{angle}", html)
    html = replace_inner(html, "fear-greed-value", str(fg_score), "div")
    for lang in ("zh", "en"):
        html = replace_inner(html, f"fear-greed-label-{lang}", fg_label(fg_score, lang), "span")
        sentiment = (f"自製市場情緒 {fg_score}/100（{fg_label(fg_score, lang)}）。" if lang == "zh"
                     else f"Market Pulse sentiment {fg_score}/100 ({fg_label(fg_score, lang)}). ")
        html = replace_inner(html, f"bottom-line-{lang}",
                             sentiment + gen_asset_summary(spy, "SPY", lang), "p")

    # ── Snapshot cards ──
    html = replace_inner(html, "sp500-price", fmt_price(spy.get("price")), "span")
    html = replace_span_full(html, "sp500-change",
                             change_class(spy.get("pct")), fmt_pct(spy.get("pct")))

    html = replace_inner(html, "twii-price", fmt_price(twii.get("price")), "span")
    html = replace_span_full(html, "twii-change",
                             change_class(twii.get("pct")), fmt_pct(twii.get("pct")))

    html = replace_inner(html, "gold-price", fmt_price(gold.get("price")), "span")
    html = replace_span_full(html, "gold-change",
                             change_class(gold.get("pct")), fmt_pct(gold.get("pct")))

    html = replace_inner(html, "oil-price", fmt_price(oil.get("price")), "span")
    html = replace_span_full(html, "oil-change",
                             change_class(oil.get("pct")), fmt_pct(oil.get("pct")))

    # ── Summary ──
    html = replace_inner(html, "summary-zh", gen_summary(data, fg_score, "zh"), "span")
    html = replace_inner(html, "summary-en", gen_summary(data, fg_score, "en"), "span")

    # ── Chart analysis ──
    html = replace_inner(html, "chart-analysis-zh",
                         "\n        " + gen_chart_analysis(spy if spy else None, fg_score, "zh") + "\n      ",
                         "p")
    html = replace_inner(html, "chart-analysis-en",
                         "\n        " + gen_chart_analysis(spy if spy else None, fg_score, "en") + "\n      ",
                         "p")

    # ── Key levels ──
    html = replace_inner(html, "key-levels-zh",
                         "\n            " + gen_key_levels(spy if spy else None, "zh") + "\n          ",
                         "div")
    html = replace_inner(html, "key-levels-en",
                         "\n            " + gen_key_levels(spy if spy else None, "en") + "\n          ",
                         "div")

    # ── Signal cards ──
    panel_map = {
        "us":     data.get("SPY"),
        "tw":     data.get("^TWII"),
        "tech":   data.get("NVDA"),
        "metals": data.get("GC=F"),
        "energy": data.get("CL=F"),
    }
    for panel, asset in panel_map.items():
        empty = dict(cls="neutral", zh="資料暫缺", en="Unavailable")
        trend, rsi_s, ma_s = get_signals(asset) if asset else (empty, empty, empty)
        html = replace_signal_div(html, f"{panel}-trend", trend)
        html = replace_signal_div(html, f"{panel}-rsi",   rsi_s)
        html = replace_signal_div(html, f"{panel}-ma",    ma_s)
        label = {"us": "SPY", "tw": "TAIEX", "tech": "NVDA", "metals": "Gold", "energy": "WTI"}[panel]
        for lang in ("zh", "en"):
            html = replace_inner(html, f"{panel}-analysis-{lang}", gen_asset_summary(asset, label, lang), "span")

    for symbol, ticker in ETF_SYMBOLS.items():
        asset = data.get(symbol)
        empty = dict(cls="neutral", zh="資料暫缺", en="Unavailable")
        signals = get_signals(asset) if asset else (empty, empty, empty)
        for kind, sig in zip(("trend", "rsi", "ma"), signals):
            html = replace_signal_div(html, f"etf-{ticker}-{kind}", sig, "etf-signal-val")
        date = asset['as_of'] if asset else ""
        state = "retained" if symbol in failed and asset else ("current" if asset else "unavailable")
        note = (f'<span data-lang-zh>資料日期：{date or "暫缺"}</span>'
                f'<span data-lang-en>Bar date: {date or "unavailable"}</span>'
                f' <span class="asset-age" data-as-of="{date}" data-fetch-state="{state}"></span>')
        html = replace_inner(html, f"etf-{ticker}-date", note, "p")

    # ── Self-hosted Taiwan ETF charts ──
    for yahoo_symbol, ticker in TW_ETFS.items():
        asset = data.get(yahoo_symbol)
        chart = render_tw_etf_chart(ticker, asset.get("history") if asset else None)
        if chart:
            html = replace_tw_etf_chart(html, ticker, chart)
        else:
            html = replace_tw_etf_chart(html, ticker,
                '<div class="tw-etf-chart"><span data-lang-zh>圖表資料暫缺</span>'
                '<span data-lang-en>Chart data unavailable</span></div>')

    html = update_charts(html, data, failed)

    # ── Timestamps ──
    dates = sorted({data[s]["as_of"] for s in CORE_SYMBOLS})
    date_range = dates[0] if len(dates) == 1 else f"{dates[0]} — {dates[-1]}"
    proto = (f'<span data-lang-zh>行情日期（交易所當地）：{date_range} · 日線資料可能含當日未收盤行情</span>'
             f'<span data-lang-en>Exchange bar dates: {date_range} · Daily bars may include an unfinished session</span>')
    html = replace_inner(html, "protoTag", proto, "div")
    html = replace_inner(html, "heroDate", date_range, "p")
    html = replace_inner(html, "freshnessTime", f'<time datetime="{now.isoformat()}">{stamp}</time>', "span")
    warning = (f"部分來源未更新：{', '.join(failed)}" if failed else "")
    warning_en = (f"Some sources did not refresh: {', '.join(failed)}" if failed else "")
    html = replace_inner(html, "dataHealth", f'<span data-lang-zh>{warning}</span><span data-lang-en>{warning_en}</span>', "p")
    metadata = json.dumps({"generated_at": now.isoformat(), "failed": failed,
                           "core_dates": {s: data[s]["as_of"] for s in sorted(CORE_SYMBOLS)}})
    html = replace_inner(html, "market-data-status", metadata, "script")

    return html


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"\nMarket Pulse Update — {datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    data = fetch_all()
    failed = [symbol for symbol, asset in data.items() if not asset]
    missing_core = sorted(CORE_SYMBOLS.intersection(failed))
    if missing_core:
        message = "Core data unavailable; published files unchanged: " + ", ".join(missing_core)
        report_health(message, error=True)
        raise SystemExit(1)
    if SNAPSHOT_PATH.exists():
        previous = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        for symbol in failed:
            cached = previous.get("assets", {}).get(symbol)
            if cached and cached.get("as_of"):
                if symbol in SOURCE_SPECS:
                    try:
                        history_points(cached, SOURCE_SPECS[symbol]['sessions'])
                    except (ValueError, TypeError, KeyError):
                        continue
                data[symbol] = cached
    fg   = calc_fear_greed(data)
    print(f"\nFear & Greed: {fg} ({fg_label(fg, 'en')})")

    try:
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"\nERROR: {INDEX_HTML} not found. Run from the repo root.")
        sys.exit(1)

    now = utc_now()
    html = update_html(html, data, fg, now, failed)
    validate_output(html, data, fg)

    snapshot = json.dumps({"generated_at": now.isoformat(), "failed": failed, "assets": data},
                          ensure_ascii=False, indent=2, allow_nan=False)
    atomic_write(SNAPSHOT_PATH, snapshot + "\n")
    atomic_write(Path(INDEX_HTML), html)
    report_health("Published valid daily data; " + ("retained/unavailable: " + ", ".join(failed) if failed else "all sources refreshed"), warning=bool(failed))

    print(f"\nDone — {INDEX_HTML} updated successfully.")


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def report_health(message, error=False, warning=False):
    print(("::error::" if error else "::warning::" if warning else "") + message)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Market data health\n\n" + message + "\n")


def validate_output(html, data, score):
    validate_charts(html, data)
    if "\x00" in html or re.search(r">\s*(?:nan|inf|-inf)\s*<", html, re.I):
        raise ValueError("Invalid numeric output or NUL padding")
    if f'id="fear-greed-label-en" data-lang-en>{fg_label(score)}<' not in html:
        raise ValueError("Sentiment label mismatch")
    for ticker in TW_ETFS.values():
        if f'TWSE:{ticker}' in html:
            raise ValueError("Restricted TW widget still present")
    if "proto.innerHTML" in html or "tag.textContent = 'Updated '" in html:
        raise ValueError("Browser overwrites source timestamp")


if __name__ == "__main__":
    main()
