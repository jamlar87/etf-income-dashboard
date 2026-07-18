#!/usr/bin/env python3
"""
ETF Tax Treatment Scraper v2
Extracts qualified dividend percentages from fund provider tax supplement PDFs.
"""

import re
import sqlite3
import ssl
from urllib.request import urlopen, Request

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"


def parse_globalx(text):
    """
    Parse Global X 2024 Tax Supplement PDF text.
    Format: All data in one giant line with "Totals" rows for each fund.
    Each "Totals" row has the annual aggregate percentages at the end.
    The fund name and ticker appear on the row before "Totals".
    
    Columns (0-indexed positions from the header):
    [15]=QDI%  [16]=Income%  [17]=Income%  [18]=ROC%  [19]=Section199A%
    """
    results = {}
    
    # Find all "Totals " occurrences with their context
    # Format: "... Fund Name TICKER dates ... Totals $amounts ... % % % % %"
    # The ticker appears right before the dates in the line before Totals
    
    # Split on " Totals " to get segments
    # Each segment before "Totals" contains the fund data
    # The fund data row ends with: "Fund Name TICKER MM/DD/YYYY ... percentages"
    
    # Pattern to find fund lines (not Totals lines) that have tickers and 
    # percentages, then the subsequent "Totals" line
    # Simpler: find all percentage clusters at line endings
    lines = text.split('Totals ')
    
    for i, segment in enumerate(lines):
        if i == 0:
            continue  # Skip the header text before first "Totals"
        
        # The segment starts right after "Totals" and looks like:
        # "$money $money ... $money XX.XX% XX.XX% XX.XX% XX.XX% XX.XX%"
        # The line BEFORE "Totals" has the fund name and ticker
        prev_line = lines[i-1]
        
        # Find ticker in previous segment - look for pattern:
        # "Fund Name TICKER MM/DD/YYYY" at end of prev segment
        ticker_match = re.search(r'([A-Z]{2,6})\s+\d{2}/\d{2}/\d{4}\s', prev_line)
        if not ticker_match:
            continue
        
        ticker = ticker_match.group(1)
        
        # Extract the 5 percentage values from the "Totals" line
        # The percentages are at the end: XX.XX% XX.XX% XX.XX% XX.XX% XX.XX%
        pcts = re.findall(r'(\d+\.?\d*)%', segment)
        
        if len(pcts) >= 5:
            qdi_pct = float(pcts[0])     # Qualified Dividend Income %
            inc1_pct = float(pcts[1])     # Income % 
            inc2_pct = float(pcts[2])     # Income %
            roc_pct = float(pcts[3])      # Return of Capital %
            sec199a_pct = float(pcts[4])  # Section 199A %
            
            # Score: QDI + ROC*0.5 (ROC is tax-deferred)
            score = min(1.0, (qdi_pct + roc_pct * 0.5) / 100.0)
            
            if ticker not in results:
                results[ticker] = {
                    'qdi_pct': qdi_pct,
                    'roc_pct': roc_pct,
                    'score': round(score, 3)
                }
    
    return results


def parse_jpmorgan(text):
    """
    Parse JPMorgan 2024 Distribution Notice PDF.
    Similar format to Global X but slightly different column layout.
    """
    results = {}
    # JPMorgan format usually has ticker and qualified dividend info
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Look for ticker patterns followed by qualified dividend info
        ticker_match = re.search(r'\b([A-Z]{2,6})\b.*?(\d+\.?\d*)%.*?Qualified', line, re.IGNORECASE)
        if ticker_match:
            ticker = ticker_match.group(1)
            qdi_pct = float(ticker_match.group(2))
            score = min(1.0, qdi_pct / 100.0)
            results[ticker] = {'qdi_pct': qdi_pct, 'roc_pct': 0, 'score': round(score, 3)}
    return results


