#!/usr/bin/env python3
"""Download monthly price history for filtered universe ETFs (~600 tickers).
Batch-commits every 50 tickers to survive mid-run kills."""
import sqlite3
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
MAX_WORKERS = 10
BATCH_SIZE = 50


def get_db():
    return sqlite3.connect(DB_PATH)


def get_tickers_to_download():
    """Return tickers from filtered universe that lack price history."""
    conn = get_db()
    rows = conn.execute("""
        SELECT u.ticker
        FROM etf_universe u
        LEFT JOIN etfs e ON u.ticker = e.ticker
        WHERE u.is_active = 1
          AND (u.is_leveraged IS NULL OR u.is_leveraged = 0)
          AND u.aum IS NOT NULL AND u.aum >= 2000
          AND (COALESCE(e.expense_ratio, u.expense_ratio) IS NULL
               OR COALESCE(e.expense_ratio, u.expense_ratio) <= 3.0)
          AND u.ticker NOT IN (SELECT ticker FROM price_history)
        ORDER BY u.aum DESC
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


def download_ticker(ticker):
    """Download monthly close + dividends. Returns list of rows or None."""
    try:
        hist = yf.Ticker(ticker).history(period="5y", interval="1mo")
        if hist.empty or hist["Close"].isna().all():
            # Fallback: daily aggregation
            daily = yf.Ticker(ticker).history(period="5y", interval="1d")
            if daily.empty:
                return None
            hist = daily.resample("ME").agg({
                "Close": "last",
                "Dividends": "sum",
            }).dropna(subset=["Close"])

        if hist.empty:
            return None

        rows = []
        for idx, row in hist.iterrows():
            close = float(row["Close"]) if pd.notna(row["Close"]) else None
            div = float(row.get("Dividends", 0) or 0)
            if close is not None and close == close:  # not NaN
                rows.append((ticker, idx.strftime("%Y-%m-%d"), close, div))

        if rows:
            print(f"  {ticker}: {len(rows)} months")
        return rows
    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")
        return None


def store_batch(conn, all_rows):
    """Insert all collected rows, commit, return count."""
    total = 0
    for ticker_rows in all_rows:
        if not ticker_rows:
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
    return total


def main():
    tickers = get_tickers_to_download()
    print(f"Filtered universe: {len(tickers)} tickers need price history download")

    if not tickers:
        print("All tickers already have history. Nothing to do.")
        return

    conn = get_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    total_stored = 0
    good = 0
    failed = 0

    # Process in batches
    for batch_start in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[batch_start:batch_start + BATCH_SIZE]
        print(f"\n--- Batch {batch_start // BATCH_SIZE + 1}: {batch[0]}..{batch[-1]} ({len(batch)} tickers) ---")

        batch_rows = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(download_ticker, t): t for t in batch}
            for f in as_completed(futures):
                t = futures[f]
                try:
                    rows = f.result(timeout=90)
                    if rows:
                        good += 1
                        batch_rows.append(rows)
                    else:
                        failed += 1
                except Exception as e:
                    print(f"  {t}: TIMEOUT - {e}")
                    failed += 1
                    batch_rows.append(None)

        stored = store_batch(conn, batch_rows)
        total_stored += stored
        progress = f"  → Batch complete: {stored} rows stored. Total: {total_stored} rows, {good} good, {failed} failed"
        print(progress)

    conn.close()

    # Final summary
    conn2 = get_db()
    r = conn2.execute(
        "SELECT COUNT(DISTINCT ticker) as t, COUNT(*) as n, MAX(date) as latest FROM price_history"
    ).fetchone()
    print(f"\n{'='*50}")
    print(f"Done. {good} succeeded, {failed} failed, {total_stored} total rows stored.")
    print(f"DB now: {r[0]} tickers, {r[1]} rows, latest: {r[2]}")
    conn2.close()


if __name__ == "__main__":
    main()
