"""Read-only data-quality audit for the ETF dashboard.

Compares the columns the dashboard trusts (etf_universe / etfs) against
ground-truth recomputed from price_history. Reports discrepancies; writes nothing.
"""
import sqlite3
import math
import os

DB = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def recompute(ticker, rows):
    """Recompute yield/sharpe/total_return/nav/div_payments from price_history rows
    (date, close, dividend), ordered ascending, windowed to TRAILING 12 MONTHS
    (last 13 months of data). Returns dict or None if too few rows."""
    rows = [r for r in rows if r["close"] and r["close"] > 0]
    if len(rows) < 2:
        return None
    # Window to trailing 12 months: latest row date minus 12 months
    from datetime import datetime
    latest_date = datetime.strptime(rows[-1]["date"], "%Y-%m-%d")
    cutoff = (latest_date.replace(year=latest_date.year - 1)).strftime("%Y-%m-%d")
    win = [r for r in rows if r["date"] >= cutoff]
    if len(win) < 2:
        win = rows  # fall back to full history if <2 in window
    total_div = sum(r["dividend"] or 0 for r in win if (r["dividend"] or 0) > 0)
    latest_close = win[-1]["close"]
    first_close = win[0]["close"]
    live_yield = round(total_div / latest_close * 100, 2) if latest_close > 0 else None
    total_return = round((latest_close + total_div) / first_close * 100 - 100, 2) if first_close > 0 else None
    nav = round(latest_close / first_close * 100 - 100, 2) if first_close > 0 else None
    div_payments = sum(1 for r in win if (r["dividend"] or 0) > 0)

    # Sharpe from monthly returns (need >=3 return observations)
    sharpe = None
    if len(rows) >= 6:
        rets = []
        for j in range(1, len(rows)):
            prev, cur, dv = rows[j - 1]["close"], rows[j]["close"], rows[j]["dividend"] or 0
            if prev and prev > 0 and cur and cur > 0:
                rets.append((cur + dv - prev) / prev)
        if len(rets) >= 3:
            avg = sum(rets) / len(rets)
            var = sum((r - avg) ** 2 for r in rets) / len(rets)
            std = math.sqrt(var)
            if std > 0:
                sharpe = round((avg * 12 - 0.03) / (std * math.sqrt(12)), 2)
    return {
        "live_yield": live_yield,
        "total_return": total_return,
        "nav": nav,
        "div_payments": div_payments,
        "sharpe": sharpe,
    }


