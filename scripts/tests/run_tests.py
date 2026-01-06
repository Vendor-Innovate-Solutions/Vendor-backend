#!/usr/bin/env python
"""
Test runner script for Vendor ERP Backend

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py accounting         # Run accounting tests
    python run_tests.py --coverage         # Run with coverage
    python run_tests.py --parallel         # Run in parallel
"""

import sys
import os
import subprocess


def get_python_executable():
    """Get the Python executable (prefer venv if available)"""
    # Check if we're in a virtual environment
    venv_python = os.path.join(os.path.dirname(__file__), 'env', 'Scripts', 'python.exe')
    if os.path.exists(venv_python):
        return venv_python
    # Fallback to current Python
    return sys.executable


def run_tests(app=None, coverage=False, parallel=False, verbosity=2):
    """
    Run Django tests with options
    
    Args:
        app: Specific app to test (e.g., 'accounting', 'inventory')
        coverage: Whether to run with coverage
        parallel: Whether to run tests in parallel
        verbosity: Verbosity level (0-3)
    """
    python_exe = get_python_executable()
    
    # Base command
    if coverage:
        cmd = [python_exe, '-m', 'coverage', 'run', '--source=.', 'manage.py', 'test']
    else:
        cmd = [python_exe, 'manage.py', 'test']
    
    # Add app filter
    if app:
        cmd.append(f'apps.{app}.tests')
    
    # Add options
    cmd.append(f'--verbosity={verbosity}')
    
    if parallel:
        cmd.append('--parallel')
    
    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    # If coverage, generate report
    if coverage and result.returncode == 0:
        print("\n" + "="*70)
        print("Coverage Report:")
        print("="*70)
        subprocess.run([python_exe, '-m', 'coverage', 'report'])
        print("\nGenerating HTML coverage report...")
        subprocess.run([python_exe, '-m', 'coverage', 'html'])
        print("HTML report generated in htmlcov/index.html")
    
    return result.returncode


def print_usage():
    """Print usage instructions"""
    print("""
Test Runner for Vendor ERP Backend
===================================

Usage:
    python run_tests.py [options] [app]

Apps:
    accounting       Run accounting tests
    company          Run company tests
    inventory        Run inventory tests
    party            Run party tests
    system           Run system tests
    voucher          Run voucher tests
    (no app)         Run all tests

Options:
    --coverage, -c   Run with coverage report
    --parallel, -p   Run tests in parallel
    --help, -h       Show this help message

Examples:
    python run_tests.py                      # All tests
    python run_tests.py accounting           # Accounting tests only
    python run_tests.py --coverage           # All tests with coverage
    python run_tests.py inventory --parallel # Inventory tests in parallel
    python run_tests.py -c accounting        # Accounting with coverage

Individual Test Commands:
    # Run specific test class
    python manage.py test apps.inventory.tests.test_fifo_stock_movement.FIFOStockMovementTest
    
    # Run specific test method
    python manage.py test apps.accounting.tests.test_concurrent_posting.ConcurrentPostingTest.test_double_posting_protection
    
    # Run with pytest
    pytest apps/inventory/tests/
    """)


if __name__ == '__main__':
    # Parse arguments
    args = sys.argv[1:]
    
    if '--help' in args or '-h' in args:
        print_usage()
        sys.exit(0)
    
    # Check for options
    coverage = '--coverage' in args or '-c' in args
    parallel = '--parallel' in args or '-p' in args
    
    # Remove flags from args
    app_args = [arg for arg in args if not arg.startswith('-')]
    
    # Get app name
    app = app_args[0] if app_args else None
    
    # Validate app name
    valid_apps = ['accounting', 'company', 'inventory', 'party', 'system', 'voucher']
    if app and app not in valid_apps:
        print(f"Error: Unknown app '{app}'")
        print(f"Valid apps: {', '.join(valid_apps)}")
        sys.exit(1)
    
    # Run tests
    exit_code = run_tests(app=app, coverage=coverage, parallel=parallel)
    sys.exit(exit_code)
