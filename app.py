"""High Yield Income ETF Dashboard - FastAPI Backend"""
import sqlite3
import random
import math
from datetime import datetime, timedelta
from functools import lru_cache
from fastapi import FastAPI, Query, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_env = Environment(loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")))

app = FastAPI(title="ETF Income Dashboard")

# Store DB on slow disk for efficiency; fall back to local if unmounted
DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
if not os.path.exists(os.path.dirname(DB_PATH)):
    DB_PATH = os.path.join(BASE_DIR, "data", "etfs.db")

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Slow-disk optimizations
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
    conn.execute("PRAGMA mmap_size=67108864")  # 64MB mmap
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    template = _env.get_template("index.html")
    return HTMLResponse(template.render({"request": request}))


@app.get("/api/etfs")
def list_etfs(
    provider: str = Query(None),
    category: str = Query(None),
    sort_by: str = Query("current_yield"),
    sort_dir: str = Query("desc"),
):
    conn = get_db()
    query = "SELECT * FROM etfs WHERE 1=1"
    params = []

    if provider:
        query += " AND provider = ?"
        params.append(provider)
    if category:
        query += " AND category = ?"
        params.append(category)

    allowed_sorts = [
        "current_yield", "avg_yield_since_inception", "distribution_coverage",
        "sharpe_ratio", "sortino_ratio", "calmar_ratio",
        "total_return_1yr", "total_return_3yr", "total_return_5yr", "total_return_10yr",
        "price_return_1yr", "beta_sp500", "correlation_sp500",
        "available_income_10k", "growth_10k", "nav_annual_change",
        "inception_date", "ticker", "name", "provider",
        "tax_treatment_score", "income_stability_score"
    ]
    if sort_by in allowed_sorts:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort_by} {direction} NULLS LAST"
    else:
        query += " ORDER BY current_yield DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/etfs/newest-growth")
def newest_growth(limit: int = Query(15)):
    """Return $10K growth data for the newest ETFs (for the reference growth chart)."""
    conn = get_db()
    # Find newest ETFs with price history
    newest = conn.execute("""
        SELECT ticker, name, inception_date FROM etfs
        WHERE inception_date IS NOT NULL
          AND ticker IN (SELECT DISTINCT ticker FROM price_history)
        ORDER BY inception_date DESC LIMIT ?
    """, (limit,)).fetchall()

    tickers = [r["ticker"] for r in newest]
    start_dates = {r["ticker"]: r["inception_date"] for r in newest}

    if not tickers:
        conn.close()
        return {"tickers": [], "growth_data": {}}

    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(f"""
        SELECT ticker, date, close
        FROM price_history
        WHERE ticker IN ({placeholders})
        ORDER BY date
    """, tickers).fetchall()
    conn.close()

    # Group by ticker, compute $10K growth
    histories = {}
    for r in rows:
        t = r["ticker"]
        if t not in histories:
            histories[t] = []
        histories[t].append({"date": r["date"], "close": float(r["close"])})

    growth_data = {}
    for t in tickers:
        hist = histories.get(t, [])
        if len(hist) < 2:
            continue
        start_price = hist[0]["close"]
        if not start_price or start_price <= 0:
            continue

        # Price return: $10K * (current_price / start_price)
        price_points = [{"date": h["date"], "value": round(10000 * h["close"] / start_price, 2)} for h in hist]

        # Total return: include dividends reinvested
        # Get dividend amounts aligned to the same dates
        conn3 = get_db()
        div_rows = conn3.execute(
            "SELECT date, dividend FROM price_history WHERE ticker = ? ORDER BY date", (t,)
        ).fetchall()
        conn3.close()

        div_map = {r["date"]: float(r["dividend"]) for r in div_rows}

        total_points = []
        shares = 10000.0 / start_price
        cash_from_divs = 0.0

        for h in hist:
            date = h["date"]
            price = h["close"]
            # Add any dividend from this period
            div = div_map.get(date, 0)
            if div > 0:
                cash_from_divs += shares * div

            value = shares * price + cash_from_divs
            total_points.append({"date": date, "value": round(value, 2)})

        growth_data[t] = {
            "name": start_dates.get(t, t),
            "start_date": hist[0]["date"],
            "price_growth": price_points,
            "total_growth": total_points,
            "total_return_value": round(total_points[-1]["value"], 2) if total_points else 10000,
            "price_return_value": round(price_points[-1]["value"], 2) if price_points else 10000,
            "initial_value": 10000,
        }

    return {
        "tickers": [t for t in tickers if t in growth_data],
        "growth_data": growth_data,
    }

