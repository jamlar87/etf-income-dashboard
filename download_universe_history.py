#!/usr/bin/env python3
"""Download/extend monthly price history for filtered universe ETFs (~600 tickers).
Runs incrementally — existing rows are skipped (INSERT OR IGNORE)."""
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
    """Return tickers from filtered universe (incremental — all with price history)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT u.ticker
        FROM etf_universe u
        INNER JOIN price_history p ON u.ticker = p.ticker
        WHERE u.is_active = 1
          AND (u.is_leveraged IS NULL OR u.is_leveraged = 0)
          AND u.aum IS NOT NULL AND u.aum >= 2000
        ORDER BY u.aum DESC
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


def download_ticker(ticker):
    """Download monthly close + dividends (max period). Return list of rows or None."""
    try:
        etf = yf.Ticker(ticker)
        hist = etf.history(period="max", interval="1mo")
        if hist.empty or hist["Close"].isna().all():
            # Fallback: daily -> monthly resample
            daily = etf.history(period="max", interval="1d")
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
            dt = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
            date_str = dt.strftime("%Y-%m-01")
            close = float(row["Close"]) if pd.notna(row["Close"]) else None
            div = float(row.get("Dividends", 0) or 0)
            if close is not None and close == close:
                rows.append((ticker, date_str, close, div))

        if rows:
            print(f"  {ticker}: {len(rows)} months ({rows[0][1]} to {rows[-1][1]})")
        return rows
    except Exception as e:
        print(f"  {ticker}: ERROR - {e}")
        return None


def store_batch(conn, all_rows):
    """Insert rows with INSERT OR IGNORE (safety for duplicates)."""
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
    print(f"Extending history for {len(tickers)} tickers (period=max, incremental)...\n")

    conn = get_db()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    total_stored = 0
    good = 0
    failed = 0

    for batch_start in range(0, len(tickers), BATCH_SIZE):
        batch = tickers[batch_start:batch_start + BATCH_SIZE]
        print(f"\n--- Batch {batch_start // BATCH_SIZE + 1}: {batch[0]}..{batch[-1]} ({len(batch)} tickers) ---")

        batch_rows = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(download_ticker, t): t for t in batch}
            for f in as_completed(futures):
                t = futures[f]
                try:
                    rows = f.result(timeout=120)
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
        print(f"  → Batch: {stored} new rows. Total: {total_stored} rows added")

    conn.close()

    # Final summary
    conn2 = get_db()
    r = conn2.execute(
        "SELECT COUNT(DISTINCT ticker) as t, COUNT(*) as n, MAX(date) as latest FROM price_history"
    ).fetchone()
    conn2.close()
    print(f"\n{'='*50}")
    print(f"Done. {good} tickers extended, {failed} failed.")
    print(f"DB now: {r[0]} tickers, {r[1]} rows, latest: {r[2]}")


if __name__ == "__main__":
    main()
