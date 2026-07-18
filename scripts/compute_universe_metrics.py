#!/usr/bin/env python3
"""Compute full metrics (beta, sortino, calmar, etc.) for universe ETFs that pass quality filters."""

import sqlite3
import sys
import time
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
RISK_FREE = 5.0  # annual risk-free rate (%)

NOW = pd.Timestamp.now()


def safe_div_yield(info, etf, current_price):
    """Calculate current dividend yield from yfinance info or dividend history."""
    best_yield = None

    for field in ["trailingAnnualDividendYield", "dividendYield"]:
        val = info.get(field)
        if val and 0 < val < 2.0:
            best_yield = val * 100
            break

    if best_yield is None:
        dr = info.get("dividendRate")
        if dr and current_price and dr > 0:
            best_yield = dr / current_price * 100

    if best_yield is None and current_price:
        divs = etf.dividends
        if len(divs) > 0:
            year_ago = NOW - pd.Timedelta(days=365)
            try:
                recent = divs[divs.index.tz_localize(None) >= year_ago] if len(divs[divs.index.tz_localize(None) >= year_ago]) > 0 else divs.iloc[-12:]
            except (TypeError, AttributeError):
                recent = divs[divs.index >= year_ago] if len(divs[divs.index >= year_ago]) > 0 else divs.iloc[-12:]
            if len(recent) > 0:
                best_yield = recent.sum() / current_price * 100

    if best_yield is None:
        return None

    best_yield = round(best_yield, 2)

    # Sanity check
    if best_yield > 50 and current_price:
        divs = etf.dividends
        if len(divs) >= 12:
            try:
                recent = divs[divs.index.tz_localize(None) >= (NOW - pd.Timedelta(days=365))]
            except (TypeError, AttributeError):
                recent = divs[divs.index >= (NOW - pd.Timedelta(days=365))]
            if len(recent) >= 4:
                hist_yield = recent.sum() / current_price * 100
                if hist_yield < best_yield * 0.5:
                    best_yield = round(hist_yield, 2)

    return best_yield


