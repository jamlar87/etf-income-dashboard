#!/usr/bin/env python3
"""
Performance Benchmarking Script for Monte Carlo Simulation
Compares sequential vs parallel execution performance.

Usage:
    python benchmark_simulation.py --tickers "KQQQ,IGLD,RPAR" --iterations 1000 --window 12
"""

import argparse
import json
import os
import time
import sqlite3
from datetime import datetime
from statistics import mean, median

# Configuration
DB_PATH = "/media/james/SlowDisk1tb/etf-dashboard/etfs.db"
OUTPUT_DIR = "/home/james/etf-dashboard/performance-test"
BENCHMARK_RESULTS = os.path.join(OUTPUT_DIR, "benchmarks")

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def load_price_data(conn, tickers, window_months):
    """Load price history for tickers with sufficient data."""
    symbol_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    
    price_data = {}
    for ticker in symbol_list:
        rows = conn.execute(
            "SELECT date, close, dividend FROM price_history WHERE ticker=? ORDER BY date",
            (ticker,)
        ).fetchall()
        
        if len(rows) >= window_months:
            price_data[ticker] = [dict(r) for r in rows]
    
    return price_data

def run_sequential_simulation(price_data, window_months, iterations):
    """Run simulation sequentially (baseline)."""
    import random
    
    tickers_valid = list(price_data.keys())
    n = len(tickers_valid)
    weights = [1.0 / n] * n
    
    annualized_incomes = []
    total_returns = []
    nav_changes = []
    
    for _ in range(iterations):
        months = min(window_months, min(len(v) for v in price_data.values()))
        start_idx = random.randint(0, max(0, min(len(v) for v in price_data.values()) - months))
        
        portfolio_returns = []
        portfolio_divs = []
        
        for t in tickers_valid:
            prices = price_data[t]
            w = weights[tickers_valid.index(t)]
            window_prices = prices[start_idx:start_idx + months]
            
            if len(window_prices) < months:
                continue
            
            for i in range(1, len(window_prices)):
                ret = (window_prices[i]["close"] - window_prices[i-1]["close"]) / window_prices[i-1]["close"]
                div = window_prices[i]["dividend"] or 0
                div_yield = div / window_prices[i-1]["close"] if window_prices[i-1]["close"] > 0 else 0
                portfolio_returns.append(ret * w)
                portfolio_divs.append(div_yield * w)
        
        if portfolio_returns:
            total_ret = sum(portfolio_returns) + sum(portfolio_divs)
            total_returns.append(total_ret)
            nav_changes.append(sum(portfolio_returns))
            annualized_incomes.append(sum(portfolio_divs) * 12)
    
    return {
        "annualized_incomes": annualized_incomes,
        "total_returns": total_returns,
        "nav_changes": nav_changes
    }

def run_parallel_simulation(price_data, window_months, iterations):
    """Run simulation with parallel processing."""
    import random
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import concurrent.futures
    
    tickers_valid = list(price_data.keys())
    n = len(tickers_valid)
    weights = [1.0 / n] * n
    
    def run_batch(batch_size):
        batch_incomes = []
        batch_returns = []
        batch_navs = []
        
        for _ in range(batch_size):
            months = min(window_months, min(len(v) for v in price_data.values()))
            start_idx = random.randint(0, max(0, min(len(v) for v in price_data.values()) - months))
            
            portfolio_returns = []
            portfolio_divs = []
            
            for t in tickers_valid:
                prices = price_data[t]
                w = weights[tickers_valid.index(t)]
                window_prices = prices[start_idx:start_idx + months]
                
                if len(window_prices) < months:
                    continue
                
                for i in range(1, len(window_prices)):
                    ret = (window_prices[i]["close"] - window_prices[i-1]["close"]) / window_prices[i-1]["close"]
                    div = window_prices[i]["dividend"] or 0
                    div_yield = div / window_prices[i-1]["close"] if window_prices[i-1]["close"] > 0 else 0
                    portfolio_returns.append(ret * w)
                    portfolio_divs.append(div_yield * w)
            
            if portfolio_returns:
                total_ret = sum(portfolio_returns) + sum(portfolio_divs)
                batch_returns.append(total_ret)
                batch_navs.append(sum(portfolio_returns))
                batch_incomes.append(sum(portfolio_divs) * 12)
        
        return batch_incomes, batch_returns, batch_navs
    
    # Parallel execution
    batch_size = 100
    num_batches = (iterations + batch_size - 1) // batch_size
    
    annualized_incomes = []
    total_returns = []
    nav_changes = []
    
    with ThreadPoolExecutor(max_workers=min(4, num_batches)) as executor:
        futures = []
        for i in range(num_batches):
            current_batch_size = min(batch_size, iterations - i * batch_size)
            future = executor.submit(run_batch, current_batch_size)
            futures.append(future)
        
        for future in concurrent.futures.as_completed(futures):
            batch_incomes, batch_returns, batch_navs = future.result()
            annualized_incomes.extend(batch_incomes)
            total_returns.extend(batch_returns)
            nav_changes.extend(batch_navs)
    
    return {
        "annualized_incomes": annualized_incomes,
        "total_returns": total_returns,
        "nav_changes": nav_changes
    }