# ──────────────────────────────────────────────
# Category-based heuristic scoring
# ──────────────────────────────────────────────
# For providers/funds where we don't have actual tax data, 
# assign scores based on the fund's investment strategy category
CATEGORY_SCORES = {
    'Covered Call / Option Income': 0.15,  # Mostly non-qualified (options = ordinary income)
    'Equity / Dividend Growth': 0.85,       # Mostly qualified dividends
    'Preferred Stock': 0.80,                 # Qualified dividend income
    'REIT': 0.15,                            # Mostly non-qualified, some ROC
    'Bond / Fixed Income': 0.20,             # Ordinary income
    'MLP / Energy': 0.70,                    # Often has return of capital (tax-deferred)
    'Multi-Asset / Hybrid': 0.50,            # Mixed
    'Commodity': 0.30,                       # Complex, often non-qualified
    'Crypto / Digital Asset': 0.15,          # Mostly non-qualified
    'Treasury / Government': 0.25,           # Taxable ordinary income
    'Muni / Tax-Free': 1.00,                 # Tax-exempt (best tax treatment)
    'International / Emerging': 0.60,        # Often foreign tax credits
    'Buffered / Defined Outcome': 0.30,      # Options-based, mixed
    'Sector / Thematic': 0.50,               # Varies widely
}

def classify_etf(name, ticker):
    """Classify an ETF into a category for heuristic scoring."""
    name = (name or '').upper()
    ticker = ticker.upper()
    
    # Check for specific strategy keywords
    if any(kw in name for kw in ['COVERED CALL', 'OPTION INCOME', 'PUTWRITE', 
                                   'BUYWRITE', 'PREMIUM INCOME', 'PUT WRITE',
                                   'INCOME EDGE']):
        return 'Covered Call / Option Income'
    if any(kw in name for kw in ['TREASURY', 'TREASURY BOND', 'GOVERNMENT BOND',
                                   'TREASURY BILL', 'T-BILL', 'TREASURY INCOME']):
        return 'Treasury / Government'
    if any(kw in name for kw in ['BOND', 'FIXED INCOME', 'CORPORATE BOND', 
                                   'HIGH YIELD BOND', 'CREDIT']):
        return 'Bond / Fixed Income'
    if any(kw in name for kw in ['REIT', 'REAL ESTATE', 'MORTGAGE']):
        return 'REIT'
    if any(kw in name for kw in ['MLP', 'MIDSTREAM', 'ENERGY', 'OIL', 'GAS',
                                   'NATURAL RESOURCE']):
        return 'MLP / Energy'
    if any(kw in name for kw in ['BITCOIN', 'ETHEREUM', 'CRYPTO', 'BLOCKCHAIN',
                                   'DIGITAL']):
        return 'Crypto / Digital Asset'
    if any(kw in name for kw in ['MUNI', 'MUNICIPAL', 'TAX-FREE', 'TAX EXEMPT',
                                   'NATIONAL MUNI']):
        return 'Muni / Tax-Free'
    if any(kw in name for kw in ['PREFERRED', 'PFD', 'PREF']):
        return 'Preferred Stock'
    if any(kw in name for kw in ['DIVIDEND', 'QUALITY DIVIDEND', 'DIVIDEND GROWTH',
                                   'DIVIDEND ARISTOCRAT', 'BUYBACK']):
        return 'Equity / Dividend Growth'
    if any(kw in name for kw in ['BUFFER', 'DEFINED OUTCOME', 'HEDGED', 'FLEX',
                                   'RISK MANAGED', 'MANAGED VOLATILITY', 'POWERED']):
        return 'Buffered / Defined Outcome'
    if any(kw in name for kw in ['COMMODITY', 'GOLD', 'SILVER', 'COPPER', 'URANIUM',
                                   'METAL']):
        return 'Commodity'
    if any(kw in name for kw in ['INTERNATIONAL', 'EMERGING', 'GLOBAL EX US', 
                                   'DEVELOPED MARKET', 'FOREIGN']):
        return 'International / Emerging'
    if any(kw in name for kw in ['SECTOR', 'THEMATIC', 'TECHNOLOGY', 'HEALTHCARE',
                                   'FINANCIAL', 'CONSUMER', 'INDUSTRIAL']):
        return 'Sector / Thematic'
    if any(kw in name for kw in ['MULTI', 'HYBRID', 'BALANCED', 'ALLOCATION',
                                   'FLEXIBLE', 'TOTAL RETURN']):
        return 'Multi-Asset / Hybrid'
    
    # Default: check provider
    return 'Equity / Dividend Growth'


