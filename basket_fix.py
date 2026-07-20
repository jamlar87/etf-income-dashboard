@app.get("/api/basket")
def basket(tickers: str = Query(""), tax_rate: float = Query(0.20)):
    """Blended metrics for a user-selected basket of ETFs (F1). Also computes
    per-ticker max drawdown + dividend-cut count from price_history (F4)."""
    conn = get_db()
    symbol_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if not symbol_list:
        conn.close()
        return {"tickers": [], "blended": None, "holdings": []}

    placeholders = ",".join("?" * len(symbol_list))
    rows = conn.execute(f"""
        SELECT
            u.ticker,
            COALESCE(e.name, u.name) AS name,
            COALESCE(e.provider, u.provider) AS provider,
            COALESCE(e.current_yield, u.current_yield) AS current_yield,
            COALESCE(e.nav_annual_change, u.nav_annual_change) AS nav_annual_change,
            COALESCE(e.sharpe_ratio, u.sharpe_ratio) AS sharpe_ratio,
            COALESCE(e.expense_ratio, u.expense_ratio) AS expense_ratio,
            COALESCE(e.tax_treatment_score, u.tax_treatment_score) AS tax_treatment_score,
            COALESCE(e.income_stability_score, u.income_stability_score) AS income_stability_score,
            COALESCE(e.correlation_sp500, u.correlation_sp500) AS correlation_sp500,
            COALESCE(e.real_yield, u.real_yield) AS real_yield_stored,
            COALESCE(e.div_cagr_5yr, u.div_cagr_5yr) AS div_cagr_5yr
        FROM etf_universe u
        LEFT JOIN etfs e ON u.ticker = e.ticker
        WHERE u.ticker IN ({placeholders})
    """, symbol_list).fetchall()

    holdings = []
    for r in rows:
        d = dict(r)
        _enrich_derived(d, tax_rate)
        # Drawdown + div-cut from price_history (F4)
        ph = conn.execute(
            "SELECT date, close, dividend FROM price_history WHERE ticker=? ORDER BY date",
            (d["ticker"],)
        ).fetchall()
        closes = [x["close"] for x in ph if x["close"] and x["close"] > 0]
        divs = [x["dividend"] or 0 for x in ph]
        max_dd = None
        if len(closes) >= 2:
            peak = closes[0]
            worst = 0.0
            for c in closes:
                if c > peak:
                    peak = c
                dd = (c - peak) / peak
                if dd < worst:
                    worst = dd
            max_dd = round(worst * 100, 1)
        div_cuts = 0
        for i in range(1, len(divs)):
            if divs[i - 1] and divs[i] >= 0 and divs[i] < divs[i - 1] * 0.8:
                div_cuts += 1
        d["max_drawdown"] = max_dd
        d["div_cuts_12m"] = div_cuts
        d["is_trap"] = bool((d["real_yield"] is not None and d["real_yield"] < 0) or div_cuts > 0)
        holdings.append(d)

    conn.close()

    if not holdings:
        return {"tickers": symbol_list, "blended": None, "holdings": []}

    n = len(holdings)
    def avg(key):
        vals = [h[key] for h in holdings if h.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None
    def avg_corr():
        corrs = [h["correlation_sp500"] for h in holdings if h.get("correlation_sp500") is not None]
        return round(sum(corrs) / len(corrs), 2) if corrs else None

    blended = {
        "count": n,
        "current_yield": avg("current_yield"),
        "after_tax_yield": avg("after_tax_yield"),
        "real_yield": avg("real_yield"),
        "net_real_yield": avg("net_real_yield"),
        "quality_score": avg("quality_score"),
        "avg_sharpe": avg("sharpe_ratio"),
        "avg_expense": avg("expense_ratio"),
        "avg_correlation_sp500": avg_corr(),
        "avg_max_drawdown": avg("max_drawdown"),
        "trap_count": sum(1 for h in holdings if h["is_trap"]),
    }
    return {"tickers": symbol_list, "blended": blended, "holdings": holdings}