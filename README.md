# Market Pulse 市場脈動

Daily 30-second market briefing covering US stocks, Taiwan equities, precious metals, and energy.

Live site: [lingalen78-tech.github.io/market-pulse](https://lingalen78-tech.github.io/market-pulse/)

---

## Automated Daily Updates

Market data is scheduled via **GitHub Actions** every weekday at **14:00 UTC** (6 AM PST / 7 AM PDT). Runs may be delayed. Daily bars can include an unfinished trading session; the page displays exchange-local bar dates separately from the UTC fetch timestamp.

The workflow:
1. Fetches adjusted daily prices via **Yahoo Finance** (`yfinance`) and computes RSI and moving averages
2. Calculates a custom **Market Pulse sentiment** score (not CNN's index)
3. Generates bilingual (EN/ZH) market analysis
4. Rebuilds five Taiwan ETF SVG charts from the latest 66 valid closes
5. Rewrites `index.html` and `data/market-data.json` with validated values and commits the result

Each source gets up to three attempts and must contain at least 200 valid closes, finite indicators, and a bar no more than seven calendar days old. If a core source (SPY, TAIEX, gold, oil or VIX) fails, the update exits nonzero without changing published files. Optional-source failures retain that asset's last valid snapshot (or display unavailable on first failure), visibly identify it as retained, and emit an Actions warning and job summary. Browser age checks flag an old overall snapshot without inventing a new update time.

All ten ETF signal cards, five dashboard summaries, the main SPY chart analysis, sentiment labels and Bottom Line are generated from this snapshot. Sector/theme and other editorial text is explicitly static; it is not refreshed by this workflow. The separate daily optimization report does not itself deploy code.

To trigger a manual update, go to **Actions → Daily Market Update → Run workflow**.

---

## Data Sources

| Asset class | Source |
|---|---|
| US equities (SPY, AAPL, NVDA, MSFT, GOOGL) | Yahoo Finance via `yfinance` |
| Taiwan index (^TWII) + TSMC ADR (TSM) | Yahoo Finance via `yfinance` |
| Taiwan ETFs (0050, 0056, 00878, 00919, 00929) | Yahoo Finance via `yfinance`; inline SVG charts |
| Precious metals (GC=F Gold, SI=F Silver) | Yahoo Finance via `yfinance` |
| Energy (CL=F Crude Oil, NG=F Natural Gas) | Yahoo Finance via `yfinance` |
| Other charts | TradingView embedded widgets |

---

## Methodology

### Indicators
| Indicator | Definition |
|---|---|
| **RSI(14)** | Simple 14-day mean gains/losses on adjusted daily closes, not Wilder smoothing. >=70 = overbought, <=30 = oversold. |
| **SMA 50** | 50-day Simple Moving Average |
| **SMA 200** | 200-day Simple Moving Average. Price above = bullish long-term bias. |
| **MA Signal** | Bullish alignment = SMA50 >= SMA200; bearish alignment = SMA50 < SMA200. This is a state, not a newly detected crossover. |

### Fear & Greed Composite
An equal-weight average of three clipped 0–100 components (not the CNN Fear & Greed Index):
- **SPY RSI** — momentum proxy (RSI 30→70 maps to 10→90)
- **VIX level** — volatility proxy (VIX 10→40 maps to 90→10)
- **SPY vs 200-DMA** — trend proxy (% above/below 200-day SMA)

### Key Levels
- **Support** = 20-day rolling low
- **Resistance** = 20-day rolling high
- **Long-term reference** = 200-day SMA (not necessarily support)

---

## Local Development

```bash
pip install -r requirements.txt
python -m unittest -v test_market_data.py
node --test test_data_status.cjs
python update_market_data.py
```

Then open `index.html` in your browser.

---

## Tech Stack

- Pure HTML / CSS / JavaScript — no frontend build step
- TradingView Widgets plus self-hosted SVG charts for Taiwan ETFs
- GitHub Pages for hosting
- GitHub Actions for daily automation
- Python + `yfinance` for data pipeline

---

*Content is for informational purposes only and does not constitute investment advice.*
