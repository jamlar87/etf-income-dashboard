"""ETF Database - Seed script with 135 high-yield income ETFs"""
import sqlite3
import os
from datetime import datetime, timedelta
import random
import math

DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
_LOCAL_DB = os.path.join(os.path.dirname(__file__), "data", "etfs.db")
if not os.path.exists(os.path.dirname(DB_PATH)):
    DB_PATH = _LOCAL_DB

random.seed(42)  # Reproducible "random" data

# Real ETF data with ticker, name, provider, category, inception date
ETFS = [
    # === NEOS ===
    ("SPYI", "NEOS S&P 500 High Income ETF", "NEOS", "Covered Call", "2022-08-30"),
    ("QQQI", "NEOS Nasdaq 100 High Income ETF", "NEOS", "Covered Call", "2024-01-23"),
    ("IWMI", "NEOS Russell 2000 High Income ETF", "NEOS", "Covered Call", "2024-03-19"),
    ("BTCI", "NEOS Bitcoin High Income ETF", "NEOS", "Crypto", "2024-06-18"),
    ("NEHI", "NEOS Ethereum High Income ETF", "NEOS", "Crypto", "2024-09-24"),
    ("BNDI", "NEOS Enhanced Income Aggregate Bond ETF", "NEOS", "Bond", "2023-04-18"),
    ("CSHI", "NEOS Enhanced Income 1-3 Month T-Bill ETF", "NEOS", "Bond", "2023-03-21"),

    # === JP Morgan ===
    ("JEPI", "JPMorgan Equity Premium Income ETF", "J.P. Morgan", "Covered Call", "2020-05-20"),
    ("JEPQ", "JPMorgan Nasdaq Equity Premium Income ETF", "J.P. Morgan", "Covered Call", "2022-05-03"),
    ("JEPY", "JPMorgan Premium Income ETF", "J.P. Morgan", "Covered Call", "2024-09-10"),

    # === Global X ===
    ("QYLD", "Global X Nasdaq 100 Covered Call ETF", "Global X", "Covered Call", "2013-12-12"),
    ("XYLD", "Global X S&P 500 Covered Call ETF", "Global X", "Covered Call", "2013-06-21"),
    ("RYLD", "Global X Russell 2000 Covered Call ETF", "Global X", "Covered Call", "2019-04-16"),
    ("QYLG", "Global X Nasdaq 100 Covered Call & Growth ETF", "Global X", "Covered Call", "2020-09-01"),
    ("XYLG", "Global X S&P 500 Covered Call & Growth ETF", "Global X", "Covered Call", "2020-09-01"),
    ("RYLG", "Global X Russell 2000 Covered Call & Growth ETF", "Global X", "Covered Call", "2020-09-01"),
    ("DJIA", "Global X Dow 30 Covered Call ETF", "Global X", "Covered Call", "2022-01-11"),
    ("DYLG", "Global X Dow 30 Covered Call & Growth ETF", "Global X", "Covered Call", "2022-01-11"),
    ("TYLG", "Global X Info Tech Covered Call & Growth ETF", "Global X", "Covered Call", "2022-04-12"),
    ("MLPD", "Global X MLP & Energy Infrastructure Covered Call ETF", "Global X", "Covered Call", "2022-04-12"),
    ("TLTX", "Global X Treasury Bond Enhanced Income ETF", "Global X", "Bond", "2024-07-16"),
    ("BCCC", "Global X Bitcoin Covered Call ETF", "Global X", "Crypto", "2024-11-12"),
    ("EHCC", "Global X Ethereum Covered Call ETF", "Global X", "Crypto", "2025-02-18"),
    ("EDGX", "Global X U.S. 500 Income Edge ETF", "Global X", "Covered Call", "2025-04-01"),
    ("EDGQ", "Global X Nasdaq 100 Income Edge ETF", "Global X", "Covered Call", "2025-04-01"),

    # === YieldMax Broad-Based ===
    ("CHPY", "YieldMax Semiconductor Portfolio Option Income ETF", "YieldMax", "Covered Call", "2024-10-15"),
    ("GDXY", "YieldMax Gold Miners Option Income Strategy ETF", "YieldMax", "Covered Call", "2024-08-06"),
    ("GPTY", "YieldMax AI & Tech Portfolio Option Income ETF", "YieldMax", "Covered Call", "2024-10-01"),
    ("LFGY", "YieldMax Crypto Industry & Tech Portfolio Option Income ETF", "YieldMax", "Crypto", "2024-10-15"),
    ("MINY", "YieldMax Strategic Metals & Mining Portfolio Option Income ETF", "YieldMax", "Covered Call", "2024-06-25"),
    ("SLTY", "YieldMax Ultra Short Option Income Strategy ETF", "YieldMax", "Options", "2024-08-13"),
    ("ULTY", "YieldMax Ultra Option Income Strategy ETF", "YieldMax", "Options", "2024-02-27"),
    ("YMAG", "YieldMax Magnificent 7 Fund of Option Income ETF", "YieldMax", "Fund of Funds", "2024-01-23"),
    ("YMAX", "YieldMax Universe Fund of Option Income ETFs", "YieldMax", "Fund of Funds", "2024-01-16"),
    ("YQQQ", "YieldMax Short N100 Option Income Strategy ETF", "YieldMax", "Inverse", "2024-04-09"),
    ("BIGY", "YieldMax Target 12 Big 50 Option Income ETF", "YieldMax", "Target Income", "2024-12-03"),
    ("SOXY", "YieldMax Target 12 Semiconductor Option Income ETF", "YieldMax", "Target Income", "2024-12-03"),
    ("QDTY", "YieldMax Nasdaq 100 0DTE Covered Call Strategy ETF", "YieldMax", "0DTE", "2025-03-04"),
    ("RDTY", "YieldMax R2000 0DTE Covered Call Strategy ETF", "YieldMax", "0DTE", "2025-03-04"),
    ("SDTY", "YieldMax S&P 500 0DTE Covered Call Strategy ETF", "YieldMax", "0DTE", "2025-03-04"),
    ("RNTY", "YieldMax Target 12 Real Estate Option Income ETF", "YieldMax", "Target Income", "2025-05-06"),

    # === YieldMax Single Stock (non-stock-specific diversified ones) ===
    ("YBIT", "YieldMax Bitcoin Option Income Strategy ETF", "YieldMax", "Crypto", "2024-04-23"),
    ("FIAT", "YieldMax Short COIN Option Income Strategy ETF", "YieldMax", "Inverse", "2024-04-02"),

    # === Defiance ===
    ("QQQY", "Defiance Nasdaq 100 Enhanced Options Income ETF", "Defiance", "Covered Call", "2023-09-14"),
    ("SPYT", "Defiance S&P 500 Target Income ETF", "Defiance", "Target Income", "2024-02-13"),
    ("QQQT", "Defiance Nasdaq 100 Income Target ETF", "Defiance", "Target Income", "2024-08-20"),
    ("IWMY", "Defiance R2000 Enhanced Options Income ETF", "Defiance", "Covered Call", "2023-10-19"),
    ("USOY", "Defiance Oil Enhanced Options Income ETF", "Defiance", "Covered Call", "2023-11-28"),
    ("TRES", "Defiance Treasury Alternative Yield ETF", "Defiance", "Bond", "2024-04-16"),
    ("BNDW", "Defiance Bond Enhanced Income ETF", "Defiance", "Bond", "2024-07-30"),

    # === Roundhill ===
    ("QDTE", "Roundhill N-100 0DTE Covered Call Strategy ETF", "Roundhill", "0DTE", "2024-03-07"),
    ("XDTE", "Roundhill S&P 500 0DTE Covered Call Strategy ETF", "Roundhill", "0DTE", "2024-03-07"),
    ("RDTE", "Roundhill Small Cap 0DTE Covered Call Strategy ETF", "Roundhill", "0DTE", "2024-09-10"),
    ("SVOL", "Simplify Volatility Premium ETF", "Simplify", "Volatility", "2021-05-12"),

    # === REX ===
    ("FEPI", "REX FANG & Innovation Equity Premium Income ETF", "REX", "Covered Call", "2023-10-03"),
    ("AIPI", "REX AI Equity Premium Income ETF", "REX", "Covered Call", "2024-06-25"),
    ("CEPI", "REX Crypto Equity Premium Income ETF", "REX", "Crypto", "2024-09-17"),
    ("DIVI", "REX International Equity Premium Income ETF", "REX", "Covered Call", "2025-01-14"),

    # === Kurv ===
    ("AAPY", "Kurv Yield Premium Strategy Apple ETF", "Kurv", "Covered Call", "2023-10-24"),
    ("AMZP", "Kurv Yield Premium Strategy Amazon ETF", "Kurv", "Covered Call", "2023-10-24"),
    ("TSLP", "Kurv Yield Premium Strategy Tesla ETF", "Kurv", "Covered Call", "2023-11-21"),
    ("GOOP", "Kurv Yield Premium Strategy Google ETF", "Kurv", "Covered Call", "2023-10-24"),
    ("MSFY", "Kurv Yield Premium Strategy Microsoft ETF", "Kurv", "Covered Call", "2023-10-24"),
    ("NFLP", "Kurv Yield Premium Strategy Netflix ETF", "Kurv", "Covered Call", "2023-12-12"),

    # === Amplify ===
    ("DIVO", "Amplify CWP Enhanced Dividend Income ETF", "Amplify", "Covered Call", "2016-12-13"),
    ("IDVO", "Amplify CWP International Enhanced Dividend Income ETF", "Amplify", "Covered Call", "2023-01-24"),
    ("HCOW", "Amplify COWS Covered Call ETF", "Amplify", "Covered Call", "2024-04-23"),
    ("BITY", "Amplify Bitcoin Income ETF", "Amplify", "Crypto", "2025-04-08"),
    ("BAGY", "Amplify Bitcoin & Gold Income ETF", "Amplify", "Crypto", "2025-04-08"),

    # === First Trust ===
    ("KNG", "FT Vest S&P 500 Dividend Aristocrats Target Income ETF", "First Trust", "Covered Call", "2018-03-26"),
    ("LGIG", "FT Vest U.S. Equity Enhance & Moderate Buffer ETF", "First Trust", "Buffer", "2023-08-18"),

    # === Invesco ===
    ("PEY", "Invesco High Yield Equity Dividend Achievers ETF", "Invesco", "Dividend", "2004-12-09"),
    ("KBWY", "Invesco KBW Premium Yield Equity REIT ETF", "Invesco", "REIT", "2010-12-02"),

    # === Cohen & Steers ===
    ("RNP", "Cohen & Steers REIT & Preferred Income Fund", "Cohen & Steers", "REIT/Preferred", "2003-06-27"),
    ("RQI", "Cohen & Steers Quality Income Realty Fund", "Cohen & Steers", "REIT", "2002-02-28"),
    ("PTA", "Cohen & Steers Tax-Advantaged Preferred Securities Fund", "Cohen & Steers", "Preferred", "2008-07-24"),

    # === Adams Funds (CEFs) ===
    ("ADX", "Adams Diversified Equity Fund", "Adams Funds", "Equity CEF", "1929-10-01"),
    ("PEO", "Adams Natural Resources Fund", "Adams Funds", "Natural Resources", "1929-10-24"),

    # === Cornerstone (CEFs) ===
    ("CLM", "Cornerstone Strategic Value Fund", "Cornerstone", "Equity CEF", "1987-06-26"),
    ("CRF", "Cornerstone Total Return Fund", "Cornerstone", "Equity CEF", "1973-05-16"),

    # === Alerian / Energy ===
    ("MLPI", "Alerian MLP ETF", "Alerian", "Energy/MLP", "2012-08-15"),
    ("AMLP", "Alerian MLP ETF", "Alerian", "Energy/MLP", "2010-08-25"),
    ("AMJ", "JPMorgan Alerian MLP Index ETN", "J.P. Morgan", "Energy/MLP", "2009-04-02"),

    # === Other Notable Income ETFs ===
    ("DIV", "Global X SuperDividend U.S. ETF", "Global X", "Dividend", "2013-03-11"),
    ("SDIV", "Global X SuperDividend ETF", "Global X", "Dividend", "2011-06-08"),
    ("SRET", "Global X SuperDividend REIT ETF", "Global X", "REIT", "2015-03-17"),
    ("ALTY", "Global X Alternative Income ETF", "Global X", "Multi-Asset", "2015-05-20"),
    ("PFFA", "Virtus InfraCap U.S. Preferred Stock ETF", "Virtus", "Preferred", "2018-05-15"),
    ("PFFD", "Global X U.S. Preferred ETF", "Global X", "Preferred", "2017-09-12"),
    ("PGX", "Invesco Preferred ETF", "Invesco", "Preferred", "2008-01-31"),
    ("PFF", "iShares Preferred & Income Securities ETF", "iShares", "Preferred", "2007-03-26"),
    ("HYD", "VanEck High Yield Muni ETF", "VanEck", "Muni Bond", "2009-02-04"),
    ("HYG", "iShares iBoxx $ High Yield Corporate Bond ETF", "iShares", "HY Bond", "2007-04-04"),
    ("JNK", "SPDR Bloomberg High Yield Bond ETF", "SPDR", "HY Bond", "2007-11-28"),
    ("EMB", "iShares J.P. Morgan USD Emerging Markets Bond ETF", "iShares", "EM Bond", "2007-12-17"),
    ("EMLC", "VanEck J.P. Morgan EM Local Currency Bond ETF", "VanEck", "EM Bond", "2010-07-22"),
    ("BKLN", "Invesco Senior Loan ETF", "Invesco", "Senior Loan", "2011-03-03"),
    ("SRLN", "SPDR Blackstone Senior Loan ETF", "SPDR", "Senior Loan", "2013-04-03"),
    ("FLOT", "iShares Floating Rate Bond ETF", "iShares", "Floating Rate", "2011-06-14"),
    ("FLRN", "SPDR Bloomberg Investment Grade Floating Rate ETF", "SPDR", "Floating Rate", "2011-11-30"),
    ("MORT", "VanEck Mortgage REIT Income ETF", "VanEck", "mREIT", "2011-08-16"),
    ("REM", "iShares Mortgage Real Estate Capped ETF", "iShares", "mREIT", "2007-05-01"),
    ("XLRE", "Real Estate Select Sector SPDR Fund", "SPDR", "REIT", "2015-10-07"),
    ("VNQ", "Vanguard Real Estate ETF", "Vanguard", "REIT", "2004-09-23"),
    ("SCHH", "Schwab U.S. REIT ETF", "Charles Schwab", "REIT", "2011-01-13"),
    ("ICSH", "iShares Ultra Short-Term Bond ETF", "iShares", "Short Bond", "2013-12-11"),
    ("JPST", "JPMorgan Ultra-Short Income ETF", "J.P. Morgan", "Short Bond", "2017-05-17"),
    ("MINT", "PIMCO Enhanced Short Maturity Active ETF", "PIMCO", "Short Bond", "2009-11-16"),
    ("BIL", "SPDR Bloomberg 1-3 Month T-Bill ETF", "SPDR", "Short Bond", "2007-05-25"),
    ("SGOV", "iShares 0-3 Month Treasury Bond ETF", "iShares", "Short Bond", "2020-05-26"),
    ("USFR", "WisdomTree Floating Rate Treasury Fund", "WisdomTree", "Floating Rate", "2014-02-20"),
    ("TFLO", "iShares Treasury Floating Rate Bond ETF", "iShares", "Floating Rate", "2014-02-04"),
    ("TDIV", "First Trust NASDAQ Technology Dividend Index Fund", "First Trust", "Tech Dividend", "2012-08-13"),
    ("VIG", "Vanguard Dividend Appreciation ETF", "Vanguard", "Dividend Growth", "2006-04-21"),
    ("VYM", "Vanguard High Dividend Yield ETF", "Vanguard", "Dividend", "2006-11-10"),
    ("SCHD", "Schwab U.S. Dividend Equity ETF", "Charles Schwab", "Dividend", "2011-10-20"),
    ("DGRO", "iShares Core Dividend Growth ETF", "iShares", "Dividend Growth", "2014-06-10"),
    ("HDV", "iShares Core High Dividend ETF", "iShares", "Dividend", "2011-03-29"),
    ("SPHD", "Invesco S&P 500 High Dividend Low Volatility ETF", "Invesco", "Dividend", "2012-10-18"),
    ("DVY", "iShares Select Dividend ETF", "iShares", "Dividend", "2003-11-03"),
    ("NOBL", "ProShares S&P 500 Dividend Aristocrats ETF", "ProShares", "Dividend Growth", "2013-10-09"),
    ("DES", "WisdomTree U.S. SmallCap Dividend Fund", "WisdomTree", "Small Cap Div", "2006-06-16"),
    ("DON", "WisdomTree U.S. MidCap Dividend Fund", "WisdomTree", "Mid Cap Div", "2006-06-16"),
    ("DLN", "WisdomTree U.S. LargeCap Dividend Fund", "WisdomTree", "Large Cap Div", "2006-06-16"),
    ("DHS", "WisdomTree U.S. High Dividend Fund", "WisdomTree", "Dividend", "2006-06-16"),
    ("RDVY", "First Trust Rising Dividend Achievers ETF", "First Trust", "Dividend Growth", "2014-01-07"),
    ("FDL", "First Trust Morningstar Dividend Leaders Index Fund", "First Trust", "Dividend", "2005-10-14"),
    ("FVD", "First Trust Value Line Dividend Index Fund", "First Trust", "Dividend", "2003-08-19"),
    ("PFM", "Invesco Dividend Achievers ETF", "Invesco", "Dividend Growth", "2005-09-15"),
    ("PFFL", "ETRACS Monthly Pay 2xLeveraged Preferred Stock ETN", "ETRACS", "Leveraged Pref", "2018-09-24"),
    ("CEFS", "Saba Closed-End Funds ETF", "Saba", "CEF", "2017-03-21"),
    ("YYY", "Amplify High Income ETF", "Amplify", "Fund of CEFs", "2013-06-25"),
    ("THTA", "SoFi Enhanced Yield ETF", "Tidal", "Options", "2023-12-27"),
    ("TUGN", "STF Tactical Growth & Income ETF", "STF", "Covered Call", "2022-07-12"),
    ("SCLZ", "Swan Enhanced Dividend Income ETF", "Swan", "Covered Call", "2022-12-28"),
    ("ISPY", "ProShares S&P 500 High Income ETF", "ProShares", "Covered Call", "2023-12-19"),
    ("BALI", "BlackRock Advantage Large Cap Income ETF", "BlackRock", "Covered Call", "2023-06-27"),

    # === Additional Defiance / REX / Roundhill ===
    ("MSTP", "Kurv Yield Premium Strategy MSTR ETF", "Kurv", "Covered Call", "2024-01-30"),
    ("KQQQ", "Kurv Nasdaq 100 Enhanced Yield ETF", "Kurv", "Covered Call", "2024-05-14"),
    ("COIP", "Kurv Yield Premium Strategy COIN ETF", "Kurv", "Covered Call", "2024-02-20"),

    # === Tap Alpha ===
    ("SPCX", "TappAlpha SPX Growth & Income ETF", "TappAlpha", "Options", "2023-11-21"),
    ("NAIX", "TappAlpha Innovation Growth & Income ETF", "TappAlpha", "Options", "2024-04-02"),

    # === Bitwise ===
    ("ICOI", "Bitwise COIN Option Income Strategy ETF", "Bitwise", "Crypto", "2025-04-01"),
    ("IMST", "Bitwise MSTR Option Income Strategy ETF", "Bitwise", "Crypto", "2025-04-01"),

    # === GraniteShares ===
    ("XBTY", "GraniteShares YieldBOOST Bitcoin ETF", "GraniteShares", "Crypto", "2025-03-18"),
    ("HOYY", "GraniteShares YieldBOOST HOOD ETF", "GraniteShares", "Covered Call", "2025-04-01"),

    # === ProShares ===
    ("BITO", "ProShares Bitcoin Strategy ETF", "ProShares", "Crypto", "2021-10-19"),

    # === More YieldMax ===
    ("DEFI", "YieldMax DeFi Option Income Strategy ETF", "YieldMax", "Crypto", "2024-07-02"),
    ("SOXXY", "YieldMax SOXX Option Income Strategy ETF", "YieldMax", "Covered Call", "2024-04-30"),
    ("KCEP", "YieldMax KCE Option Income Strategy ETF", "YieldMax", "Covered Call", "2024-06-11"),

    # === Virtus ===
    ("VRAI", "Virtus Real Asset Income ETF", "Virtus", "Real Assets", "2018-10-23"),

    # === OVL ===
    ("OVL", "Overlay Shares Large Cap Equity ETF", "Overlay Shares", "Covered Call", "2019-09-25"),
    ("OVB", "Overlay Shares Core Bond ETF", "Overlay Shares", "Bond", "2019-09-25"),

    # === Additional CEFs ===
    ("WTPI", "West Shore Tactical Premium Income Fund", "West Shore", "Multi-Asset CEF", "2020-07-14"),
    ("IGLD", "FT Vest Gold Strategy Target Income ETF", "First Trust", "Gold/Covered Call", "2021-07-20"),

    # === Curve ===
    ("CURV", "Curve Frontier Markets Income ETF", "Curve", "EM Income", "2024-05-07"),

    # === Crosshares ===
    ("XRMI", "Crosshares Monthly Income ETF", "Crosshares", "Options", "2024-01-30"),

    # === Reeves ===
    ("RINC", "Reeves Income Fund", "Reeves", "Multi-Asset", "2024-03-12"),
]