def compute_stats(data):
    """Compute statistics from simulation results."""
    from statistics import quantiles
    
    if not data:
        return {"mean": 0, "median": 0, "p5": 0, "p25": 0, "p75": 0, "p95": 0}
    
    stats = quantiles(data, n=100)
    return {
        "mean": round(mean(data), 2),
        "median": round(median(data), 2),
        "p5": round(stats[4], 2),
        "p25": round(stats[24], 2),
        "p75": round(stats[74], 2),
        "p95": round(stats[94], 2)
    }

def run_benchmark(tickers, iterations, window_months, warmup=True):
    """Run full benchmark comparison."""
    print(f"\n{'='*60}")
    print(f"Monte Carlo Simulation Benchmark")
    print(f"{'='*60}")
    print(f"Tickers: {tickers}")
    print(f"Iterations: {iterations}")
    print(f"Window: {window_months} months")
    print(f"{'='*60}\n")
    
    # Load data
    conn = get_db_connection()
    price_data = load_price_data(conn, tickers, window_months)
    conn.close()
    
    valid_tickers = list(price_data.keys())
    print(f"Valid tickers: {valid_tickers}")
    
    if not valid_tickers:
        print("ERROR: No tickers with sufficient history")
        return None
    
    # Warmup run (for JIT, caching, etc.)
    if warmup:
        print("\nWarmup run (sequential)...")
        run_sequential_simulation(price_data, window_months, min(100, iterations))
        print("Warmup complete")
    
    # Sequential benchmark
    print(f"\nRunning sequential simulation ({iterations} iterations)...")
    start_time = time.time()
    seq_results = run_sequential_simulation(price_data, window_months, iterations)
    seq_time = time.time() - start_time
    print(f"Sequential time: {seq_time:.2f}s")
    
    # Parallel benchmark
    print(f"\nRunning parallel simulation ({iterations} iterations)...")
    start_time = time.time()
    par_results = run_parallel_simulation(price_data, window_months, iterations)
    par_time = time.time() - start_time
    print(f"Parallel time: {par_time:.2f}s")
    
    # Calculate speedup
    speedup = seq_time / par_time if par_time > 0 else 0
    
    # Verify consistency
    print("\nVerifying result consistency...")
    
    # Compare key statistics
    seq_stats = {
        "income_mean": mean(seq_results["annualized_incomes"]) if seq_results["annualized_incomes"] else 0,
        "return_mean": mean(seq_results["total_returns"]) if seq_results["total_returns"] else 0
    }
    par_stats = {
        "income_mean": mean(par_results["annualized_incomes"]) if par_results["annualized_incomes"] else 0,
        "return_mean": mean(par_results["total_returns"]) if par_results["total_returns"] else 0
    }
    
    income_diff = abs(seq_stats["income_mean"] - par_stats["income_mean"])
    return_diff = abs(seq_stats["return_mean"] - par_stats["return_mean"])
    
    print(f"Income mean diff: {income_diff:.4f}")
    print(f"Return mean diff: {return_diff:.4f}")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tickers": valid_tickers,
        "iterations": iterations,
        "window_months": window_months,
        "sequential_time": round(seq_time, 3),
        "parallel_time": round(par_time, 3),
        "speedup": round(speedup, 2),
        "results_consistent": income_diff < 0.01 and return_diff < 0.01,
        "income_difference": round(income_diff, 4),
        "return_difference": round(return_diff, 4),
        "sequential_stats": {
            "annualized_income": compute_stats(seq_results["annualized_incomes"]),
            "total_return": compute_stats(seq_results["total_returns"]),
            "nav_change": compute_stats(seq_results["nav_changes"])
        },
        "parallel_stats": {
            "annualized_income": compute_stats(par_results["annualized_incomes"]),
            "total_return": compute_stats(par_results["total_returns"]),
            "nav_change": compute_stats(par_results["nav_changes"])
        }
    }
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Benchmark Monte Carlo simulation performance")
    parser.add_argument("--tickers", default="KQQQ,IGLD,RPAR", help="Comma-separated tickers")
    parser.add_argument("--iterations", type=int, default=1000, help="Number of iterations")
    parser.add_argument("--window", type=int, default=12, help="Lookback window in months")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warmup run")
    
    args = parser.parse_args()
    
    # Run benchmark
    results = run_benchmark(
        tickers=args.tickers,
        iterations=args.iterations,
        window_months=args.window,
        warmup=not args.no_warmup
    )
    
    if results:
        # Ensure output directory exists
        os.makedirs(BENCHMARK_RESULTS, exist_ok=True)
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = args.output or os.path.join(
            BENCHMARK_RESULTS, 
            f"benchmark_{timestamp}.json"
        )
        
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n{'='*60}")
        print("RESULTS SUMMARY")
        print(f"{'='*60}")
        print(f"Sequential time: {results['sequential_time']}s")
        print(f"Parallel time:   {results['parallel_time']}s")
        print(f"Speedup:         {results['speedup']}x")
        print(f"Consistent:      {results['results_consistent']}")
        print(f"\nResults saved to: {output_file}")
        
        # Print validation
        if results['speedup'] >= 3.0:
            print("\n✅ BENCHMARK PASSED: Achieved >=3x speedup")
        else:
            print(f"\n⚠️  BENCHMARK WARNING: Speedup {results['speedup']}x < 3x target")
        
        return results
    
    return None

if __name__ == "__main__":
    main()