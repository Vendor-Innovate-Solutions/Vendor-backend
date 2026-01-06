#!/usr/bin/env python
"""
Test Runner Script for Vendor ERP Backend

Runs all 6 comprehensive test suites covering:
1. Posting & Reversal Engine
2. Stock Reservation & Balance Updates
3. Invoice Generation & Outstanding
4. Payment Allocation
5. Credit Limit Guards
6. Financial Year Lock

Usage:
    python run_all_tests.py              # Run all tests
    python run_all_tests.py --verbose    # Verbose output
    python run_all_tests.py --coverage   # With coverage report
    python run_all_tests.py --fast       # Parallel execution
"""

import sys
import subprocess
from pathlib import Path

# ANSI color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    """Print colored header"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text.center(80)}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

def print_success(text):
    """Print success message"""
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    """Print error message"""
    print(f"{RED}❌ {text}{RESET}")

def print_info(text):
    """Print info message"""
    print(f"{YELLOW}ℹ️  {text}{RESET}")

def run_test_suite(test_file, description):
    """Run a single test suite"""
    print(f"\n{YELLOW}Running: {test_file} - {description}{RESET}")
    
    cmd = ["python", "-m", "pytest", f"tests/{test_file}", "-v", "--tb=short"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print_success(f"{test_file} - ALL TESTS PASSED")
            return True, result.stdout
        else:
            print_error(f"{test_file} - SOME TESTS FAILED")
            print(result.stdout)
            print(result.stderr)
            return False, result.stdout
    except Exception as e:
        print_error(f"Error running {test_file}: {str(e)}")
        return False, str(e)

def run_all_tests(verbose=False, coverage=False, fast=False):
    """Run all test suites"""
    print_header("VENDOR ERP BACKEND - COMPREHENSIVE TEST SUITE")
    
    test_suites = [
        ("test_posting_reversal.py", "Posting & Reversal Engine (16 tests)"),
        ("test_stock_reservation.py", "Stock Reservation & Balance Updates (13 tests)"),
        ("test_invoice_outstanding.py", "Invoice Generation & Outstanding (23 tests)"),
        ("test_payment_allocation.py", "Payment Allocation (13 tests)"),
        ("test_credit_guards.py", "Credit Limit Guards (18 tests)"),
        ("test_financial_year_lock.py", "Financial Year Lock (14 tests)"),
    ]
    
    results = []
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    print_info(f"Total Test Suites: {len(test_suites)}")
    print_info("Expected Total Tests: 97")
    
    # Run each test suite
    for test_file, description in test_suites:
        success, output = run_test_suite(test_file, description)
        results.append((test_file, success, output))
    
    # Summary
    print_header("TEST EXECUTION SUMMARY")
    
    for test_file, success, output in results:
        if success:
            print_success(f"{test_file} - PASSED")
        else:
            print_error(f"{test_file} - FAILED")
    
    # Count results
    passed_suites = sum(1 for _, success, _ in results if success)
    failed_suites = len(results) - passed_suites
    
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"Test Suites: {GREEN}{passed_suites} passed{RESET}, {RED}{failed_suites} failed{RESET}, {len(results)} total")
    
    if passed_suites == len(results):
        print(f"\n{GREEN}{'🎉 ALL TEST SUITES PASSED! 🎉'.center(80)}{RESET}")
        return 0
    else:
        print(f"\n{RED}{'⚠️  SOME TEST SUITES FAILED ⚠️'.center(80)}{RESET}")
        return 1

def run_with_coverage():
    """Run all tests with coverage report"""
    print_header("RUNNING TESTS WITH COVERAGE")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/test_posting_reversal.py",
        "tests/test_stock_reservation.py",
        "tests/test_invoice_outstanding.py",
        "tests/test_payment_allocation.py",
        "tests/test_credit_guards.py",
        "tests/test_financial_year_lock.py",
        "-v",
        "--cov=core",
        "--cov=apps",
        "--cov-report=html",
        "--cov-report=term"
    ]
    
    try:
        result = subprocess.run(cmd)
        
        if result.returncode == 0:
            print_success("Coverage report generated in htmlcov/index.html")
            return 0
        else:
            print_error("Some tests failed")
            return 1
    except Exception as e:
        print_error(f"Error running coverage: {str(e)}")
        return 1

def run_fast():
    """Run tests in parallel"""
    print_header("RUNNING TESTS IN PARALLEL (FAST MODE)")
    
    cmd = [
        "python", "-m", "pytest",
        "tests/test_posting_reversal.py",
        "tests/test_stock_reservation.py",
        "tests/test_invoice_outstanding.py",
        "tests/test_payment_allocation.py",
        "tests/test_credit_guards.py",
        "tests/test_financial_year_lock.py",
        "-n", "auto",
        "-v"
    ]
    
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        print_error(f"Error running fast mode: {str(e)}")
        print_info("Note: Fast mode requires pytest-xdist. Install with: pip install pytest-xdist")
        return 1

def main():
    """Main entry point"""
    args = sys.argv[1:]
    
    if "--coverage" in args or "-c" in args:
        return run_with_coverage()
    elif "--fast" in args or "-f" in args:
        return run_fast()
    elif "--help" in args or "-h" in args:
        print(__doc__)
        return 0
    else:
        verbose = "--verbose" in args or "-v" in args
        return run_all_tests(verbose=verbose)

if __name__ == "__main__":
    sys.exit(main())