def generate_metrics(inception_date, ticker):
    """Generate semi-realistic metrics for an ETF."""
    inception = datetime.strptime(inception_date, "%Y-%m-%d")
    days_since = max((datetime(2026, 7, 1) - inception).days, 365)
    years = days_since / 365.25

    # Base yield varies by provider/category
    ticker_upper = ticker.upper()

    if ticker in ("BIL", "SGOV", "ICSH", "JPST", "MINT", "USFR", "TFLO", "FLOT", "FLRN"):
        current_yield = round(random.uniform(4.0, 5.5), 2)
        avg_yield = round(current_yield * random.uniform(0.85, 1.05), 2)
    elif ticker in ("HYG", "JNK", "HYD", "EMB", "EMLC", "BKLN", "SRLN"):
        current_yield = round(random.uniform(5.5, 8.5), 2)
        avg_yield = round(current_yield * random.uniform(0.85, 1.05), 2)
    elif ticker in ("SCHD", "VYM", "VIG", "DGRO", "HDV", "DVY", "NOBL", "SPHD", "PEY"):
        current_yield = round(random.uniform(2.5, 5.0), 2)
        avg_yield = round(current_yield * random.uniform(0.88, 1.02), 2)
    elif ticker in ("DIVO", "IDVO", "JEPI", "JEPQ", "JEPY"):
        current_yield = round(random.uniform(5.0, 9.0), 2)
        avg_yield = round(current_yield * random.uniform(0.85, 1.08), 2)
    elif ticker in ("SPYI", "QQQI", "IWMI"):
        current_yield = round(random.uniform(11.0, 15.0), 2)
        avg_yield = round(current_yield * random.uniform(0.8, 1.05), 2)
    elif ticker in ("QYLD", "XYLD", "RYLD"):
        current_yield = round(random.uniform(9.0, 13.5), 2)
        avg_yield = round(current_yield * random.uniform(0.82, 1.0), 2)
    elif "YIELDMAX" in ticker or ticker in ("CHPY", "GDXY", "GPTY", "LFGY", "MINY", "ULTY", "YMAG", "YMAX", "SLTY", "BIGY", "SOXY", "QDTY", "RDTY", "SDTY"):
        current_yield = round(random.uniform(25, 65), 2)
        avg_yield = round(current_yield * random.uniform(0.7, 0.95), 2)
    elif ticker in ("QDTE", "XDTE", "RDTE"):
        current_yield = round(random.uniform(5.0, 11.0), 2)
        avg_yield = round(current_yield * random.uniform(0.75, 0.95), 2)
    elif ticker in ("FEPI", "AIPI", "CEPI", "DIVI"):
        current_yield = round(random.uniform(6.0, 25.0), 2)
        avg_yield = round(current_yield * random.uniform(0.7, 0.95), 2)
    elif ticker in ("QQQY", "IWMY", "QQQT", "SPYT"):
        current_yield = round(random.uniform(7.0, 22.0), 2)
        avg_yield = round(current_yield * random.uniform(0.7, 0.9), 2)
    elif ticker in ("SVOL",):
        current_yield = round(random.uniform(16.0, 22.0), 2)
        avg_yield = round(current_yield * random.uniform(0.75, 0.9), 2)
    elif ticker in ("PFFA", "PFFD", "PGX", "PFF", "PFFL"):
        current_yield = round(random.uniform(6.0, 10.0), 2)
        avg_yield = round(current_yield * random.uniform(0.85, 1.02), 2)
    elif ticker in ("AMLP", "MLPI", "AMJ"):
        current_yield = round(random.uniform(6.5, 8.5), 2)
        avg_yield = round(current_yield * random.uniform(0.85, 1.05), 2)
    elif ticker in ("VNQ", "SCHH", "XLRE", "REM", "MORT"):
        current_yield = round(random.uniform(3.5, 8.0), 2)
        avg_yield = round(current_yield * random.uniform(0.88, 1.02), 2)
    elif ticker in ("CLM", "CRF", "ADX", "PEO", "RNP", "RQI", "PTA"):
        current_yield = round(random.uniform(7.0, 16.0), 2)
        avg_yield = round(current_yield * random.uniform(0.8, 1.0), 2)
    else:
        current_yield = round(random.uniform(5.0, 20.0), 2)
        avg_yield = round(current_yield * random.uniform(0.78, 1.0), 2)

    # NAV erosion pattern
    nav_erosion = random.uniform(-0.15, 0.06)  # annualized NAV change (most lose value)
    total_return = current_yield / 100 + nav_erosion + random.uniform(-0.05, 0.05)

    # Sharpe ratio
    sharpe = round(random.uniform(-0.5, 1.8), 2)
    sortino = round(sharpe + random.uniform(-0.2, 0.5), 2)
    calmar = round(sharpe * random.uniform(0.5, 1.2), 2)

    # Distribution coverage
    dist_coverage = round(random.uniform(-0.5, 2.5), 2)

    # Beta and correlation
    if ticker in ("USOY", "MLPI", "AMLP", "MLPD"):
        beta = round(random.uniform(0.1, 0.5), 2)
        correlation = round(random.uniform(0.05, 0.4), 2)
    elif ticker in ("SVOL",):
        beta = round(random.uniform(-0.1, 0.15), 2)
        correlation = round(random.uniform(0.0, 0.2), 2)
    elif ticker in ("BIL", "SGOV", "ICSH", "JPST", "MINT", "USFR", "TFLO"):
        beta = round(random.uniform(-0.02, 0.05), 2)
        correlation = round(random.uniform(-0.1, 0.15), 2)
    else:
        beta = round(random.uniform(0.3, 1.8), 2)
        correlation = round(min(random.uniform(0.3, 0.95), beta * 0.7 + 0.1), 2)

    # Available income per $10k
    available_income = round(10000 * (current_yield / 100 - max(0, -nav_erosion)), 0)

    # Returns
    t12_return = round(total_return * 100, 2)
    price_return_t12 = round(nav_erosion * 100, 2)

    if years >= 3:
        ret_3yr = round((total_return - random.uniform(-0.03, 0.03)) * 100 * (3 if years >= 3 else years), 2)
    else:
        ret_3yr = None

    if years >= 5:
        ret_5yr = round((total_return - random.uniform(-0.04, 0.02)) * 100 * 5, 2)
    else:
        ret_5yr = None

    if years >= 10:
        ret_10yr = round((total_return - random.uniform(-0.03, 0.05)) * 100 * 10, 2)
    else:
        ret_10yr = None

    # $10k growth
    growth_10k = round(10000 * (1 + total_return) ** min(years, 2), 0)

    return {
        "current_yield": current_yield,
        "avg_yield_since_inception": avg_yield,
        "inception_date": inception_date,
        "years_history": round(years, 1),
        "distribution_coverage": dist_coverage,
        "sharpe_ratio": sharpe,
        "sharpe_t12": round(sharpe + random.uniform(-0.3, 0.3), 2),
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "total_return_1yr": t12_return,
        "total_return_3yr": ret_3yr,
        "total_return_5yr": ret_5yr,
        "total_return_10yr": ret_10yr,
        "price_return_t12": price_return_t12,
        "beta_sp500": beta,
        "correlation_sp500": correlation,
        "available_income_10k": available_income,
        "growth_10k": growth_10k,
        "nav_annual_change": round(nav_erosion * 100, 2),
    }


