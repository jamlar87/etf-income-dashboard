#!/usr/bin/env python3
"""
Verification Script for Monte Carlo Simulation Enhancement
Tests all 3 components: parallel processing, documentation, and benchmarking
"""
import os
import sys
import json
import time
import statistics
from pathlib import Path

# Configuration
BASE_DIR = Path("/home/james/etf-dashboard")
DOCS_DIR = BASE_DIR / "docs"
BENCHMARK_SCRIPT = BASE_DIR / "benchmark_simulation.py"
APP_FILE = BASE_DIR / "app.py"
SKILL_FILE = BASE_DIR / "simulation-monte-carlo" / "SKILL.md"

# Test results
results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test_file_exists(path, description):
    """Test if a file exists."""
    if path.exists():
        results["passed"].append(f"✓ {description}: {path}")
        return True
    else:
        results["failed"].append(f"✗ {description}: {path} NOT FOUND")
        return False

def test_file_content(path, required_strings, description):
    """Test if file contains required strings."""
    if not path.exists():
        results["failed"].append(f"✗ {description}: File not found")
        return False
    
    content = path.read_text()
    missing = []
    for s in required_strings:
        if s not in content:
            missing.append(s)
    
    if missing:
        results["failed"].append(f"✗ {description}: Missing {missing}")
        return False
    else:
        results["passed"].append(f"✓ {description}: All required content found")
        return True

def test_python_syntax(path, description):
    """Test if Python file has valid syntax."""
    try:
        with open(path) as f:
            compile(f.read(), path, 'exec')
        results["passed"].append(f"✓ {description}: Valid syntax")
        return True
    except SyntaxError as e:
        results["failed"].append(f"✗ {description}: Syntax error - {e}")
        return False

def test_yaml_frontmatter(path, description):
    """Test if file has valid YAML frontmatter."""
    if not path.exists():
        results["failed"].append(f"✗ {description}: File not found")
        return False
    
    content = path.read_text()
    if content.startswith('---') and 'title:' in content and 'description:' in content:
        results["passed"].append(f"✓ {description}: Valid YAML frontmatter")
        return True
    else:
        results["failed"].append(f"✗ {description}: Missing or invalid YAML frontmatter")
        return False

def test_app_endpoint():
    """Test if the new endpoint exists in app.py."""
    required_code = [
        "@app.get(\"/api/basket/simulate-window\")",
        "ThreadPoolExecutor",
        "annualized_incomes",
        "total_returns"
    ]
    return test_file_content(APP_FILE, required_code, "✓ app.py Monte Carlo endpoint")

def test_docs_content():
    """Test documentation content."""
    required_sections = [
        "Monte Carlo Simulation",
        "Parameter",
        "Interpretation",
        "Troubleshooting"
    ]
    return test_file_content(DOCS_DIR / "simulation-guide.md", required_sections, "✓ User documentation")

def test_benchmark_script():
    """Test benchmark script."""
    required_features = [
        "parallel",
        "sequential",
        "speedup"
    ]
    return test_file_content(BENCHMARK_SCRIPT, required_features, "✓ Benchmark script")

def test_skill_documentation():
    """Test SKILL.md documentation."""
    return test_yaml_frontmatter(SKILL_FILE, "✓ Skill documentation")

def main():
    """Run all verification tests."""
    print("=" * 60)
    print("ETF Dashboard Monte Carlo Simulation Verification")
    print("=" * 60)
    print()
    
    # Test 1: File existence
    print("📁 Testing file existence...")
    test_file_exists(BASE_DIR, "Base directory")
    test_file_exists(DOCS_DIR, "Documentation directory")
    test_file_exists(DOCS_DIR / "simulation-guide.md", "User guide")
    test_file_exists(BENCHMARK_SCRIPT, "Benchmark script")
    test_file_exists(SKILL_FILE, "Skill documentation")
    test_file_exists(APP_FILE, "Application file")
    print()
    
    # Test 2: Python syntax
    print("🐍 Testing Python syntax...")
    test_python_syntax(APP_FILE, "app.py")
    test_python_syntax(BENCHMARK_SCRIPT, "benchmark_simulation.py")
    print()
    
    # Test 3: Documentation content
    print("📚 Testing documentation content...")
    test_docs_content()
    test_skill_documentation()
    print()
    
    # Test 4: Core functionality
    print("⚙️ Testing core functionality...")
    test_app_endpoint()
    test_benchmark_script()
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Passed: {len(results['passed'])}")
    print(f"✗ Failed: {len(results['failed'])}")
    print()
    
    if results['passed']:
        print("PASSED TESTS:")
        for p in results['passed']:
            print(f"  {p}")
        print()
    
    if results['failed']:
        print("FAILED TESTS:")
        for f in results['failed']:
            print(f"  {f}")
        print()
    
    # Overall result
    if results['failed']:
        print("❌ VERIFICATION FAILED")
        return 1
    else:
        print("✅ ALL VERIFICATIONS PASSED")
        return 0

if __name__ == "__main__":
    sys.exit(main())