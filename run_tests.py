"""
Test runner script for Vendor ERP Backend.

This script provides convenient commands for running different test suites.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --unit             # Run only unit tests
    python run_tests.py --api              # Run only API tests
    python run_tests.py --integration      # Run only integration tests
    python run_tests.py --fast             # Run fast tests only (exclude slow)
    python run_tests.py --coverage         # Run with coverage report
    python run_tests.py --parallel         # Run tests in parallel
    python run_tests.py --verbose          # Verbose output
    python run_tests.py --products         # Run product-related tests only
    python run_tests.py --file tests/api/test_products_api.py  # Run specific file
"""

import sys
import subprocess
import argparse


def run_tests(args):
    """Run pytest with specified arguments."""
    cmd = ['pytest']
    
    # Add markers
    if args.unit:
        cmd.extend(['-m', 'unit'])
    elif args.api:
        cmd.extend(['-m', 'api'])
    elif args.integration:
        cmd.extend(['-m', 'integration'])
    elif args.products:
        cmd.extend(['-m', 'products'])
    elif args.inventory:
        cmd.extend(['-m', 'inventory'])
    elif args.orders:
        cmd.extend(['-m', 'orders'])
    elif args.accounting:
        cmd.extend(['-m', 'accounting'])
    elif args.posting:
        cmd.extend(['-m', 'posting'])
    
    # Exclude slow tests if --fast
    if args.fast:
        cmd.extend(['-m', 'not slow'])
    
    # Coverage
    if args.coverage:
        cmd.extend([
            '--cov=apps',
            '--cov=core',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])
    
    # Parallel execution
    if args.parallel:
        cmd.extend(['-n', 'auto'])
    
    # Verbosity
    if args.verbose:
        cmd.append('-vv')
    else:
        cmd.append('-v')
    
    # Specific file
    if args.file:
        cmd.append(args.file)
    
    # Specific test
    if args.test:
        cmd.extend(['-k', args.test])
    
    # Failed tests only
    if args.failed:
        cmd.extend(['--lf'])  # Last failed
    
    # Stop on first failure
    if args.exitfirst:
        cmd.append('-x')
    
    # Show local variables in tracebacks
    if args.showlocals:
        cmd.append('-l')
    
    # Print the command
    print(f"Running: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run pytest
    result = subprocess.run(cmd)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description='Run tests for Vendor ERP Backend',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                          # Run all tests
  python run_tests.py --unit                   # Run unit tests only
  python run_tests.py --api --verbose          # Run API tests with verbose output
  python run_tests.py --coverage               # Run with coverage report
  python run_tests.py --fast --parallel        # Run fast tests in parallel
  python run_tests.py --products               # Run product-related tests
  python run_tests.py --file tests/api/test_products_api.py
  python run_tests.py --test test_create_product
  python run_tests.py --failed                 # Re-run failed tests
        """
    )
    
    # Test selection
    selection = parser.add_argument_group('Test Selection')
    selection.add_argument('--unit', action='store_true',
                          help='Run unit tests only')
    selection.add_argument('--api', action='store_true',
                          help='Run API tests only')
    selection.add_argument('--integration', action='store_true',
                          help='Run integration tests only')
    selection.add_argument('--products', action='store_true',
                          help='Run product-related tests')
    selection.add_argument('--inventory', action='store_true',
                          help='Run inventory-related tests')
    selection.add_argument('--orders', action='store_true',
                          help='Run order-related tests')
    selection.add_argument('--accounting', action='store_true',
                          help='Run accounting-related tests')
    selection.add_argument('--posting', action='store_true',
                          help='Run posting service tests')
    selection.add_argument('--fast', action='store_true',
                          help='Exclude slow tests')
    selection.add_argument('--file', type=str,
                          help='Run specific test file')
    selection.add_argument('--test', type=str,
                          help='Run tests matching pattern (pytest -k)')
    selection.add_argument('--failed', action='store_true',
                          help='Re-run only failed tests')
    
    # Test execution
    execution = parser.add_argument_group('Test Execution')
    execution.add_argument('--parallel', action='store_true',
                          help='Run tests in parallel')
    execution.add_argument('--coverage', action='store_true',
                          help='Generate coverage report')
    execution.add_argument('--verbose', action='store_true',
                          help='Verbose output')
    execution.add_argument('--exitfirst', '-x', action='store_true',
                          help='Stop on first failure')
    execution.add_argument('--showlocals', '-l', action='store_true',
                          help='Show local variables in tracebacks')
    
    args = parser.parse_args()
    
    # Run tests
    sys.exit(run_tests(args))


if __name__ == '__main__':
    main()
