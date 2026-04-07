# Market Pulse 市場脈動

Daily 30-second market briefing covering US stocks, Taiwan equities, precious metals, and energy.

Live site: [lingalen78-tech.github.io/market-pulse](https://lingalen78-tech.github.io/market-pulse/)

---

## Automated Daily Updates

Market data is refreshed automatically via **GitHub Actions** every weekday at **6 AM PT** (UTC 14:00).

The workflow:
1. Fetches live price, RSI, and moving average data via **Yahoo Finance** (`yfinance`)
2. Calculates a composite **Fear & Greed** score
3. Generates bilingual (EN/ZH) market analysis
4. Rewrites `index.html` with updated values and commits the result

To trigger a manual update, go to **Actions → Daily Market Update → Run workflow**.

---

## Data Sources

| Asset class | Source |
|---|---|
| US equities (SPY, AAPL, NVDA, MSFT, GOOGL) | Yahoo Finance via `yfinance` |
| Taiwan index (^TWII) + TSMC ADR (TSM) | Yahoo Finance via `yfinance` |
| Precious metals (GC=F Gold, SI=F Silver) | Yahoo Finance via `yfinance` |
| Energy (CL=F Crude Oil, NG=F Natural Gas) | Yahoo Finance via `yfinance` |
| Charts | TradingView embedded widgets |

---

## Methodology

### Indicators
| Indicator | Definition |
|---|---|
| **RSI(14)** | 14-period Relative Strength Index on daily closes. >70 = overbought, <30 = oversold. |
| **SMA 50** | 50-day Simple Moving Average |
| **SMA 200** | 200-day Simple Moving Average. Price above = bullish long-term bias. |
| **MA Signal** | Bullish Cross = SMA50 > SMA200; Bearish Cross = SMA50 < SMA200 |

### Fear & Greed Composite
A weighted average of three components:
- **SPY RSI** — momentum proxy (RSI 30→70 maps to 10→90)
- **VIX level** — volatility proxy (VIX 10→40 maps to 90→10)
- **SPY vs 200-DMA** — trend proxy (% above/below 200-day SMA)

### Key Levels
- **Support** = 20-day rolling low
- **Resistance** = 20-day rolling high
- **Deep support** = 200-day SMA

---

## Local Development

```bash
pip install -r requirements.txt
python update_market_data.py
```

Then open `index.html` in your browser.

---

## Tech Stack

- Pure HTML / CSS / JavaScript — no frontend build step
- TradingView Widgets for interactive charts
- GitHub Pages for hosting
- GitHub Actions for daily automation
- Python + `yfinance` for data pipeline

---

*Content is for informational purposes only and does not constitute investment advice.*