@app.get("/api/etfs/new")
def newest_additions(limit: int = Query(20)):
    """Return ETFs with the most recent inception dates (dynamic 'newest' list)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT ticker, name, current_yield, total_return_1yr, inception_date
        FROM etfs
        WHERE current_yield IS NOT NULL
        ORDER BY inception_date DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/etfs/{ticker}")
def etf_detail(ticker: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM etfs WHERE ticker = ?", (ticker.upper(),)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "ETF not found")
    return dict(row)


@app.get("/api/providers")
def list_providers():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT provider FROM etfs ORDER BY provider"
    ).fetchall()
    conn.close()
    return [r["provider"] for r in rows]


@app.get("/api/categories")
def list_categories():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM etfs ORDER BY category"
    ).fetchall()
    conn.close()
    return [r["category"] for r in rows]


@app.get("/api/leaderboard")
def leaderboard(period: str = Query("1yr")):
    conn = get_db()
    etfs = conn.execute("SELECT * FROM etfs").fetchall()
    conn.close()

    # Map period param to the right total_return field
    period_field = {
        "1yr": "total_return_1yr",
        "3yr": "total_return_3yr",
        "5yr": "total_return_5yr",
        "10yr": "total_return_10yr",
        "max": "total_return_10yr",
    }.get(period, "total_return_1yr")

    categories = {
        "highest_yield": [],
        "best_dist_coverage": [],
        "best_total_return_1yr": [],
        "best_total_return_3yr": [],
        "best_total_return_5yr": [],
        "best_total_return_10yr": [],
        "best_sharpe": [],
        "best_sortino": [],
        "best_calmar": [],
        "best_nav_growth": [],
    }

    etf_list = [dict(e) for e in etfs]

    def _safe_sort(keyfn, lst, reverse=True):
        return sorted([x for x in lst if keyfn(x) is not None], key=keyfn, reverse=reverse)

    categories["highest_yield"] = _safe_sort(lambda x: x["current_yield"], etf_list)[:10]
    categories["best_dist_coverage"] = _safe_sort(lambda x: x["distribution_coverage"], etf_list)[:10]

    for p in ["total_return_1yr", "total_return_3yr", "total_return_5yr", "total_return_10yr"]:
        valid = [e for e in etf_list if e[p] is not None]
        categories[f"best_{p}"] = _safe_sort(lambda x, p=p: x[p], valid)[:10]

    categories["best_sharpe"] = _safe_sort(lambda x: x["sharpe_ratio"], etf_list)[:10]
    categories["best_sortino"] = _safe_sort(lambda x: x["sortino_ratio"], etf_list)[:10]
    categories["best_calmar"] = _safe_sort(lambda x: x["calmar_ratio"], etf_list)[:10]
    categories["best_nav_growth"] = _safe_sort(lambda x: x["nav_annual_change"], etf_list)[:10]

    ticker_appearances = {}
    for cat_name, cat_etfs in categories.items():
        for e in cat_etfs[:5]:
            ticker = e["ticker"]
            ticker_appearances[ticker] = ticker_appearances.get(ticker, 0) + 1

    leaderboard = {}
    for cat_name, cat_etfs in categories.items():
        entries = []
        for e in cat_etfs:
            count = ticker_appearances.get(e["ticker"], 0)
            tier = "green" if count >= 4 else ("red" if count >= 3 else "blue")
            entries.append({**e, "appearances": count, "tier": tier})
        leaderboard[cat_name] = entries

    yields = [e["current_yield"] for e in etf_list if e["current_yield"] is not None]
    avg_yield = round(sum(yields) / len(yields), 2) if yields else 0

    # Period-specific best values
    best_total_return = None
    best_sharpe = None
    if period_field in ["total_return_1yr","total_return_3yr","total_return_5yr","total_return_10yr"]:
        valid = [e for e in etf_list if e[period_field] is not None]
        if valid:
            best = max(valid, key=lambda x: x[period_field])
            best_total_return = (best["ticker"], round(best[period_field], 2))

    # Period-specific Sharpe: 1yr → sharpe_t12, max → sharpe_ratio, others → compute from price history
    if period == "1yr":
        valid_sh = [e for e in etf_list if e["sharpe_t12"] is not None]
        if valid_sh:
            best_s = max(valid_sh, key=lambda x: x["sharpe_t12"])
            best_sharpe = (best_s["ticker"], round(best_s["sharpe_t12"], 2))
    elif period == "max":
        valid_sh = [e for e in etf_list if e["sharpe_ratio"] is not None]
        if valid_sh:
            best_s = max(valid_sh, key=lambda x: x["sharpe_ratio"])
            best_sharpe = (best_s["ticker"], round(best_s["sharpe_ratio"], 2))
    else:
        # Compute Sharpe from price history for 3yr/5yr/10yr
        conn2 = get_db()
        months_map = {"3yr": 36, "5yr": 60, "10yr": 120}
        n_months = months_map.get(period, 36)
        # Get SPY and all ETF prices
        tickers_all = [e["ticker"] for e in etf_list]
        ph_rows = conn2.execute(
            "SELECT ticker, date, close FROM price_history ORDER BY date DESC"
        ).fetchall()
        conn2.close()
        # Group by ticker
        price_map = {}
        for r in ph_rows:
            t = r["ticker"]
            if t not in price_map:
                price_map[t] = []
            price_map[t].append(float(r["close"]))
        # Compute Sharpe for each ETF
        sharpe_results = []
        for e in etf_list:
            t = e["ticker"]
            closes = price_map.get(t, [])
            if len(closes) < n_months + 1:
                continue
            recent = closes[:n_months + 1]
            returns = [(recent[i-1] - recent[i]) / recent[i] for i in range(1, len(recent))]
            if len(returns) < 3:
                continue
            mean_r = sum(returns) / len(returns)
            std_r = math.sqrt(sum((r - mean_r)**2 for r in returns) / (len(returns) - 1))
            if std_r > 0:
                sharpe = (mean_r * 12) / (std_r * math.sqrt(12))  # annualized
                sharpe_results.append((e["ticker"], round(sharpe, 2)))
        if sharpe_results:
            best_s = max(sharpe_results, key=lambda x: x[1])
            best_sharpe = best_s

    stats = {
        "total_etfs": len(etf_list),
        "avg_yield": avg_yield,
        "highest_yield": max(yields) if yields else 0,
        "providers": len(set(e["provider"] for e in etf_list)),
        "best_total_return": best_total_return,
        "best_sharpe": best_sharpe,
        "period": period,
    }

    return {"stats": stats, "categories": leaderboard}


@app.get("/api/beta-correlation")
def beta_correlation(period: str = Query("1yr")):
    conn = get_db()

    # Get all ETFs
    rows = conn.execute("""
        SELECT ticker, name, provider, beta_sp500, correlation_sp500, current_yield
        FROM etfs WHERE beta_sp500 IS NOT NULL
    """).fetchall()

    # Determine month cutoff
    now = datetime.now()
    if period == "1yr":
        cutoff = now - timedelta(days=400)  # generous buffer for monthly data
    elif period == "3yr":
        cutoff = now - timedelta(days=1100)
    else:  # full
        cutoff = datetime(1900, 1, 1)

    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # Fetch price history for all tickers + SPY
    tickers = [r["ticker"] for r in rows]
    all_tickers = tickers + ["SPY"]
    if not tickers:
        conn.close()
        return {"points": [], "period": period}

    placeholders = ",".join("?" * len(all_tickers))
    price_rows = conn.execute(
        f"SELECT ticker, date, close, dividend FROM price_history WHERE ticker IN ({placeholders}) AND date >= ? ORDER BY ticker, date",
        [*all_tickers, cutoff_str]
    ).fetchall()

    # Build price dict: ticker -> [{date, close}, ...]
    prices = {}
    for r in price_rows:
        t = r["ticker"]
        if t not in prices:
            prices[t] = []
        prices[t].append({"date": r["date"], "close": float(r["close"])})

    conn.close()

    # Compute monthly returns for each ticker
    def monthly_returns(ticker):
        pts = prices.get(ticker, [])
        if len(pts) < 3:
            return []
        rets = []
        for i in range(1, len(pts)):
            prev = pts[i-1]["close"]
            curr = pts[i]["close"]
            if prev > 0:
                rets.append((curr - prev) / prev)
        return rets

    spy_rets = monthly_returns("SPY")
    if len(spy_rets) < 3:
        # Fallback to DB stored values
        points = []
        for r in rows:
            points.append({
                "ticker": r["ticker"], "name": r["name"], "provider": r["provider"],
                "beta": r["beta_sp500"], "correlation": r["correlation_sp500"],
                "yield": r["current_yield"],
            })
        return {"points": points, "period": period}

    # Helper: compute beta and correlation between two return series
    def compute_beta_corr(etf_rets, spy_rets):
        n = min(len(etf_rets), len(spy_rets))
        if n < 3:
            return None, None
        er = etf_rets[-n:]
        sr = spy_rets[-n:]
        mean_er = sum(er) / n
        mean_sr = sum(sr) / n
        cov = sum((er[i] - mean_er) * (sr[i] - mean_sr) for i in range(n)) / (n - 1)
        var_sr = sum((sr[i] - mean_sr) ** 2 for i in range(n)) / (n - 1)
        std_er = math.sqrt(sum((er[i] - mean_er) ** 2 for i in range(n)) / (n - 1))
        std_sr = math.sqrt(var_sr)
        beta = cov / var_sr if var_sr > 0 else 0
        corr = cov / (std_er * std_sr) if (std_er > 0 and std_sr > 0) else 0
        return beta, corr

    points = []
    for r in rows:
        etf_rets = monthly_returns(r["ticker"])
        beta, corr = compute_beta_corr(etf_rets, spy_rets)
        if beta is None:
            beta = r["beta_sp500"]
            corr = r["correlation_sp500"]
        points.append({
            "ticker": r["ticker"], "name": r["name"], "provider": r["provider"],
            "beta": round(beta, 2), "correlation": round(corr, 2),
            "yield": r["current_yield"],
        })

    return {"points": points, "period": period}


@app.get("/api/price-growth")
def price_growth(period: str = Query("1yr")):
    conn = get_db()

    # Determine start date based on period
    now = datetime.now()
    period_days = {"1yr": 400, "3yr": 1100, "5yr": 1825, "10yr": 3650, "max": 99999}
    days = period_days.get(period, 400)
    cutoff = now - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    # Get all ETF tickers with inception before cutoff
    rows = conn.execute(
        "SELECT ticker, name FROM etfs ORDER BY ticker"
    ).fetchall()
    tickers = [r["ticker"] for r in rows]

    # Fetch monthly close prices since cutoff
    placeholders = ",".join("?" * len(tickers))
    price_rows = conn.execute(
        f"SELECT ticker, date, close FROM price_history WHERE ticker IN ({placeholders}) AND date >= ? ORDER BY ticker, date",
        [*tickers, cutoff_str]
    ).fetchall()
    conn.close()

    # Group by ticker
    price_map = {}
    dates_set = set()
    for r in price_rows:
        t = r["ticker"]
        d = r["date"]
        c = float(r["close"])
        if t not in price_map:
            price_map[t] = []
        price_map[t].append({"date": d, "close": c})
        dates_set.add(d)

    # Sort dates and keep those with enough data
    all_dates = sorted(dates_set)
    if not all_dates:
        return {"labels": [], "datasets": []}

    # For each date, count how many tickers have data
    date_counts = {}
    for d in all_dates:
        cnt = sum(1 for pts in price_map.values() if any(p["date"] == d for p in pts))
        date_counts[d] = cnt

    # Find the first date where at least 10% of tickers have data (reduces early sparse dates)
    min_ratio = 0.15
    total_tickers = len(tickers)
    first_good = None
    for d in all_dates:
        if date_counts[d] / total_tickers >= min_ratio:
            first_good = d
            break

    if first_good is None:
        first_good = all_dates[0]

    # Trim labels to start from first_good
    trimmed_labels = []
    for d in all_dates:
        if d >= first_good:
            trimmed_labels.append(d)
    all_dates = trimmed_labels
    if not all_dates:
        return {"labels": [], "datasets": []}

    # Build datasets: normalize each ticker to $10,000 at first price
    datasets = []
    for t in tickers:
        pts = price_map.get(t, [])
        if len(pts) < 4:
            continue
        # Map to date → close
        pt_map = {p["date"]: p["close"] for p in pts}
        first_close = None
        values = []
        for d in all_dates:
            c = pt_map.get(d)
            if c is None:
                values.append(None)
            else:
                if first_close is None:
                    first_close = c
                values.append(round(c / first_close * 10000, 2))
        # Skip tickers with zero data
        if not any(v is not None for v in values):
            continue
        datasets.append({
            "ticker": t,
            "data": values,
            "fill": False,
        })

    return {"labels": all_dates, "datasets": datasets}


def _get_monthly_prices(conn, tickers):
    """Return dict: ticker -> [{date, close, dividend}, ...] sorted by date."""
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, date, close, dividend FROM price_history WHERE ticker IN ({placeholders}) ORDER BY date",
        tickers
    ).fetchall()

    data = {}
    for r in rows:
        t = r["ticker"]
        if t not in data:
            data[t] = []
        data[t].append({"date": r["date"], "close": float(r["close"]), "dividend": float(r["dividend"])})
    return data


def _find_common_months(price_data, tickers):
    """Find the earliest date where ALL tickers have data, return list of common month dicts."""
    if not tickers:
        return [], None

    # Find the latest "first date" among selected tickers
    latest_start = None
    for t in tickers:
        if t in price_data and price_data[t]:
            first = price_data[t][0]["date"]
            if latest_start is None or first > latest_start:
                latest_start = first

    if latest_start is None:
        return [], None

    # Collect aligned months
    months = []
    # Use the first ticker's dates as reference, filter by latest_start
    for row in price_data[tickers[0]]:
        if row["date"] >= latest_start:
            months.append(row["date"])

    return months, latest_start


@app.post("/api/portfolio/simulate")
def simulate_portfolio(data: dict):
    tickers_weight = data.get("tickers", [])
    initial = data.get("initial_investment", 25000)
    reinvest_pct = data.get("reinvest_pct", 50) / 100
    rebalance_freq = data.get("rebalance", "none")

    tickers = [t["ticker"].upper() for t in tickers_weight]
    weights = {t["ticker"].upper(): t["weight"] / 100 for t in tickers_weight}

    conn = get_db()
    price_data = _get_monthly_prices(conn, tickers)
    conn.close()

    if not price_data:
        raise HTTPException(400, "No historical data available for selected tickers")

    # Get ETF names and current yields for display
    conn2 = get_db()
    etf_info = {}
    for t in tickers:
        row = conn2.execute("SELECT name, current_yield FROM etfs WHERE ticker = ?", (t,)).fetchone()
        if row:
            etf_info[t] = {"name": row["name"], "current_yield": row["current_yield"]}
    conn2.close()

    months, start_date = _find_common_months(price_data, tickers)
    if not months or len(months) < 2:
        raise HTTPException(400, "Not enough overlapping history for selected tickers")

    # Apply period filter
    period = data.get("period", "max")
    if period != "max" and period in ("1yr", "3yr", "5yr", "10yr"):
        years = int(period.replace("yr", ""))
        cutoff_date = (datetime.strptime(months[-1], "%Y-%m-%d") - timedelta(days=years * 365 + 1)).strftime("%Y-%m-%d")
        months = [m for m in months if m >= cutoff_date]
        if len(months) < 2:
            raise HTTPException(400, f"Not enough history for {period} period with selected tickers")
        start_date = months[0]

    # Simulate month by month
    shares = {}
    cash = 0.0
    total_cash_received = 0.0

    # First month: buy initial shares
    first_month = months[0]
    for t in tickers:
        entry = next((p for p in price_data[t] if p["date"] == first_month), None)
        if entry:
            alloc = initial * weights.get(t, 0)
            price = entry["close"]
            if price > 0:
                shares[t] = alloc / price
            else:
                shares[t] = 0
        else:
            shares[t] = 0

    monthly_nav = []
    monthly_income = []
    monthly_no_reinvest = []

    # Record initial shares for no-reinvest calculation
    initial_shares = dict(shares)

    # Process subsequent months
    for i, month in enumerate(months[1:], 1):
        month_income = 0
        total_value = 0

        for t in tickers:
            entry = next((p for p in price_data[t] if p["date"] == month), None)
            if not entry or t not in shares:
                continue
            price = entry["close"]
            div_per_share = entry["dividend"]
            s = shares[t]

            total_value += s * price
            div_income = s * div_per_share
            month_income += div_income

            # Reinvest dividends
            if reinvest_pct > 0 and price > 0:
                reinvested = div_income * reinvest_pct
                shares[t] += reinvested / price
                cash += div_income * (1 - reinvest_pct)
            else:
                cash += div_income

        total_cash_received += month_income * (1 - reinvest_pct)

        # Rebalance if needed
        if rebalance_freq == "monthly" and total_value > 0:
            for t in tickers:
                target_value = total_value * weights.get(t, 0)
                entry = next((p for p in price_data[t] if p["date"] == month), None)
                if entry and entry["close"] > 0:
                    target_shares = target_value / entry["close"]
                    current_shares = shares.get(t, 0)
                    shares[t] = target_shares
        elif rebalance_freq == "annual" and i % 12 == 0 and total_value > 0:
            for t in tickers:
                target_value = total_value * weights.get(t, 0)
                entry = next((p for p in price_data[t] if p["date"] == month), None)
                if entry and entry["close"] > 0:
                    shares[t] = target_value / entry["close"]

        # Calculate NAV after processing
        current_nav = cash
        for t in tickers:
            entry = next((p for p in price_data[t] if p["date"] == month), None)
            if entry:
                current_nav += shares.get(t, 0) * entry["close"]

        monthly_nav.append(round(current_nav, 2))
        monthly_income.append(round(month_income, 2))

        # NAV-only: initial shares at current prices (no reinvestment)
        nr_value = 0
        for t in tickers:
            entry = next((p for p in price_data[t] if p["date"] == month), None)
            if entry:
                nr_value += initial_shares.get(t, 0) * entry["close"]
        monthly_no_reinvest.append(round(nr_value, 2))

    # Final value
    final_value = cash
    last_month = months[-1]
    for t in tickers:
        entry = next((p for p in price_data[t] if p["date"] == last_month), None)
        if entry:
            final_value += shares.get(t, 0) * entry["close"]

    total_return = round(((final_value + total_cash_received) / initial - 1) * 100, 2)
    nav_change_pct = round((final_value / initial - 1) * 100, 2)
    avg_yield = round(sum((etf_info.get(t, {}).get("current_yield") or 0) * weights.get(t, 0) for t in tickers), 2)

    return {
        "initial_investment": initial,
        "final_value": round(final_value, 2),
        "total_cash_received": round(total_cash_received, 2),
        "total_return_pct": total_return,
        "nav_change_pct": nav_change_pct,
        "avg_yield": avg_yield,
        "months": len(months) - 1,
        "start_date": start_date,
        'monthly_nav': monthly_nav,
        'monthly_income': monthly_income,
        'monthly_no_reinvest': monthly_no_reinvest,
    }


@app.get("/api/best-portfolios")
def best_portfolios(
    period: str = Query("1yr"),
    sort_by: str = Query("income"),
):
    """Monte Carlo portfolio optimization using real monthly price history."""
    conn = get_db()

    # Determine lookback months
    if period == "1yr":
        lookback_months = 12
    elif period == "3yr":
        lookback_months = 36
    elif period == "5yr":
        lookback_months = 60
    elif period == "10yr":
        lookback_months = 120
    else:
        lookback_months = 12

    # Find tickers with sufficient history (have data spanning the lookback period)
    min_rows = max(int(lookback_months * 0.7), 6)
    cutoff_start = f"datetime('now', '-{lookback_months + 2} months')"
    cutoff_end = f"datetime('now', '-1 month')"
    rows = conn.execute(f"""
        SELECT ticker, COUNT(*) as cnt, MIN(date) as first_d, MAX(date) as last_d
        FROM price_history
        WHERE date >= {cutoff_start} AND date <= {cutoff_end}
        GROUP BY ticker
        HAVING cnt >= {min_rows}
        ORDER BY cnt DESC
    """).fetchall()

    eligible = [r["ticker"] for r in rows]
    if len(eligible) < 4:
        conn.close()
        return {"portfolios": [], "eligible_etfs": len(eligible), "period": period}

    # Load price data for eligible tickers
    price_data = _get_monthly_prices(conn, eligible)

    # Filter to only tickers with enough recent data
    recent_tickers = []
    for t in eligible:
        if t in price_data and len(price_data[t]) >= lookback_months:
            recent_tickers.append(t)

    conn.close()

    # Load tax treatment scores from DB (already closed, load from etfs data on next query)
    # We'll use a separate read since conn is closed
    conn2 = get_db()
    tax_rows = conn2.execute(
        "SELECT ticker, tax_treatment_score FROM etfs WHERE tax_treatment_score IS NOT NULL"
    ).fetchall()
    tax_scores = {r["ticker"]: r["tax_treatment_score"] for r in tax_rows}
    conn2.close()

    if len(recent_tickers) < 4:
        return {"portfolios": [], "eligible_etfs": len(recent_tickers), "period": period}

    # Run Monte Carlo — buy-and-hold simulation matching original dashboard
    n_simulations = min(3000, math.comb(len(recent_tickers), 4) * 5)
    n_simulations = max(n_simulations, 200)
    random.seed(42)

    all_portfolios = []

    for _ in range(n_simulations):
        n_etfs = random.randint(4, min(8, len(recent_tickers)))
        selected = random.sample(recent_tickers, n_etfs)
        raw_weights = [random.uniform(5, 25) for _ in selected]
        tw = sum(raw_weights)
        weights = [w / tw for w in raw_weights]

        initial_val = 10000
        buy_price = {}  # ticker -> first month close
        nav_values = []   # monthly NAV (price only)
        monthly_incomes = []
        total_cash_received = 0
        shares = {}

        # Find common months across selected tickers
        common_months = None
        for t in selected:
            hist = price_data.get(t, [])
            if not hist:
                continue
            ticker_months = {h["date"] for h in hist}
            if common_months is None:
                common_months = ticker_months
            else:
                common_months &= ticker_months

        if not common_months:
            continue

        common_months = sorted(common_months)
        if len(common_months) < 2:
            continue

        # Trim to lookback period
        if len(common_months) > lookback_months:
            common_months = common_months[-lookback_months:]

        # Month 0: allocate and buy shares
        start_m = common_months[0]
        for i, t in enumerate(selected):
            entry = next((h for h in price_data.get(t, []) if h["date"] == start_m), None)
            if entry and entry["close"] > 0:
                alloc = initial_val * weights[i]
                shares[t] = alloc / entry["close"]
                buy_price[t] = entry["close"]
            else:
                shares[t] = 0

        # Month 1+ : collect dividends, track NAV
        for m in common_months[1:]:
            m_nav = 0
            m_income = 0
            for t in selected:
                entry = next((h for h in price_data.get(t, []) if h["date"] == m), None)
                if not entry or shares.get(t, 0) == 0:
                    continue
                m_nav += shares[t] * entry["close"]
                m_income += shares[t] * entry["dividend"]
            total_cash_received += m_income
            nav_values.append(m_nav)
            monthly_incomes.append(m_income)

        if not nav_values:
            continue

        final_nav = nav_values[-1]
        num_months = len(nav_values)

        # Total return = (NAV + cash received) / initial - 1
        avg_monthly_income = total_cash_received / num_months if num_months > 0 else 0
        total_return_pct = ((final_nav + total_cash_received) / initial_val - 1) * 100
        nav_change_pct = (final_nav / initial_val - 1) * 100
        available_income_per_10k = round(avg_monthly_income * 12, 2)  # annualized avg income per $10K
        avg_yield_pct = (avg_monthly_income * 12 / initial_val) * 100

        # Sharpe ratio from monthly total returns
        portfolio_monthly_rets = []
        for i in range(num_months):
            total_val = nav_values[i] + sum(monthly_incomes[:i+1])
            if i == 0:
                prev_total = initial_val
            else:
                prev_total = nav_values[i-1] + sum(monthly_incomes[:i])
            if prev_total > 0:
                m_ret = (total_val - prev_total) / prev_total
                portfolio_monthly_rets.append(m_ret)

        if len(portfolio_monthly_rets) >= 2:
            avg_mret = sum(portfolio_monthly_rets) / len(portfolio_monthly_rets)
            std_mret = (sum((r - avg_mret) ** 2 for r in portfolio_monthly_rets) / len(portfolio_monthly_rets)) ** 0.5
            sharpe = (avg_mret * 12 - 0.045) / (std_mret * (12 ** 0.5)) if std_mret > 0 else 0
        else:
            sharpe = 0

        # Income stability: downside-only deviation (drops penalized, growth ignored)
        non_zero = [i for i in monthly_incomes if i > 0]
        if len(non_zero) >= 4:
            changes = [(non_zero[i] - non_zero[i-1]) / non_zero[i-1] * 100 for i in range(1, len(non_zero))]
            neg = [abs(c) for c in changes if c < 0]
            cut_freq = len(neg) / len(changes) if changes else 0
            avg_depth = sum(neg) / len(neg) if neg else 0
            penalty = (cut_freq ** 0.4) * (avg_depth / 25)
            income_stability = round(max(0.05, min(1, 1 - penalty)), 3)
        else:
            income_stability = 0.5

        # Tax treatment: weighted average of each ETF's manual tax_treatment_score (0-1)
        scored = [tax_scores.get(t) for t in selected if tax_scores.get(t) is not None]
        tax_treatment = round(sum(scored) / len(scored), 3) if scored else 0.5

        all_portfolios.append({
            "etfs": [{"ticker": selected[i], "weight": round(weights[i] * 100, 1)} for i in range(len(selected))],
            "avg_yield": round(avg_yield_pct, 1),
            "total_return": round(total_return_pct, 1),
            "nav_change": round(nav_change_pct, 1),
            "sharpe": round(sharpe, 2),
            "monthly_income": round(avg_monthly_income, 2),
            "available_income_per_10k": available_income_per_10k,
            "num_etfs": len(selected),
            "income_stability": income_stability,
            "tax_treatment": round(tax_treatment, 3) if 'tax_treatment' in dir() else 0,
        })

    sort_keys = {
        "income": "monthly_income",
        "total_return": "total_return",
        "nav_change": "nav_change",
        "sharpe": "sharpe",
        "income_stability": "income_stability",
        "tax_treatment": "tax_treatment",
    }
    key = sort_keys.get(sort_by, "monthly_income")
    sorted_ports = sorted(all_portfolios, key=lambda x: -x[key])[:25]

    ticker_count = {}
    for p in sorted_ports:
        for e in p["etfs"]:
            ticker_count[e["ticker"]] = ticker_count.get(e["ticker"], 0) + 1

    for p in sorted_ports:
        for e in p["etfs"]:
            e["highlight"] = ticker_count[e["ticker"]] >= 3

    return {
        "portfolios": sorted_ports,
        "eligible_etfs": len(recent_tickers),
        "period": period,
        "total_simulations": n_simulations,
        "data_source": "live",
    }


@app.get("/api/tax-scores")
def get_tax_scores():
    conn = get_db()
    rows = conn.execute(
        "SELECT ticker, name, provider, current_yield, tax_treatment_score FROM etfs ORDER BY ticker"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/tax-admin")
def tax_admin_page():
    tmpl = _env.get_template("tax-admin.html")
    return HTMLResponse(tmpl.render())


@app.post("/api/tax-scores")
def update_tax_score(ticker: str = Form(...), score: str = Form("")):
    if score == "" or score == "null":
        # Clear the score
        conn = get_db()
        conn.execute(
            "UPDATE etfs SET tax_treatment_score = NULL WHERE ticker = ?",
            (ticker,)
        )
        conn.commit()
        conn.close()
        return {"status": "ok", "ticker": ticker, "score": None}
    try:
        score_val = max(0.0, min(1.0, float(score)))
    except (ValueError, TypeError):
        raise HTTPException(400, "Score must be a number 0.0-1.0 or empty to clear")
    conn = get_db()
    conn.execute(
        "UPDATE etfs SET tax_treatment_score = ? WHERE ticker = ?",
        (score_val, ticker)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "ticker": ticker, "score": score_val}


@app.get("/api/stats")
def overview_stats():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM etfs").fetchone()[0]
    avg_yield = conn.execute("SELECT AVG(current_yield) FROM etfs").fetchone()[0]
    providers = conn.execute("SELECT COUNT(DISTINCT provider) FROM etfs").fetchone()[0]
    newest = conn.execute(
        "SELECT ticker, name, current_yield, total_return_1yr FROM etfs WHERE current_yield IS NOT NULL ORDER BY inception_date DESC LIMIT 15"
    ).fetchall()
    conn.close()

    return {
        "total_etfs": count,
        "avg_yield": round(avg_yield, 2),
        "total_providers": providers,
        "newest_additions": [dict(r) for r in newest],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)
