"""Backfill etf_universe + etfs metrics from ground-truth price_history.

Recomputes (trailing 12 months):
  current_yield, sharpe_ratio, total_return_1yr, nav_annual_change, div_payments_12m
for every ticker that has price_history. Tickers without price_history are left
untouched (their metrics stay NULL by design).

Also normalizes any stray non-month-start price_history dates (RINC 2025-09-18).
Idempotent + safe to re-run (UPDATEs only).

Run with --dry-run to print changes without writing.
"""
import sqlite3
import math
import os
import argparse
from datetime import datetime

DB = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"


def recompute(rows):
    """rows: list of (date, close, dividend) ascending. Window to trailing 12mo.
    Returns dict of recomputed metrics, or None if <2 valid rows."""
    rows = [r for r in rows if r[1] and r[1] > 0]
    if len(rows) < 2:
        return None
    latest_date = datetime.strptime(rows[-1][0], "%Y-%m-%d")
    cutoff = (latest_date.replace(year=latest_date.year - 1)).strftime("%Y-%m-%d")
    win = [r for r in rows if r[0] >= cutoff]
    if len(win) < 2:
        win = rows
    total_div = sum(r[2] or 0 for r in win if (r[2] or 0) > 0)
    latest_close = win[-1][1]
    first_close = win[0][1]

    live_yield = round(total_div / latest_close * 100, 2) if latest_close > 0 else 0.0
    total_return = round((latest_close + total_div) / first_close * 100 - 100, 2) if first_close > 0 else None
    nav = round(latest_close / first_close * 100 - 100, 2) if first_close > 0 else None
    div_payments = sum(1 for r in win if (r[2] or 0) > 0)

    sharpe = None
    if len(win) >= 6:
        rets = []
        for j in range(1, len(win)):
            prev, cur, dv = win[j - 1][1], win[j][1], win[j][2] or 0
            if prev and prev > 0 and cur and cur > 0:
                rets.append((cur + dv - prev) / prev)
        if len(rets) >= 3:
            avg = sum(rets) / len(rets)
            var = sum((r - avg) ** 2 for r in rets) / len(rets)
            std = math.sqrt(var)
            if std > 0:
                sharpe = round((avg * 12 - 0.03) / (std * math.sqrt(12)), 2)
    return {
        "current_yield": live_yield,
        "total_return_1yr": total_return,
        "nav_annual_change": nav,
        "sharpe_ratio": sharpe,
        "div_payments_12m": div_payments,
    }


def backfill_table(conn, table, dry_run, columns=("current_yield", "sharpe_ratio",
                                                    "total_return_1yr", "nav_annual_change",
                                                    "div_payments_12m")):
    tickers = [r[0] for r in conn.execute(
        f"SELECT DISTINCT ticker FROM {table} WHERE ticker IN (SELECT ticker FROM price_history)"
    ).fetchall()]
    updated = 0
    changes = []
    for t in tickers:
        rows = conn.execute(
            "SELECT date, close, dividend FROM price_history WHERE ticker=? ORDER BY date", (t,)
        ).fetchall()
        rc = recompute(rows)
        if rc is None:
            continue
        # Zero out yield if no dividends paid
        if rc["current_yield"] is None:
            rc["current_yield"] = 0.0
        # Keep only the columns that exist in this table
        rc = {k: rc[k] for k in columns}
        if dry_run:
            changes.append((t, rc))
            updated += 1
            continue
        set_clause = ", ".join(f"{k} = ?" for k in columns)
        params = [rc[k] for k in columns] + [t]
        conn.execute(f"UPDATE {table} SET {set_clause} WHERE ticker = ?", params)
        updated += 1
    if dry_run:
        print(f"  [{table}] would update {updated} tickers (dry-run, no writes)")
        for t, rc in changes[:8]:
            print(f"    {t}: " + ", ".join(f"{k}={v}" for k, v in rc.items()))
        if len(changes) > 8:
            print(f"    ... +{len(changes) - 8} more")
    else:
        print(f"  [{table}] updated {updated} tickers")
    return updated


