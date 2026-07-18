#!/usr/bin/env python3
"""Download monthly price history for ETFs — incremental mode.
Only fetches data newer than what's already stored.
"""
import sqlite3
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "etfs.db")
if not os.path.exists(os.path.dirname(DB_PATH)):
    DB_PATH = _LOCAL_DB
MAX_WORKERS = 8


def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn


def get_last_dates():
    """Return {ticker: latest_date} for all tickers, or None if no history."""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT ticker, MAX(date) as last_date FROM price_history GROUP BY ticker
    """).fetchall()
    conn.close()
    return {r["ticker"]: r["last_date"] for r in rows}


def get_all_tickers():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT ticker FROM etfs ORDER BY ticker").fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def download_incremental(ticker, last_date):
    """Download only months newer than last_date. Falls back to full if no last_date."""
    try:
        etf = yf.Ticker(ticker)

        if last_date:
            # Parse as timezone-aware to match yfinance's tz-aware index
            start = pd.Timestamp(last_date, tz="America/New_York") - pd.Timedelta(days=45)
            hist = etf.history(start=start.strftime("%Y-%m-%d"), interval="1mo")
        else:
            hist = etf.history(period="max", interval="1mo")

        if hist.empty:
            return None

        # Filter to strictly newer than last_date
        if last_date:
            cutoff = pd.Timestamp(last_date, tz="America/New_York")
            hist = hist[hist.index > cutoff]

        if hist.empty:
            return None  # No new data

        rows = []
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close = float(row["Close"])
            div = float(row.get("Dividends", 0) or 0)
            if close and close == close:  # not NaN
                rows.append((ticker, date_str, close, div))

        if rows:
            tag = "new" if last_date else "FULL"
            print(f"  {ticker}: {len(rows)} months ({tag})")
        return rows
    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")
        return None


def store_incremental(all_rows):
    """INSERT OR IGNORE new rows."""
    conn = get_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    total = 0
    for ticker_rows in all_rows:
        if ticker_rows is None:
            continue
        valid = [(t, d, c, dv) for t, d, c, dv in ticker_rows
                 if c is not None and not (isinstance(c, float) and c != c)]
        if not valid:
            continue
        conn.executemany(
            "INSERT OR IGNORE INTO price_history (ticker, date, close, dividend) VALUES (?, ?, ?, ?)",
            valid
        )
        total += len(valid)
    conn.commit()
    conn.close()
    return total


def main():
    tickers = get_all_tickers()
    last_dates = get_last_dates()
    has_history = len(last_dates)

    if has_history > 0:
        print(f"Incremental mode: {has_history} tickers have history, fetching new months only...\n")
    else:
        print(f"Full download: no existing history, fetching all for {len(tickers)} tickers...\n")

    tasks = []
    for t in tickers:
        last = last_dates.get(t)
        tasks.append((t, last))

    all_rows = []
    good, bad, skipped = 0, 0, 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(download_incremental, t, last): t for t, last in tasks}
        for f in as_completed(futures):
            t = futures[f]
            try:
                rows = f.result(timeout=60)
                if rows:
                    good += 1
                    all_rows.append(rows)
                else:
                    skipped += 1  # No new data = good
                    all_rows.append(None)
            except Exception as e:
                print(f"  {t}: TIMEOUT - {e}")
                bad += 1
                all_rows.append(None)

    count = store_incremental(all_rows)
    print(f"\n{good} new, {skipped} up-to-date, {bad} failed. Stored {count} new rows.")

    conn = get_db()
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT COUNT(DISTINCT ticker) as t, COUNT(*) as n, MAX(date) as latest FROM price_history").fetchone()
    print(f"DB now: {r['t']} tickers, {r['n']} rows, latest: {r['latest']}")
    conn.close()


if __name__ == "__main__":
    main()