def apply_category_scores():
    """Apply category-based heuristic scores to unscored ETFs."""
    conn = sqlite3.connect(DB_PATH)
    unscored = conn.execute(
        "SELECT ticker, name, provider FROM etfs WHERE tax_treatment_score IS NULL"
    ).fetchall()
    
    applied = 0
    for ticker, name, provider in unscored:
        cat = classify_etf(name, ticker)
        score = CATEGORY_SCORES[cat]
        conn.execute(
            "UPDATE etfs SET tax_treatment_score = ? WHERE ticker = ?",
            (score, ticker)
        )
        conn.commit()
        applied += 1
        cat_label = cat.replace('Covered Call / Option Income', '⚡Option').replace('Equity / Dividend Growth', '📈Equity')
        print(f"  ~ {ticker}: score={score:.2f} [{cat}]")
    
    conn.close()
    print(f"\n  Category-based scores applied to {applied} ETFs")
    return applied


def fetch_text(url, timeout=30):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    with urlopen(req, context=ctx, timeout=timeout) as resp:
        data = resp.read()
        try:
            return data.decode('utf-8')
        except:
            return data.decode('latin-1')


def save_scores(ticker_scores, source_name=""):
    if not ticker_scores:
        print(f"  [SKIP] No scores from {source_name}")
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    saved = 0
    for ticker, info in sorted(ticker_scores.items()):
        score = info['score']
        qdi = info['qdi_pct']
        before = conn.execute("SELECT tax_treatment_score FROM etfs WHERE ticker = ?", (ticker,)).fetchone()
        conn.execute(
            "UPDATE etfs SET tax_treatment_score = ? WHERE ticker = ?",
            (score, ticker)
        )
        conn.commit()
        saved += 1
        prev = " (was " + str(round(before[0], 3)) + ")" if before and before[0] is not None else ""
        print(f"  ✓ {ticker}: score={score:.3f} (QDI={qdi:.1f}%){prev}")
    
    conn.close()
    return saved


def fetch_and_parse_globalx():
    """Fetch Global X PDF and parse it."""
    print("\n--- Source: Global X 2024 Tax Supplement ---")
    
    # Try cached file first
    try:
        with open('/home/james/.hermes/cache/web/cms-stage-cdn.globalxetfs.com-fa17e5fac2.md', 'r') as f:
            text = f.read()
        scores = parse_globalx(text)
        print(f"  Found {len(scores)} Global X ETFs from cached data")
        saved = save_scores(scores, "Global X")
        return saved
    except FileNotFoundError:
        pass
    
    # Fallback: fetch directly
    try:
        text = fetch_text("https://cms-stage-cdn.globalxetfs.com/2024-Year-End-Tax-Supplement-Global-X-ETFs.pdf")
        scores = parse_globalx(text)
        print(f"  Found {len(scores)} Global X ETFs")
        return save_scores(scores, "Global X")
    except Exception as e:
        print(f"  ERROR fetching Global X PDF: {e}")
        return 0


def main():
    print("=" * 60)
    print("ETF TAX TREATMENT SCRAPER v2")
    print("=" * 60)
    
    total_saved = fetch_and_parse_globalx()
    
    # Apply category-based heuristic scores for remaining unscored ETFs
    print("\n--- Category-based Heuristic Scoring ---")
    cat_saved = apply_category_scores()
    
    # Show summary
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT COUNT(*) FROM etfs WHERE tax_treatment_score IS NOT NULL"
    ).fetchone()[0]
    unscored = conn.execute(
        "SELECT COUNT(*) FROM etfs WHERE tax_treatment_score IS NULL"
    ).fetchone()[0]
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"Scored this run: {total_saved}")
    print(f"Total scored ETFs: {rows}")
    print(f"Remaining unscored: {unscored}")
    print(f"{'='*60}")
    
    # Show detailed list
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT ticker, name, provider, tax_treatment_score 
           FROM etfs 
           WHERE tax_treatment_score IS NOT NULL 
           ORDER BY tax_treatment_score DESC"""
    ).fetchall()
    conn.close()
    
    if rows:
        print(f"\nScored ETFs by score (highest first):")
        print(f"{'Ticker':<8} {'Score':<7} {'Provider':<22} {'Name'}")
        print("-" * 75)
        for r in rows:
            ticker, name, provider, score = r
            provider = (provider or '')[:22]
            name = (name or '')[:40]
            print(f"{ticker:<8} {score:<7.3f} {provider:<22} {name}")
    
    return rows


if __name__ == "__main__":
    main()
