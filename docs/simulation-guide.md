---
title: "Monte Carlo Simulation User Guide"
description: "Comprehensive guide for using the Rolling-Window Monte Carlo simulation feature in the ETF Income Dashboard"
version: "1.0.0"
metadata:
  tags:
    - "documentation"
    - "user-guide"
    - "monte-carlo"
    - "etf"
---

# 📊 Monte Carlo Simulation User Guide

## Table of Contents
1. [Getting Started](#getting-started)
2. [Understanding the Parameters](#understanding-the-parameters)
3. [Interpreting Results](#interpreting-results)
4. [Advanced Usage](#advanced-usage)
5. [Troubleshooting](#troubleshooting)

---

## Getting Started

The Monte Carlo simulation helps you understand potential portfolio outcomes under different scenarios. It uses historical price and dividend data to simulate thousands of possible future paths.

### Quick Start

1. **Navigate to the Portfolio Builder**: Click on "Portfolio Builder" in the sidebar
2. **Enter ETF Tickers**: Type comma-separated tickers (e.g., `KQQQ,IGLD,RPAR`)
3. **Configure Simulation**: Adjust parameters as needed
4. **Run Simulation**: Click "Simulate" button
5. **Review Results**: View statistics and charts

---

## Understanding the Parameters

### Tickers
**What it is**: A comma-separated list of ETF symbols to include in your simulation.

**How to use**: 
- Enter valid ticker symbols (e.g., `VYM, SCHD, DVY`)
- Maximum 10 tickers recommended for performance
- Only tickers with sufficient price history will be included

### Window Periods
**What it is**: The lookback period used for historical analysis.

| Value | Description |
|-------|-------------|
| 1 Year | Most recent 12 months of data |
| 3 Years | Trailing 36 months |
| 5 Years | Trailing 60 months |
| 10 Years | Trailing 120 months |
| 15 Years | Trailing 180 months |
| 20 Years | Trailing 240 months |
| Max | All available historical data |

**Recommendation**: Use 5-10 years for balanced analysis. Longer periods provide more data but may include outdated market conditions.

### Iterations
**What it is**: The number of simulation runs to perform.

| Range | Use Case |
|-------|----------|
| 100-500 | Quick previews, exploratory analysis |
| 500-2000 | Standard portfolio analysis |
| 2000-5000 | Detailed risk assessment |
| 5000-10000 | High-confidence scenarios |

**Note**: The system automatically uses parallel processing for >500 iterations.

### Tax Rate
**What it is**: Your marginal tax rate for dividend income.

**How to use**:
- Enter percentage (e.g., 24 for 24%)
- Default is 20%, a reasonable estimate for many investors
- Higher rates reduce after-tax yield projections

---

## Interpreting Results

### Key Metrics

#### Annualized Income
The projected annual dividend income as a percentage of portfolio value.

| Statistic | Meaning |
|-----------|---------|
| Mean | Average annualized yield across all simulations |
| Median | Middle value (50% of simulations above/below) |
| P5/P95 | Best/worst case scenarios (5th/95th percentile) |

**Example**: If median = 3.5% and P95 = 5.2%, you can expect income between 3.5-5.2% in most scenarios.

#### Total Return
Combined return from price appreciation + dividends (before tax).

| Statistic | Meaning |
|-----------|---------|
| Mean | Average total return |
| Median | Typical outcome |
| P5/P95 | Conservative vs optimistic scenarios |

#### NAV Change
Pure price appreciation component (excludes dividends).

---

### Charts

#### Portfolio Value Chart
Shows the distribution of ending portfolio values across simulations.

**Interpretation**:
- Bell curve = Normal distribution of outcomes
- Wide spread = Higher uncertainty/risk
- Tight cluster = More predictable outcomes

#### Monthly Income Chart
Distribution of monthly dividend payments.

**Interpretation**:
- Look for consistency (low variance)
- High median with low spread = Stable income

#### NAV Analysis
Visualizes potential drawdowns and recovery patterns.

---

## Advanced Usage

### Scenario Analysis

**Conservative Portfolio** (Low Risk):
```
Tickers: VYM, SCHD
Window: 10 years
Iterations: 2000
Tax Rate: 24%
```

**Growth-Oriented Portfolio**:
```
Tickers: KQQQ, IGLD, RPAR
Window: 5 years
Iterations: 3000
Tax Rate: 20%
```

### Stress Testing

Use shorter windows during volatile periods:
- 1-2 year window with 5000+ iterations
- Focus on P5/P95 margins
- Compare to 5-year baseline

### Tax-Adjusted Analysis

To see after-tax outcomes:
1. Enable "Tax Adj" checkbox
2. Enter your actual tax rate
3. Compare taxable vs non-taxable results

---

## Troubleshooting

### Common Issues

**No Results Displayed**
- Check that tickers are valid and have price history
- Ensure window period doesn't exceed available data
- Try reducing the number of tickers

**Slow Performance**
- Reduce iterations (start with 500-1000)
- Reduce window period
- Use fewer tickers

**Inconsistent Results**
- Small iteration counts (<100) can vary significantly
- Run multiple times and compare medians
- Use higher iteration counts for stable results

**Error: "Insufficient history"**
- The ETF doesn't have enough historical data
- Try a different ETF or shorter window period

### Tips for Best Results

1. **Start Simple**: Begin with 2-3 well-known ETFs
2. **Validate Data**: Check that tickers have at least 5 years of history
3. **Use Defaults**: Default settings work well for most users
4. **Iterate**: Run multiple simulations with different parameters
5. **Compare**: Run side-by-side comparisons of different portfolios

---

## Technical Details

### Methodology

- **Bootstrap Resampling**: Samples historical periods with replacement
- **Equal Weighting**: All ETFs in the basket receive equal weight
- **Monthly Sampling**: Simulates one month at a time
- **Return Calculation**: (Current - Previous) / Previous + Dividend Yield

### Limitations

- Historical performance doesn't guarantee future results
- Assumes equal weighting (no rebalancing)
- Does not account for tax-loss harvesting
- Does not model transaction costs

---

## Getting Help

If you encounter issues:
1. Check the [ETF Income Dashboard documentation](/)
2. Review your ticker symbols at [ETF Database](https://etfdb.com)
3. Contact support for technical issues

---

*Last updated: July 2026*