def main():
    print("=" * 70)
    print("ETF DASHBOARD — DATA QUALITY AUDIT (read-only)")
    print("=" * 70)

    # ---- 0. Row counts ----
    curated = conn.execute("SELECT COUNT(*) FROM etfs").fetchone()[0]
    universe = conn.execute("SELECT COUNT(*) FROM etf_universe WHERE is_active = 1").fetchone()[0]
    price_tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM price_history").fetchone()[0]
    print(f"\netfs (curated):        {curated}")
    print(f"etf_universe (active): {universe}")
    print(f"price_history tickers: {price_tickers}")

    # ---- 1. Date-format integrity (MC corruption risk) ----
    bad_dates = conn.execute(
        "SELECT COUNT(*) FROM price_history WHERE date NOT LIKE '%-01'"
    ).fetchone()[0]
    bad_tickers = conn.execute(
        "SELECT DISTINCT ticker FROM price_history WHERE date NOT LIKE '%-01'"
    ).fetchall()
    print(f"\n[1] DATE FORMAT")
    print(f"  non-month-start rows: {bad_dates}  ({'CLEAN' if bad_dates == 0 else 'CORRUPTED'})")
    if bad_tickers:
        print(f"  tickers affected: {', '.join(t['ticker'] for t in bad_tickers)}")

    # ---- 2. Universe columns backed by price_history ----
    # Pull all universe tickers that have price_history, compare stored vs recomputed.
    pairs = conn.execute("""
        SELECT u.ticker, u.current_yield, u.sharpe_ratio, u.total_return_1yr,
               u.nav_annual_change, u.div_payments_12m, u.aum, u.is_leveraged
        FROM etf_universe u
        WHERE EXISTS (SELECT 1 FROM price_history p WHERE p.ticker = u.ticker)
    """).fetchall()

    yield_bad, sharpe_bad, tr_bad, nav_bad, div_bad = [], [], [], [], []
    yield_abs_worst = []
    no_price_for_universe = conn.execute("""
        SELECT COUNT(*) FROM etf_universe u
        WHERE is_active=1 AND NOT EXISTS (SELECT 1 FROM price_history p WHERE p.ticker=u.ticker)
    """).fetchone()[0]

    checked = 0
    for p in pairs:
        t = p["ticker"]
        rows = conn.execute(
            "SELECT date, close, dividend FROM price_history WHERE ticker=? ORDER BY date", (t,)
        ).fetchall()
        rc = recompute(t, rows)
        if rc is None:
            continue
        checked += 1

        # Yield: stored vs live. Flag if stored is >1.5x or <0.5x live, OR sign flip (stored>0, live=0)
        sy = p["current_yield"]
        ly = rc["live_yield"]
        if sy is not None and ly is not None:
            if ly == 0 and sy > 1:
                yield_bad.append((t, sy, ly, "stored yield but no dividends paid"))
            elif ly > 0 and (sy is None or sy <= 0 or sy > ly * 2 or sy < ly * 0.5):
                yield_bad.append((t, sy, ly, "discrepancy >2x"))
        elif sy is not None and sy > 1 and ly == 0:
            yield_bad.append((t, sy, ly, "stored yield, live=0"))
        if ly is not None:
            yield_abs_worst.append((t, abs((sy or 0) - ly), sy, ly))

        # Sharpe
        ss = p["sharpe_ratio"]
        rs = rc["sharpe"]
        if rs is not None and ss is not None and abs(ss - rs) > 1.0:
            sharpe_bad.append((t, ss, rs))

        # total_return_1yr
        str_ = p["total_return_1yr"]
        rtr = rc["total_return"]
        if rtr is not None and str_ is not None and abs(str_ - rtr) > 10:
            tr_bad.append((t, str_, rtr))

        # nav_annual_change
        snav = p["nav_annual_change"]
        rnav = rc["nav"]
        if rnav is not None and snav is not None and abs(snav - rnav) > 10:
            nav_bad.append((t, snav, rnav))

        # div_payments_12m
        sdp = p["div_payments_12m"]
        rdp = rc["div_payments"]
        if sdp is not None and rdp is not None and sdp != rdp:
            div_bad.append((t, sdp, rdp))

    print(f"\n[2] UNIVERSE COLUMNS vs price_history (checked {checked} tickers with >=2 price rows)")
    print(f"  universe tickers w/ NO price_history: {no_price_for_universe}")

    print(f"\n  current_yield mismatches: {len(yield_bad)}")
    for t, sy, ly, note in sorted(yield_bad, key=lambda x: -(x[1] or 0))[:15]:
        print(f"    {t:6} stored={sy!s:>8}  live={ly!s:>7}  [{note}]")
    if len(yield_bad) > 15:
        print(f"    ... and {len(yield_bad) - 15} more")

    print(f"\n  sharpe_ratio mismatches (>1.0 abs): {len(sharpe_bad)}")
    for t, ss, rs in sorted(sharpe_bad, key=lambda x: abs(x[1] - x[2]), reverse=True)[:15]:
        print(f"    {t:6} stored={ss!s:>8}  live={rs!s:>7}")
    if len(sharpe_bad) > 15:
        print(f"    ... and {len(sharpe_bad) - 15} more")

    print(f"\n  total_return_1yr mismatches (>10pp): {len(tr_bad)}")
    for t, s, r in sorted(tr_bad, key=lambda x: abs(x[1] - x[2]), reverse=True)[:10]:
        print(f"    {t:6} stored={s!s:>8}  live={r!s:>7}")
    if len(tr_bad) > 10:
        print(f"    ... and {len(tr_bad) - 10} more")

    print(f"\n  nav_annual_change mismatches (>10pp): {len(nav_bad)}")
    for t, s, r in sorted(nav_bad, key=lambda x: abs(x[1] - x[2]), reverse=True)[:10]:
        print(f"    {t:6} stored={s!s:>8}  live={r!s:>7}")
    if len(nav_bad) > 10:
        print(f"    ... and {len(nav_bad) - 10} more")

    print(f"\n  div_payments_12m mismatches: {len(div_bad)}")
    for t, s, r in sorted(div_bad, key=lambda x: abs(x[1] - x[2]), reverse=True)[:10]:
        print(f"    {t:6} stored={s!s:>4}  live={r!s:>4}")
    if len(div_bad) > 10:
        print(f"    ... and {len(div_bad) - 10} more")

    # ---- 3. Curated etfs table — same checks ----
    c_pairs = conn.execute("""
        SELECT e.ticker, e.current_yield, e.sharpe_ratio, e.total_return_1yr, e.nav_annual_change
        FROM etfs e
        WHERE EXISTS (SELECT 1 FROM price_history p WHERE p.ticker = e.ticker)
    """).fetchall()
    cy_bad, cs_bad = [], []
    cchecked = 0
    for p in c_pairs:
        t = p["ticker"]
        rows = conn.execute(
            "SELECT date, close, dividend FROM price_history WHERE ticker=? ORDER BY date", (t,)
        ).fetchall()
        rc = recompute(t, rows)
        if rc is None:
            continue
        cchecked += 1
        sy, ly = p["current_yield"], rc["live_yield"]
        if ly is not None and sy is not None and (ly == 0 and sy > 1 or (ly > 0 and (sy <= 0 or sy > ly * 2 or sy < ly * 0.5))):
            cy_bad.append((t, sy, ly))
        ss, rs = p["sharpe_ratio"], rc["sharpe"]
        if rs is not None and ss is not None and abs(ss - rs) > 1.0:
            cs_bad.append((t, ss, rs))

    print(f"\n[3] CURATED etfs TABLE vs price_history (checked {cchecked})")
    print(f"  current_yield mismatches: {len(cy_bad)}")
    for t, sy, ly in sorted(cy_bad, key=lambda x: -(x[1] or 0))[:10]:
        print(f"    {t:6} stored={sy!s:>8}  live={ly!s:>7}")
    print(f"  sharpe_ratio mismatches (>1.0): {len(cs_bad)}")
    for t, ss, rs in sorted(cs_bad, key=lambda x: abs(x[1] - x[2]), reverse=True)[:10]:
        print(f"    {t:6} stored={ss!s:>8}  live={rs!s:>7}")

    # ---- 4. Null-column coverage (sparse-table check) ----
    print(f"\n[4] NULL / SPARSE COLUMN COVERAGE (etf_universe, active)")
    cols = ["current_yield", "sharpe_ratio", "total_return_1yr", "nav_annual_change",
            "div_payments_12m", "aum", "expense_ratio", "is_leveraged"]
    for c in cols:
        n = conn.execute(f"SELECT COUNT(*) FROM etf_universe WHERE is_active=1 AND {c} IS NULL").fetchone()[0]
        if n:
            print(f"    {c:20} NULL in {n} rows")
    print("    (no output above = all populated)")

    print("\n" + "=" * 70)
    print("AUDIT COMPLETE — no changes written")
    print("=" * 70)


if __name__ == "__main__":
    main()
    conn.close()
