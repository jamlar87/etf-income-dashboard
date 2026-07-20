# Buy the Dip Screener — Implementation Plan

## Research Summary — 10 Source Analysis

### Highest-Quality Dip Signals (ranked by backtested reliability)

| Signal | Weight | Why It Works |
|--------|--------|-------------|
| **RSI(14) < 30** | 25pts | Research shows 87.5% accuracy when combined with BB; 65.6% alone |
| **% off 52-week high** | 25pts | Mean reversion: buying at 10-15% drawdown with trend intact outperforms |
| **Bollinger Band position** | 20pts | Touching below lower band = statistically significant oversold extreme |
| **52-week range percentile** | 15pts | Bottom 10% of range + RSI confirms highest win rate |
| **Trend filter (200d SMA)** | 15pts | CRITICAL: without uptrend, you catch falling knives, not dips |

### Data Constraints
- `price_history` has: ticker, date, close, dividend (monthly — no OHLCV granularity)
- Can compute: RSI, MACD, SMA, EMA, Bollinger Bands, 52-week metrics
- Cannot compute: ATR, volume, true range (need high/low/volume)

## Architecture

### Backend (app.py)
1. New route: `GET /buy-the-dip` → renders `dip-screener.html` template
2. New API: `GET /api/dip-screener` → returns dip signals for all tickers
3. New API: `GET /api/dip-screener/{ticker}` → returns detail chart data

### Frontend
1. `templates/dip-screener.html` — dedicated full page (not a section)
2. `static/js/dip-screener.js` — independent JS (Chart.js-based charts)
3. Nav link added to main template sidebar (points to /buy-the-dip)
4. CSS additions in style.v8.css for dip-specific components

### Dip Score Formula (0-100)

**RSI(14) — 25pts**: <25→25, 25-30→20, 30-40→15, 40-45→8, >45→0. Bonus +5 if rising from oversold.

**% off 52-week high — 25pts**: >20%→25, 15-20%→22, 10-15%→18, 5-10%→12, 3-5%→6, <3%→0

**BB %B position — 20pts**: Below lower band→20, at lower band→16, lower half between→10, upper half→0

**52-week range % — 15pts**: Bottom 10%→15, 10-20%→12, 20-35%→7, >35%→0

**Trend health — 15pts (modifier)**: Above 200d SMA→15 (ideal), 0-5% below→10, 5-10% below→5, >10% below→0

### Tiers
- **Strong Dip** (≥70): 3+ signals aligned, uptrend intact
- **Moderate Dip** (50-69): 2 signals, acceptable trend
- **Watch** (30-49): 1 signal, early/partial
- **No Signal** (<30): not a dip opportunity
