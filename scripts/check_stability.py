#!/usr/bin/env python3
"""Test best-portfolios endpoint for income_stability."""
import json, time, urllib.request

t0 = time.time()
req = urllib.request.Request("http://localhost:8500/api/best-portfolios?period=1yr&sort_by=income_stability")
try:
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.loads(r.read())
    ps = d.get('portfolios', [])
    print(f"Elapsed: {time.time()-t0:.1f}s")
    print(f"Eligible: {d.get('eligible_etfs')}, Portfolios: {len(ps)}, Sims: {d.get('total_simulations')}")
    if ps:
        for i, p in enumerate(ps[:5]):
            stab = p.get('income_stability', 'MISSING')
            print(f"  #{i+1}: income_stability={stab}")
            if stab == 'MISSING':
                print(f"  KEYS: {list(p.keys())}")
    else:
        print(f"No portfolios: {dict(d)}")
except Exception as e:
    print(f"Error at {time.time()-t0:.1f}s: {e}")
