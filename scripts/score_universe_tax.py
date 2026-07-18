#!/usr/bin/env python3
"""Apply category-based tax treatment and income stability scores to universe ETFs."""

import sqlite3

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"

CATEGORY_SCORES = {
    'Covered Call / Option Income': 0.15,
    'Equity / Dividend Growth': 0.85,
    'Preferred Stock': 0.80,
    'REIT': 0.15,
    'Bond / Fixed Income': 0.20,
    'MLP / Energy': 0.70,
    'Multi-Asset / Hybrid': 0.50,
    'Commodity': 0.30,
    'Crypto / Digital Asset': 0.15,
    'Treasury / Government': 0.25,
    'Muni / Tax-Free': 1.00,
    'International / Emerging': 0.60,
    'Buffered / Defined Outcome': 0.30,
    'Sector / Thematic': 0.50,
}

DEFAULT_TAX = 0.50
DEFAULT_STABILITY = 0.50


def classify_etf(name, ticker, category=None):
    """Classify an ETF into a category for heuristic scoring."""
    name = (name or '').upper()
    ticker = ticker.upper()

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

    # Check asset class from DB
    if category:
        cat_upper = category.upper()
        if 'BOND' in cat_upper:
            return 'Bond / Fixed Income'
        if 'REIT' in cat_upper or 'REAL' in cat_upper:
            return 'REIT'

    return 'Equity / Dividend Growth'


def main():
    conn = sqlite3.connect(DB_PATH)

    # Get all universe-only tickers missing tax score
    rows = conn.execute("""
        SELECT ticker, name, category
        FROM etf_universe
        WHERE tax_treatment_score IS NULL
          AND is_high_income = 0
          AND is_active = 1
        ORDER BY ticker
    """).fetchall()

    print(f"Applying scores to {len(rows)} universe ETFs...")
    tax_applied = 0
    stab_applied = 0

    for ticker, name, category in rows:
        cat = classify_etf(name, ticker, category)
        tax_score = CATEGORY_SCORES.get(cat, DEFAULT_TAX)
        
        conn.execute("UPDATE etf_universe SET tax_treatment_score = ? WHERE ticker = ?",
                     (tax_score, ticker))
        tax_applied += 1
        
        # Income stability: use a default of 0.5 for most, 
        # lower for volatile categories
        if cat in ('Covered Call / Option Income', 'Crypto / Digital Asset',
                    'Commodity', 'Sector / Thematic'):
            stab_score = 0.30
        elif cat in ('Bond / Fixed Income', 'Treasury / Government', 'Muni / Tax-Free'):
            stab_score = 0.70
        else:
            stab_score = DEFAULT_STABILITY
        
        conn.execute("UPDATE etf_universe SET income_stability_score = ? WHERE ticker = ?",
                     (stab_score, ticker))
        stab_applied += 1

        if ticker in ['VTI', 'AGG', 'EFA', 'QQQ', 'SPY', 'IWM', 'XLF', 'XLK', 'XLE']:
            print(f"  {ticker}: tax={tax_score}  stability={stab_score}  [{cat}]")

    conn.commit()
    conn.close()
    print(f"\nDone! Applied tax scores to {tax_applied}, stability scores to {stab_applied}")


if __name__ == "__main__":
    main()
