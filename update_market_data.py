#!/usr/bin/env python3
"""
Market Pulse - Daily Data Update Script
Fetches real market data from Yahoo Finance (yfinance) and updates index.html.
Run from the repo root: python update_market_data.py
"""

import re
import sys
import datetime
import numpy as np
import yfinance as yf

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
    for symbol, name in SYMBOLS.items():
        try:
            hist = yf.Ticker(symbol).history(period="250d", auto_adjust=True)
            if hist.empty or len(hist) < 20:
                print(f"  [WARN] {symbol}: insufficient data")
                result[symbol] = None
                continue

            # Yahoo occasionally appends an in-progress row whose Close is NaN.
            # Ignore incomplete rows so charts and indicators keep the latest valid close.
            close = hist["Close"].dropna()
            if len(close) < 20:
                print(f"  [WARN] {symbol}: insufficient valid closing prices")
                result[symbol] = None
                continue
            price = float(close.iloc[-1])
            prev  = float(close.iloc[-2])
            pct   = (price - prev) / prev * 100

            rsi   = calculate_rsi(close)
            ma50  = float(close.rolling(50).mean().iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1])

            tail20 = hist.loc[close.index].dropna(subset=["Low", "High"]).tail(20)
            support    = float(tail20["Low"].min())
            resistance = float(tail20["High"].max())

            history = []
            if symbol in TW_ETFS:
                history = [
                    {
                        "date": timestamp.date().isoformat(),
                        "close": round(float(value), 2),
                    }
                    for timestamp, value in close.tail(66).items()
                ]

            result[symbol] = dict(
                name=name, price=price, pct=pct,
                rsi=rsi, ma50=ma50, ma200=ma200,
                support=support, resistance=resistance,
                history=history,
            )
            print(f"  {symbol:<8}  {price:>10.2f}  ({pct:+.2f}%)  RSI={rsi:.1f}")
        except Exception as exc:
            print(f"  [ERR]  {symbol}: {exc}")
            result[symbol] = None
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
        ma_s = dict(cls="bullish", zh="多頭排列", en="Bullish Cross")
    else:
        ma_s = dict(cls="bearish", zh="空頭排列", en="Bearish Cross")

    return trend, rsi_s, ma_s


# ── Analysis text generation ──────────────────────────────────────────────────

def gen_chart_analysis(spy, fg_score, lang):
    if not spy:
        return ("S&P 500 數據目前無法取得，請稍後再試。" if lang == "zh"
                else "S&P 500 data currently unavailable. Please check back later.")

    price = spy["price"]
    rsi   = spy["rsi"]
    ma50  = spy["ma50"]
    ma200 = spy["ma200"]
    pct   = spy["pct"]
    ri    = int(round(rsi))

    if lang == "zh":
        move = "上漲" if pct >= 0 else "下跌"
        rsi_note = (f"RSI 達 {ri}，技術面超買，短期回檔壓力升高。" if rsi >= 70 else
                    f"RSI 降至 {ri}，技術面超賣，留意反彈機會。" if rsi <= 30 else
                    f"RSI 位於 {ri}，尚未進入極端區間。")
        ma_note = ("均線多頭排列，長期趨勢偏多。" if ma50 >= ma200
                   else "均線呈空頭排列，長期趨勢承壓。")
        fg_note = (f"恐懼貪婪指數 {fg_score}（{fg_label(fg_score,'zh')}），"
                   + ("市場樂觀情緒偏高，需留意過熱風險。" if fg_score >= 60 else
                      "市場情緒保守，逢低布局機會可能浮現。" if fg_score <= 40 else
                      "情緒中性，等待明確方向。"))
        return (f"S&P 500 今日{move} {fmt_pct(pct)}，報 {fmt_price(price)}。"
                f"{rsi_note}{ma_note}{fg_note}")
    else:
        move = "gained" if pct >= 0 else "lost"
        rsi_note = (f"RSI at {ri} is overbought — near-term pullback risk is elevated." if rsi >= 70 else
                    f"RSI at {ri} is oversold — watch for a potential bounce." if rsi <= 30 else
                    f"RSI at {ri} sits in neutral territory.")
        ma_note = ("MA50 above MA200 confirms a bullish long-term trend." if ma50 >= ma200
                   else "MA50 below MA200 — long-term trend remains under pressure.")
        fg_note = (f"Fear & Greed at {fg_score} ({fg_label(fg_score,'en')}) — "
                   + ("elevated optimism warrants caution." if fg_score >= 60 else
                      "defensive positioning — dip-buying opportunities may emerge." if fg_score <= 40 else
                      "neutral sentiment awaiting a catalyst."))
        return (f"S&P 500 {move} {fmt_pct(pct)} today to {fmt_price(price)}. "
                f"{rsi_note} {ma_note} {fg_note}")


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
                f'深度支撐：<span class="key-level-support">{deep}</span>（200日均線）</p>')
    else:
        return (f'<p>Support: <span class="key-level-support">{sup}</span> (20-day low)'
                f'&nbsp;|&nbsp; '
                f'Resistance: <span class="key-level-resistance">{res}</span> (20-day high)</p>'
                f'<p style="margin-top:0.35rem;font-size:0.8rem;opacity:0.8;">'
                f'Deep support: <span class="key-level-support">{deep}</span> (200-day SMA)</p>')


