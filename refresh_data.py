#!/usr/bin/env python3
"""Live ETF data refresh via yfinance — pulls real metrics for high-yield ETFs.
Run daily via cron. Uses finance venv.
v2: fixed yield calc, timezone handling, DB schema.
"""
import sqlite3
import sys
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "etfs.db")
if not os.path.exists(os.path.dirname(DB_PATH)):
    DB_PATH = _LOCAL_DB
RISK_FREE = 0.045
MAX_WORKERS = 8
NOW = pd.Timestamp.now(tz="America/New_York")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_tickers():
    conn = get_db()
    rows = conn.execute("SELECT ticker FROM etfs ORDER BY ticker").fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def safe_div_yield(info, etf, current_price):
    """Calculate current dividend yield from yfinance info or dividend history."""
    best_yield = None

    # Try all yfinance sources first
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
        # Fall back: compute from trailing 12 months of dividends
        divs = etf.dividends
        if len(divs) > 0:
            year_ago = NOW - pd.Timedelta(days=365)
            recent = divs[divs.index >= year_ago] if len(divs[divs.index >= year_ago]) > 0 else divs.iloc[-12:]
            if len(recent) > 0:
                best_yield = recent.sum() / current_price * 100

    if best_yield is None:
        return None

    best_yield = round(best_yield, 2)

    # SANITY CHECK: If yield > 50%, cross-verify against actual dividend history
    # to catch bad yfinance data for traditional dividend ETFs
    if best_yield > 50 and current_price:
        divs = etf.dividends
        if len(divs) >= 12:
            # Compute yield from actual trailing 12 months of dividends
            recent = divs[divs.index >= (NOW - pd.Timedelta(days=365))]
            if len(recent) >= 4:
                hist_yield = recent.sum() / current_price * 100
                # If historical calc shows much lower, it's a data error — trust history
                if hist_yield < best_yield * 0.5:
                    best_yield = round(hist_yield, 2)

    return best_yield


def fetch_ticker_data(ticker):
    """Fetch and compute metrics for one ticker."""
    try:
        etf = yf.Ticker(ticker)
        info = etf.info

        hist = etf.history(period="max")
        if hist.empty or len(hist) < 20:
            print(f"  {ticker}: insufficient history ({len(hist)} days)")
            return None

        closes = hist["Close"]
        current_price = float(closes.iloc[-1])
        daily_returns = closes.pct_change().dropna()

        if len(daily_returns) < 60:
            print(f"  {ticker}: too few returns ({len(daily_returns)})")
            return None

        # Yield
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

        inception = info.get("fundInceptionDate") or info.get("inceptionDate")
        if inception and isinstance(inception, (int, float)):
            inception = datetime.fromtimestamp(inception).strftime("%Y-%m-%d")

        print(f"  {ticker}: y={current_yield}%, sh={sharpe}, nav={nav}%, beta={beta}")

        return {
            "ticker": ticker,
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
        }
    except Exception as e:
        print(f"  {ticker}: ERROR - {type(e).__name__}: {e}")
        return None


def update_database(results):
    conn = get_db()
    updated = 0
    for r in results:
        if r is None:
            continue
        ticker = r.pop("ticker")
        inception = r.pop("inception_date", None)

        set_parts = []
        values = []
        for k, v in r.items():
            if v is not None:
                set_parts.append(f"{k} = ?")
                values.append(v)

        if inception:
            set_parts.append("inception_date = ?")
            values.append(inception)

        if set_parts:
            set_parts.append("last_updated = datetime('now')")
            values.append(ticker)
            sql = f"UPDATE etfs SET {', '.join(set_parts)} WHERE ticker = ?"
            conn.execute(sql, values)
            updated += 1

    conn.commit()
    conn.close()
    print(f"\nUpdated {updated} ETFs with live data.")


def main():
    tickers = get_all_tickers()
    print(f"Fetching live data for {len(tickers)} ETFs ({MAX_WORKERS} workers, {NOW.date()})...\n")

    results = []
    good, bad = 0, 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_ticker_data, t): t for t in tickers}
        for f in as_completed(futures):
            t = futures[f]
            try:
                r = f.result(timeout=60)
                if r:
                    good += 1
                else:
                    bad += 1
                results.append(r)
            except Exception as e:
                print(f"  {t}: TIMEOUT - {e}")
                bad += 1
                results.append(None)

    print(f"\nDone. {good} ok, {bad} failed.")
    update_database([r for r in results if r is not None])

    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM etfs WHERE nav_annual_change IS NOT NULL").fetchone()[0]
    conn.close()
    print(f"ETFs with live data: {count}/{len(tickers)}")


if __name__ == "__main__":
    main()