def compute_etf(ticker, existing_yield=None, existing_er=None):
    """Compute all metrics for one ETF ticker from yfinance price history."""
    try:
        etf = yf.Ticker(ticker)
        info = etf.info

        hist = etf.history(period="max")
        if hist.empty or len(hist) < 20:
            return None

        closes = hist["Close"]
        current_price = float(closes.iloc[-1])
        daily_returns = closes.pct_change().dropna()

        if len(daily_returns) < 60:
            return None

        # Yield — use pre-existing if available, else compute fresh
        if existing_yield and existing_yield < 50:
            current_yield = existing_yield
        else:
            current_yield = safe_div_yield(info, etf, current_price)

        # Sharpe
        excess = daily_returns - RISK_FREE / 252
        sharpe = round(float(excess.mean() / excess.std() * np.sqrt(252)), 2) if excess.std() > 0 else 0

        # Sortino
        downside = excess[excess < 0]
        sortino = round(float(excess.mean() / downside.std() * np.sqrt(252)), 2) if len(downside) > 0 and downside.std() > 0 else sharpe

        # Calmar
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(float(drawdown.min()))
        ann_ret = float(daily_returns.mean() * 252)
        calmar = round(ann_ret / max_dd, 2) if max_dd > 0 else 0

        # Total returns
        def calc_ret(days):
            if len(closes) < days:
                return None
            period = closes.iloc[-days:]
            start_p, end_p = float(period.iloc[0]), float(period.iloc[-1])
            divs = etf.dividends
            div_sum = 0
            if len(divs) > 0:
                try:
                    mask = (divs.index.tz_localize(None) >= period.index[0].tz_localize(None)) & \
                           (divs.index.tz_localize(None) <= period.index[-1].tz_localize(None))
                except (TypeError, AttributeError):
                    mask = (divs.index >= period.index[0]) & (divs.index <= period.index[-1])
                div_sum = divs[mask].sum()
            return round((end_p + div_sum) / start_p * 100 - 100, 2)

        ret_1yr = calc_ret(252)
        ret_3yr = calc_ret(756)
        ret_5yr = calc_ret(1260)
        ret_10yr = calc_ret(2520)

        # Beta & correlation vs S&P 500
        beta, corr = None, None
        try:
            spy = yf.Ticker("^GSPC")
            spy_hist = spy.history(period="max")["Close"]
            spy_ret = spy_hist.pct_change().dropna()
            common = daily_returns.index.intersection(spy_ret.index)
            if len(common) > 60:
                a_etf = daily_returns[common]
                a_spy = spy_ret[common]
                cov = np.cov(a_etf, a_spy)[0][1]
                var = np.var(a_spy)
                beta = round(cov / var, 2) if var > 0 else 1.0
                corr = round(float(np.corrcoef(a_etf, a_spy)[0][1]), 2)
        except Exception:
            pass

        # NAV annual change
        if len(daily_returns) > 252:
            nav = float((closes.iloc[-1] / closes.iloc[0]) ** (252 / len(daily_returns)) - 1) * 100
        else:
            nav = float(daily_returns.mean() * 252 * 100)
        nav = round(nav, 2)

        # Avg yield since inception
        divs = etf.dividends
        if len(divs) > 0 and len(closes) > 0:
            avg_p = float(closes.mean())
            years = (divs.index[-1] - divs.index[0]).days / 365.25
            if years > 0.1:
                avg_yy = round(float(divs.sum() / years / avg_p * 100), 2)
            else:
                avg_yy = current_yield
        else:
            avg_yy = current_yield

        # Dist coverage
        dc = round(1 + nav / max(current_yield or 1, 1), 2)

        # Available income
        nav_erosion = max(0, -nav / 100) if nav < 0 else 0
        avail = round(10000 * ((current_yield or 0) / 100 - nav_erosion), 0)

        # Growth of 10k
        days = min(252, len(closes))
        growth = round(10000 * float(closes.iloc[-1]) / float(closes.iloc[-days]), 0)

        # Price return 1yr
        if len(closes) >= 252:
            pr = round((float(closes.iloc[-1]) / float(closes.iloc[-252]) - 1) * 100, 2)
        else:
            pr = round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2)

        # Sharpe T12
        if len(daily_returns) >= 252:
            t12 = daily_returns.iloc[-252:]
            t12_ex = t12 - RISK_FREE / 252
            st12 = round(float(t12_ex.mean() / t12_ex.std() * np.sqrt(252)), 2) if t12_ex.std() > 0 else sharpe
        else:
            st12 = sharpe

        # Inception date from info
        inception = info.get("fundInceptionDate") or info.get("inceptionDate")
        if inception and isinstance(inception, (int, float)):
            inception = datetime.fromtimestamp(inception, tz=timezone.utc).strftime("%Y-%m-%d")

        return {
            "current_yield": current_yield,
            "avg_yield_since_inception": avg_yy,
            "distribution_coverage": dc,
            "sharpe_ratio": sharpe,
            "sharpe_t12": st12,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "total_return_1yr": ret_1yr,
            "total_return_3yr": ret_3yr,
            "total_return_5yr": ret_5yr,
            "total_return_10yr": ret_10yr,
            "price_return_1yr": pr,
            "beta_sp500": beta,
            "correlation_sp500": corr,
            "available_income_10k": avail,
            "growth_10k": growth,
            "nav_annual_change": nav,
            "inception_date": inception,
            "expense_ratio": round(info.get("netExpenseRatio"), 2) if info.get("netExpenseRatio") else None,
        }
    except Exception as e:
        print(f"  {ticker}: ERROR - {type(e).__name__}: {e}")
        return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", choices=["filtered", "all", "remaining"], default="filtered",
                        help="Which ETFs to compute: filtered=$2B+no-lev, all=everyone, remaining=those without metrics")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)

    # Determine which tickers to process
    if args.filter == "filtered":
        rows = conn.execute("""
            SELECT ticker, current_yield, expense_ratio
            FROM etf_universe
            WHERE (is_leveraged IS NULL OR is_leveraged = 0)
              AND (aum IS NOT NULL AND aum >= 2000)
              AND is_active = 1
              AND is_high_income = 0
            ORDER BY ticker
        """).fetchall()
    elif args.filter == "remaining":
        rows = conn.execute("""
            SELECT ticker, current_yield, expense_ratio
            FROM etf_universe
            WHERE (beta_sp500 IS NULL OR price_return_1yr IS NULL)
              AND is_active = 1
              AND is_high_income = 0
            ORDER BY ticker
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT ticker, current_yield, expense_ratio
            FROM etf_universe
            WHERE is_active = 1
              AND is_high_income = 0
            ORDER BY ticker
        """).fetchall()

    if args.limit > 0:
        rows = rows[:args.limit]

    print(f"Computing metrics for {len(rows)} universe ETFs...")
    updated = 0
    skipped = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_counter = 0

    for ticker, existing_yield, existing_er in rows:
        result = compute_etf(ticker, existing_yield, existing_er)
        if result is None:
            skipped += 1
            print(f"  {ticker}: skipped (no data)")
            continue

        # Build UPDATE
        set_clauses = []
        vals = []
        for key, val in result.items():
            if val is not None:
                set_clauses.append(f"{key} = ?")
                vals.append(val)

        set_clauses.append("last_updated = ?")
        vals.append(now_str)
        vals.append(ticker)

        sql = f"UPDATE etf_universe SET {', '.join(set_clauses)} WHERE ticker = ?"
        try:
            conn.execute(sql, vals)
            updated += 1
            commit_counter += 1
        except Exception as e:
            print(f"  {ticker}: DB error - {e}")
            skipped += 1
            continue

        y = result.get("current_yield")
        b = result.get("beta_sp500")
        s3 = result.get("total_return_3yr")
        print(f"  {ticker}: y={y}%  beta={b}  ret3y={s3}%")

        if commit_counter >= 50:
            conn.commit()
            commit_counter = 0

        time.sleep(args.delay)

    conn.commit()
    conn.close()
    print(f"\nDone! Updated {updated}, skipped {skipped}")


if __name__ == "__main__":
    main()