# ── HTML surgery ──────────────────────────────────────────────────────────────

def replace_inner(html, eid, new_content, tag):
    pattern = rf'(<{tag}[^>]*\bid="{eid}"[^>]*>)(.*?)(</{tag}>)'
    def _repl(m):
        return m.group(1) + new_content + m.group(3)
    return re.sub(pattern, _repl, html, flags=re.DOTALL)


def replace_span_full(html, eid, css_class, new_content):
    """Replace entire <span id="eid" ...>...</span> including class."""
    pattern = rf'<span[^>]*\bid="{eid}"[^>]*>.*?</span>'
    replacement = f'<span id="{eid}" class="{css_class}">{new_content}</span>'
    return re.sub(pattern, lambda _: replacement, html, flags=re.DOTALL)


def replace_signal_div(html, eid, sig):
    """Replace <div id="eid" class="signal-value ...">...</div>."""
    inner = (f'<span data-lang-zh>{sig["zh"]}</span>'
             f'<span data-lang-en>{sig["en"]}</span>')
    replacement = f'<div id="{eid}" class="signal-value {sig["cls"]}">{inner}</div>'
    pattern = rf'<div\s+id="{eid}"[^>]*>.*?</div>'
    return re.sub(pattern, lambda _: replacement, html, flags=re.DOTALL)


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
        return html
    return updated


def update_html(html, data, fg_score):
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M UTC")

    spy  = data.get("SPY")  or {}
    twii = data.get("^TWII") or {}
    gold = data.get("GC=F")  or {}
    oil  = data.get("CL=F")  or {}

    # ── Gauge ──
    angle = score_to_angle(fg_score)
    html = re.sub(r"(--angle:\s*)-?\d+", rf"\g<1>{angle}", html)
    html = replace_inner(html, "fear-greed-value", str(fg_score), "div")

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
        if not asset:
            continue
        trend, rsi_s, ma_s = get_signals(asset)
        html = replace_signal_div(html, f"{panel}-trend", trend)
        html = replace_signal_div(html, f"{panel}-rsi",   rsi_s)
        html = replace_signal_div(html, f"{panel}-ma",    ma_s)

    # ── Self-hosted Taiwan ETF charts ──
    for yahoo_symbol, ticker in TW_ETFS.items():
        asset = data.get(yahoo_symbol)
        chart = render_tw_etf_chart(ticker, asset.get("history") if asset else None)
        if chart:
            html = replace_tw_etf_chart(html, ticker, chart)
        else:
            print(f"  [WARN] {ticker}: keeping last-known-good chart")

    # ── Timestamps ──
    last_tag = (f'Data source: <span>Yahoo Finance</span>'
                f' &nbsp;&middot;&nbsp; Updated: <span>{now}</span>')
    html = replace_inner(html, "lastUpdatedTag", last_tag, "span")

    proto = (f'Auto-updated via GitHub Actions'
             f' &nbsp;&middot;&nbsp; Last updated: <span>{now}</span>'
             f' &nbsp;&middot;&nbsp; Sources: <span>Yahoo Finance (yfinance)</span>'
             f' &nbsp;&middot;&nbsp; Refresh: <span>Weekdays 6 AM PT</span>')
    html = replace_inner(html, "protoTag", proto, "div")

    return html


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print(f"\nMarket Pulse Update — {datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    data = fetch_all()
    fg   = calc_fear_greed(data)
    print(f"\nFear & Greed: {fg} ({fg_label(fg, 'en')})")

    try:
        with open(INDEX_HTML, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print(f"\nERROR: {INDEX_HTML} not found. Run from the repo root.")
        sys.exit(1)

    html = update_html(html, data, fg)

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDone — {INDEX_HTML} updated successfully.")


if __name__ == "__main__":
    main()