def null_orphan_metrics(conn, dry_run):
    """Tickers with NO price_history cannot have real metrics. Their existing
    sharpe_ratio/total_return_1yr/nav_annual_change/current_yield are yfinance
    garbage (e.g. -393, 97%). Null them so they don't poison sorts."""
    orphans = conn.execute("""
        SELECT ticker FROM etf_universe
        WHERE ticker NOT IN (SELECT ticker FROM price_history)
          AND (sharpe_ratio IS NOT NULL OR total_return_1yr IS NOT NULL
               OR nav_annual_change IS NOT NULL OR current_yield IS NOT NULL)
    """).fetchall()
    n = len(orphans)
    if dry_run:
        print(f"  [orphans] would null metrics on {n} tickers with no price_history")
        return n
    for r in orphans:
        conn.execute("""
            UPDATE etf_universe SET
                sharpe_ratio = NULL,
                total_return_1yr = NULL,
                nav_annual_change = NULL,
                current_yield = NULL
            WHERE ticker = ?
        """, (r[0],))
    print(f"  [orphans] nulled corrupt metrics on {n} tickers with no price_history")
    return n


def normalize_dates(conn, dry_run):
    bad = conn.execute(
        "SELECT ticker, date FROM price_history WHERE date NOT LIKE '%-01'"
    ).fetchall()
    if not bad:
        print("  [dates] no stray non-month-start rows — clean")
        return 0
    if dry_run:
        print(f"  [dates] would normalize {len(bad)} rows: {[(r[0], r[1]) for r in bad]}")
        return len(bad)
    for r in bad:
        t, d = r[0], r[1]
        norm = d[:7] + "-01"
        row = conn.execute(
            "SELECT close, dividend FROM price_history WHERE ticker=? AND date=?", (t, d)
        ).fetchone()
        existing = conn.execute(
            "SELECT rowid, close, dividend FROM price_history WHERE ticker=? AND date=?", (t, norm)
        ).fetchone()
        if existing:
            new_close = row[0] if row[0] is not None else existing[1]
            new_div = (existing[2] or 0) + (row[1] or 0)
            conn.execute(
                "UPDATE price_history SET close=?, dividend=? WHERE rowid=?",
                (new_close, new_div, existing[0])
            )
            conn.execute("DELETE FROM price_history WHERE ticker=? AND date=?", (t, d))
        else:
            conn.execute("UPDATE price_history SET date=? WHERE ticker=? AND date=?", (norm, t, d))
    # Dedupe any residual (ticker, date) collisions
    conn.execute("""
        DELETE FROM price_history WHERE rowid NOT IN (
            SELECT MIN(rowid) FROM price_history GROUP BY ticker, date
        )
    """)
    remaining = conn.execute("SELECT COUNT(*) FROM price_history WHERE date NOT LIKE '%-01'").fetchone()[0]
    print(f"  [dates] normalized {len(bad)} rows; remaining non-month-start: {remaining}")
    return len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print changes, write nothing")
    args = ap.parse_args()
    dry = args.dry_run

    print(f"Backfill mode: {'DRY-RUN (no writes)' if dry else 'LIVE (writing to DB)'}")
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA busy_timeout=30000")

    print("\n[1] Normalize stray price_history dates")
    normalize_dates(conn, dry)

    print("\n[2] Backfill etf_universe")
    u = backfill_table(conn, "etf_universe", dry)

    print("\n[3] Backfill etfs (curated)")
    e = backfill_table(conn, "etfs", dry, columns=("current_yield", "sharpe_ratio",
                                                    "total_return_1yr", "nav_annual_change"))

    print("\n[4] Null corrupt metrics on tickers with no price_history")
    o = null_orphan_metrics(conn, dry)

    if not dry:
        conn.commit()
        print(f"\nCommitted. Universe: {u} tickers, Curated: {e} tickers, Orphans nulled: {o}.")
    else:
        print(f"\nDry-run complete. Would update universe={u}, curated={e}, null orphans={o}.")
    conn.close()


if __name__ == "__main__":
    main()
