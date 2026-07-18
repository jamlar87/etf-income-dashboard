#!/usr/bin/env python3
"""Recalculate income_stability_score using downside-only volatility."""
import sqlite3, math

DB = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"

def compute(dividends):
    if len(dividends) < 4:
        return 0.5
    changes = [(dividends[i] - dividends[i-1]) / dividends[i-1] * 100 for i in range(1, len(dividends))]
    neg = [abs(c) for c in changes if c < 0]
    freq = len(neg) / len(changes)
    avg_depth = sum(neg) / len(neg) if neg else 0
    penalty = (freq ** 0.4) * (avg_depth / 25)
    return round(max(0.05, min(1, 1 - penalty)), 3)

conn = sqlite3.connect(DB)
tickers = [r[0] for r in conn.execute("SELECT ticker FROM etfs").fetchall()]
count = 0
for t in tickers:
    divs = [r[0] for r in conn.execute(
        "SELECT dividend FROM price_history WHERE ticker = ? AND dividend > 0 ORDER BY date", (t,)
    ).fetchall()]
    score = compute(divs)
    conn.execute("UPDATE etfs SET income_stability_score = ? WHERE ticker = ?", (score, t))
    count += 1

conn.commit()

# Summary
by_range = {}
for r in conn.execute("SELECT income_stability_score FROM etfs").fetchall():
    s = r[0]
    bucket = f"{s*10//1*10:.0f}-{s*10//1*10+9:.0f}%" if s < 1 else "90-100%"
    by_range[bucket] = by_range.get(bucket, 0) + 1
conn.close()

print(f"Updated {count} ETFs")
for k in sorted(by_range.keys()):
    print(f"  {k}: {by_range[k]}")
print()
print("Sample:")
conn = sqlite3.connect(DB)
for r in conn.execute("SELECT ticker, income_stability_score FROM etfs ORDER BY income_stability_score DESC LIMIT 5").fetchall():
    print(f"  HIGH {r[0]}: {r[1]:.3f}")
for r in conn.execute("SELECT ticker, income_stability_score FROM etfs ORDER BY income_stability_score ASC LIMIT 5").fetchall():
    print(f"  LOW  {r[0]}: {r[1]:.3f}")
conn.close()
