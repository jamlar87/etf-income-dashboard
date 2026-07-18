#!/usr/bin/env python3
"""Enrich etf_universe with yfinance data — yield, NAV, expense, leverage detection."""

import sqlite3
import sys
import time
import yfinance as yf
from datetime import datetime, timezone

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"

# Leverage/inverse/bear keywords in name or category
LEVERAGE_KEYWORDS = [
    "2X", "3X", "2X LONG", "3X LONG", "BULL", "BEAR", "SHORT",
    "ULTRA", "LEVERAGED", "INVERSE", "2X LEVERAGE", "3X LEVERAGE",
    "DAILY TARGET", "TRADR", "T-REX", "2X DAILY", "1X SHORT",
    "DAILY 2X", "DAILY 3X", "2X BULL", "3X BULL", "2X SHORT",
]

def is_leveraged(name, category):
    """Detect leveraged/inverse funds from name and category."""
    text = f"{name or ''} {category or ''}".upper()
    for kw in LEVERAGE_KEYWORDS:
        if kw in text:
            return True
    return False

def enrich_ticker(ticker):
    """Fetch key metrics for one ticker via yfinance."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        if not info:
            return None
        
        name = info.get("longName") or info.get("shortName") or ""
        category = info.get("category") or ""
        provider = info.get("fundFamily") or ""
        
        # Inception date
        inception = info.get("fundInceptionDate") or info.get("inceptionDate")
        if inception and isinstance(inception, (int, float)):
            inception = datetime.fromtimestamp(inception, tz=timezone.utc).strftime("%Y-%m-%d")
        
        expense_ratio = info.get("netExpenseRatio")
        if expense_ratio is not None:
            expense_ratio = round(expense_ratio, 2)  # Already in percent form (e.g. 0.35 = 0.35%)
        
        # Yield from info (unreliable — will be refined by refresh script)
        current_yield = info.get("dividendYield")
        if current_yield is not None and current_yield < 1:
            current_yield = round(current_yield * 100, 2)
        elif current_yield is not None and current_yield > 1:
            current_yield = round(current_yield, 2)
        
        # Detect leveraged
        leveraged = is_leveraged(name, category)
        
        # Returns & risk from info
        ret_1yr = info.get("totalReturn1Year") or info.get("return1Year")
        if ret_1yr is not None:
            ret_1yr = round(ret_1yr * 100, 2)
        
        beta = info.get("beta")
        if beta is not None:
            beta = round(beta, 2)
        
        return {
            "ticker": ticker,
            "name": name,
            "category": category,
            "provider": provider,
            "inception_date": inception,
            "expense_ratio": expense_ratio,
            "current_yield": current_yield,
            "total_return_1yr": ret_1yr,
            "beta_sp500": beta,
            "is_leveraged": 1 if leveraged else 0,
        }
    except Exception as e:
        return None

def main(batch_size=50, delay=0.3):
    conn = sqlite3.connect(DB_PATH)
    
    # Get un-enriched or outdated tickers (scraped but no expense_ratio yet)
    rows = conn.execute("""
        SELECT ticker, name FROM etf_universe 
        WHERE expense_ratio IS NULL OR is_leveraged IS NULL
        ORDER BY is_high_income DESC, ticker
        LIMIT ?
    """, (batch_size * 4,)).fetchall()
    
    if not rows:
        print("No un-enriched tickers found")
        conn.close()
        return
    
    print(f"Enriching {len(rows)} tickers...")
    updated = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for ticker, scraped_name in rows:
        result = enrich_ticker(ticker)
        if result is None:
            print(f"  {ticker}: skipped (no data)")
            continue
        
        updates = []
        vals = []
        for key in ["name", "category", "provider", "inception_date", 
                     "expense_ratio", "current_yield", "total_return_1yr",
                     "beta_sp500", "is_leveraged"]:
            val = result.get(key)
            if val is not None:
                updates.append(f"{key} = ?")
                vals.append(val)
        
        if updates:
            updates.append("last_updated = ?")
            vals.append(now)
            vals.append(ticker)
            sql = f"UPDATE etf_universe SET {', '.join(updates)} WHERE ticker = ?"
            conn.execute(sql, vals)
            updated += 1
        
        print(f"  {ticker}: yield={result.get('current_yield', '?')}%, "
              f"ER={result.get('expense_ratio', '?')}%, "
              f"leveraged={'Y' if result.get('is_leveraged') else 'N'}")
        
        time.sleep(delay)
    
    conn.commit()
    still_null = conn.execute(
        "SELECT COUNT(*) FROM etf_universe WHERE expense_ratio IS NULL AND is_active = 1"
    ).fetchone()[0]
    conn.close()
    print(f"\nUpdated {updated}/{len(rows)} tickers")
    print(f"Still un-enriched: {still_null}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=50)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()
    main(batch_size=args.batch, delay=args.delay)
