---
title: "Rolling-Window Monte Carlo Simulation for ETF Portfolios"
name: "simulation-monte-carlo"
description: "Implements parameterized investment simulations showing 5/10/20-year outcome distributions. Used for risk assessment and portfolio planning."
version: "1.0.0"
metadata:
  tags:
    - "monte-carlo"
    - "simulation"
    - "etf"
    - "risk-analysis"
  created_by: "ShyGuy"
  created_at: "2026-07-19"
parameters:
  tickers: "Comma-separated ETF tickers for portfolio (required)"
  window_months: "Lookback period (6-240 months, default 12)"
  iterations: "Number of simulation runs (100-10000, default 1000)"
  tax_rate: "Tax rate applied (default 0.20)"
  taxable: "Whether to apply tax treatment (default true)"
---
# Rolling-Window Monte Carlo Simulation for ETF Portfolios

Implements parameterized investment simulations showing 5/10/20-year outcome distributions. Used for risk assessment and portfolio planning.

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| tickers | Comma-separated ETF tickers for portfolio (required) | - |
| window_months | Lookback period (6-240 months) | 12 |
| iterations | Number of simulation runs (100-10000) | 1000 |
| tax_rate | Tax rate applied | 0.20 |
| taxable | Whether to apply tax treatment | true |

## Output Metrics

### annualized_income
- mean: Average annualized dividend yield (%)
- median: Median annualized yield (%)
- p5/p95: 5th/95th percentile

### total_return
- mean: Average total return with dividends (%)
- median: Median total return (%)
- p5/p95: 5th/95th percentile

### nav_change
- mean: Average NAV change (%)
- median: Median NAV change (%)
- p5/p95: 5th/95th percentile

## Implementation Notes

- Equal-weight portfolio assumed
- Bootstrap resampling used for historical periods
- Monthly returns and dividends combined for annualization
- Tax treatment applied to dividend yields only
- Results stored as JSON for API consumption

## Optimization

- Parallel execution with ThreadPoolExecutor for >500 iterations
- Cache price_history results to avoid repeated DB hits
- Pool iterations in 100-run batches
- Fallback mechanism for DB modification detection

## Quality Checks

- Validate ticker symbols before processing
- Ensure sufficient price history exists for window
- Handle zero-division cases in yield calculations
- Validate JSON output structure before returning