def create_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS etfs")
    c.execute("""
        CREATE TABLE etfs (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT,
            category TEXT,
            inception_date TEXT,
            current_yield REAL,
            avg_yield_since_inception REAL,
            distribution_coverage REAL,
            sharpe_ratio REAL,
            sharpe_t12 REAL,
            sortino_ratio REAL,
            calmar_ratio REAL,
            total_return_1yr REAL,
            total_return_3yr REAL,
            total_return_5yr REAL,
            total_return_10yr REAL,
            price_return_1yr REAL,
            beta_sp500 REAL,
            correlation_sp500 REAL,
            available_income_10k REAL,
            growth_10k REAL,
            nav_annual_change REAL,
            date_added TEXT,
            is_new BOOLEAN DEFAULT 0
        )
    """)

    # Batch insert
    batch_date = "2026-07-01"
    newest_batch = "2026-07-15"

    for i, (ticker, name, provider, category, inception) in enumerate(ETFS):
        metrics = generate_metrics(inception, ticker)
        is_new = (i >= len(ETFS) - 15)  # Last 15 are "new"

        c.execute("""
            INSERT INTO etfs (ticker, name, provider, category, inception_date,
                current_yield, avg_yield_since_inception, distribution_coverage,
                sharpe_ratio, sharpe_t12, sortino_ratio, calmar_ratio,
                total_return_1yr, total_return_3yr, total_return_5yr, total_return_10yr,
                price_return_1yr, beta_sp500, correlation_sp500,
                available_income_10k, growth_10k, nav_annual_change, date_added, is_new)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker, name, provider, category, inception,
            metrics["current_yield"], metrics["avg_yield_since_inception"],
            metrics["distribution_coverage"],
            metrics["sharpe_ratio"], metrics["sharpe_t12"],
            metrics["sortino_ratio"], metrics["calmar_ratio"],
            metrics["total_return_1yr"], metrics["total_return_3yr"],
            metrics["total_return_5yr"], metrics["total_return_10yr"],
            metrics["price_return_t12"],
            metrics["beta_sp500"], metrics["correlation_sp500"],
            metrics["available_income_10k"], metrics["growth_10k"],
            metrics["nav_annual_change"],
            newest_batch if is_new else batch_date, is_new
        ))

    conn.commit()

    # Print count
    count = c.execute("SELECT COUNT(*) FROM etfs").fetchone()[0]
    print(f"Inserted {count} ETFs into {DB_PATH}")

    conn.close()
    return count


if __name__ == "__main__":
    create_db()
