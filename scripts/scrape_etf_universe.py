#!/usr/bin/env python3
"""Scrape all ~5,500 ETFs from StockAnalysis.com into etf_universe table."""

import sqlite3
import re
import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
BASE_URL = "https://stockanalysis.com/etf/"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def parse_aum(text):
    """Convert '1.23B' -> 1230, '456M' -> 456, '--' or '' -> None"""
    text = (text or "").strip().replace(",", "")
    if not text or text == "-":
        return None
    if text.endswith("B"):
        return round(float(text[:-1]) * 1000, 2)
    elif text.endswith("M"):
        return round(float(text[:-1]), 2)
    elif text.endswith("K"):
        return round(float(text[:-1]) / 1000, 3)
    elif text.endswith("T"):
        return round(float(text[:-1]) * 1_000_000, 2)
    try:
        return round(float(text), 2)
    except:
        return None

def scrape_page(page):
    url = BASE_URL if page == 1 else f"{BASE_URL}?page={page}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Find the ETF table rows
    rows = soup.select("table tr")
    if not rows:
        # Try direct tr selection
        rows = soup.find_all("tr")
    
    etfs = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        
        # Symbol is in first td as a link
        link = cells[0].find("a") if cells[0] else None
        if not link:
            continue
        
        ticker = link.get_text(strip=True).upper()
        name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        asset_class = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        aum_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        aum = parse_aum(aum_text)
        
        if ticker and name:
            etfs.append((ticker, name, asset_class, aum))
    
    # Check if there's a "next page" indicator
    has_next = soup.select_one("a[rel='next']") or "Next" in resp.text
    
    return etfs, bool(has_next)

def main():
    conn = sqlite3.connect(DB_PATH)
    
    # Create universe table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS etf_universe (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            asset_class TEXT,
            aum REAL,
            is_high_income INTEGER DEFAULT 0,
            is_leveraged INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            category TEXT,
            provider TEXT,
            inception_date TEXT,
            expense_ratio REAL,
            current_yield REAL,
            nav_annual_change REAL,
            total_return_1yr REAL,
            sharpe_ratio REAL,
            distribution_coverage REAL,
            tax_treatment_score REAL,
            income_stability_score REAL,
            source TEXT DEFAULT 'stockanalysis',
            last_updated TEXT
        )
    """)
    conn.commit()
    
    # Mark existing high-income ETFs
    existing = set(r[0] for r in conn.execute("SELECT ticker FROM etfs").fetchall())
    
    total = 0
    page = 1
    
    while True:
        try:
            etfs, has_next = scrape_page(page)
        except Exception as e:
            print(f"Page {page}: ERROR - {e}", file=sys.stderr)
            break
        
        if not etfs:
            print(f"Page {page}: empty, stopping")
            break
        
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        for ticker, name, asset_class, aum in etfs:
            is_hi = 1 if ticker in existing else 0
            conn.execute("""
                INSERT INTO etf_universe (ticker, name, asset_class, aum, is_high_income, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    name=excluded.name,
                    asset_class=excluded.asset_class,
                    aum=excluded.aum,
                    is_high_income=MAX(is_high_income, excluded.is_high_income),
                    last_updated=excluded.last_updated
            """, (ticker, name, asset_class, aum, is_hi, now))
        
        total += len(etfs)
        print(f"Page {page}: {len(etfs)} ETFs (total: {total})")
        
        if not has_next or page >= 200:
            break
        
        page += 1
        time.sleep(1)  # Be polite
    
    conn.commit()
    conn.close()
    print(f"\nDone! Scraped {total} ETFs across {page} pages")

if __name__ == "__main__":
    main()
