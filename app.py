"""High Yield Income ETF Dashboard - FastAPI Backend"""
import sqlite3
import random
import math
from datetime import datetime, timedelta
from functools import lru_cache
from fastapi import FastAPI, Query, HTTPException
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
        "inception_date", "ticker", "name", "provider"
    ]
    if sort_by in allowed_sorts:
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort_by} {direction} NULLS LAST"
    else:
        query += " ORDER BY current_yield DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/etfs/new")
def newest_additions():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM etfs WHERE is_new = 1 ORDER BY date_added DESC"
    ).fetchall()
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
def leaderboard():
    conn = get_db()
    etfs = conn.execute("SELECT * FROM etfs").fetchall()
    conn.close()

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

    categories["highest_yield"] = sorted(etf_list, key=lambda x: -x["current_yield"])[:10]
    categories["best_dist_coverage"] = sorted(etf_list, key=lambda x: -x["distribution_coverage"])[:10]

    for period in ["total_return_1yr", "total_return_3yr", "total_return_5yr", "total_return_10yr"]:
        valid = [e for e in etf_list if e[period] is not None]
        categories[f"best_{period}"] = sorted(valid, key=lambda x, p=period: -x[p])[:10]

    categories["best_sharpe"] = sorted(etf_list, key=lambda x: -x["sharpe_ratio"])[:10]
    categories["best_sortino"] = sorted(etf_list, key=lambda x: -x["sortino_ratio"])[:10]
    categories["best_calmar"] = sorted(etf_list, key=lambda x: -x["calmar_ratio"])[:10]
    categories["best_nav_growth"] = sorted(etf_list, key=lambda x: -x["nav_annual_change"])[:10]

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

    yields = [e["current_yield"] for e in etf_list]
    avg_yield = round(sum(yields) / len(yields), 2)
    stats = {
        "total_etfs": len(etf_list),
        "avg_yield": avg_yield,
        "highest_yield": max(yields),
        "providers": len(set(e["provider"] for e in etf_list)),
    }

    return {"stats": stats, "categories": leaderboard}


@app.get("/api/beta-correlation")
def beta_correlation(period: str = Query("1yr")):
    conn = get_db()
    rows = conn.execute("""
        SELECT ticker, name, provider, beta_sp500, correlation_sp500, current_yield
        FROM etfs WHERE beta_sp500 IS NOT NULL
    """).fetchall()
    conn.close()

    points = []
    for r in rows:
        points.append({
            "ticker": r["ticker"],
            "name": r["name"],
            "provider": r["provider"],
            "beta": r["beta_sp500"],
            "correlation": r["correlation_sp500"],
            "yield": r["current_yield"],
        })
    return {"points": points, "period": period}


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
        "monthly_nav": monthly_nav,
        "monthly_income": monthly_income,
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

    # Find tickers with sufficient history
    cutoff = f"datetime('now', '-{lookback_months + 1} months')"
    rows = conn.execute(f"""
        SELECT DISTINCT ticker FROM price_history
        WHERE date <= {cutoff}
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

    if len(recent_tickers) < 4:
        return {"portfolios": [], "eligible_etfs": len(recent_tickers), "period": period}

    # Run Monte Carlo
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

        # Simulate this portfolio over the lookback period
        total_ret = 0
        monthly_rets = []
        initial_val = 10000
        nav_val = initial_val
        total_income = 0

        for i, t in enumerate(selected):
            hist = price_data[t][-lookback_months:]
            if len(hist) < 2:
                continue

            start_p = hist[0]["close"]
            end_p = hist[-1]["close"]
            divs = sum(h["dividend"] for h in hist[1:])

            if start_p > 0:
                etf_ret = (end_p + divs) / start_p - 1
                total_ret += etf_ret * weights[i]

            # Monthly returns for Sharpe
            for j in range(1, len(hist)):
                m_ret = (hist[j]["close"] + hist[j]["dividend"]) / hist[j - 1]["close"] - 1
                monthly_rets.append(m_ret * weights[i])

            # Income calc
            avg_monthly_div = divs / max(len(hist) - 1, 1)
            total_income += avg_monthly_div / hist[0]["close"] * nav_val * weights[i]

        if monthly_rets:
            avg_mret = sum(monthly_rets) / len(monthly_rets)
            std_mret = (sum((r - avg_mret) ** 2 for r in monthly_rets) / len(monthly_rets)) ** 0.5
            sharpe = (avg_mret * 12 - 0.045) / (std_mret * (12 ** 0.5)) if std_mret > 0 else 0
        else:
            sharpe = 0

        nav_change = (nav_val * (1 + total_ret) - nav_val) / nav_val * 100

        all_portfolios.append({
            "etfs": [{"ticker": selected[i], "weight": round(weights[i] * 100, 1)} for i in range(len(selected))],
            "avg_yield": round(total_income / nav_val * 100, 2),
            "total_return": round(total_ret * 100, 2),
            "nav_change": round(nav_change, 2),
            "sharpe": round(sharpe, 2),
            "monthly_income": round(total_income, 2),
        })

    sort_keys = {
        "income": "monthly_income",
        "total_return": "total_return",
        "nav_change": "nav_change",
        "sharpe": "sharpe",
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


@app.get("/api/stats")
def overview_stats():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM etfs").fetchone()[0]
    avg_yield = conn.execute("SELECT AVG(current_yield) FROM etfs").fetchone()[0]
    providers = conn.execute("SELECT COUNT(DISTINCT provider) FROM etfs").fetchone()[0]
    newest = conn.execute(
        "SELECT ticker, name, current_yield, total_return_1yr FROM etfs WHERE is_new=1 ORDER BY date_added DESC"
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
