"""
Quick Test Commands Reference
==============================

Copy and paste these commands to run tests quickly.
"""

# ============================================================================
# BASIC TEST COMMANDS
# ============================================================================

# Run ALL tests
python manage.py test

# Run with verbose output (recommended)
python manage.py test --verbosity=2

# Run keeping test database (faster for repeated runs)
python manage.py test --keepdb

# Run in parallel (faster on multi-core)
python manage.py test --parallel


# ============================================================================
# RUN SPECIFIC APP TESTS
# ============================================================================

# Inventory tests (FIFO, stock movements)
python manage.py test apps.inventory.tests

# Accounting tests (concurrent posting, double-entry)
python manage.py test apps.accounting.tests

# Company tests (financial year, company lock)
python manage.py test apps.company.tests

# Voucher tests (posting, numbering)
python manage.py test apps.voucher.tests

# System tests (idempotency, audit logs)
python manage.py test apps.system.tests

# Party tests (party-ledger integration)
python manage.py test apps.party.tests

# Integration tests (end-to-end flows)
python manage.py test tests.test_integration


# ============================================================================
# RUN SPECIFIC TEST CLASSES
# ============================================================================

# FIFO stock movement tests
python manage.py test apps.inventory.tests.test_fifo_stock_movement.FIFOStockMovementTest

# Concurrent posting tests
python manage.py test apps.accounting.tests.test_concurrent_posting.ConcurrentPostingTest

# Financial year close tests
python manage.py test apps.company.tests.test_financial_year.FinancialYearCloseTest

# Voucher posting tests
python manage.py test apps.voucher.tests.test_voucher_posting.VoucherPostingTest

# Idempotency key tests
python manage.py test apps.system.tests.test_idempotency.IdempotencyKeyTest

# Party ledger integration tests
python manage.py test apps.party.tests.test_party_ledger.PartyLedgerIntegrationTest


# ============================================================================
# RUN SPECIFIC TEST METHODS
# ============================================================================

# Test FIFO consumption
python manage.py test apps.inventory.tests.test_fifo_stock_movement.FIFOStockMovementTest.test_fifo_consumption_basic

# Test double-posting protection
python manage.py test apps.accounting.tests.test_concurrent_posting.ConcurrentPostingTest.test_double_posting_protection

# Test FY closing blocks posting
python manage.py test apps.company.tests.test_financial_year.FinancialYearCloseTest.test_posting_blocked_when_fy_closed

# Test idempotent posting
python manage.py test apps.system.tests.test_idempotency.IdempotencyKeyTest.test_idempotent_posting_with_same_key


# ============================================================================
# COVERAGE COMMANDS
# ============================================================================

# Install coverage (if not already installed)
pip install coverage

# Run tests with coverage
coverage run --source='.' manage.py test

# Show coverage report in terminal
coverage report

# Generate HTML coverage report
coverage html
# Open: htmlcov/index.html in browser

# Coverage for specific app
coverage run --source='apps/inventory' manage.py test apps.inventory.tests
coverage report


# ============================================================================
# USING THE TEST RUNNER SCRIPT
# ============================================================================

# Run all tests
python run_tests.py

# Run specific app
python run_tests.py inventory
python run_tests.py accounting
python run_tests.py company

# Run with coverage
python run_tests.py --coverage
python run_tests.py inventory --coverage

# Run in parallel
python run_tests.py --parallel

# Combined options
python run_tests.py accounting --coverage --parallel

# Show help
python run_tests.py --help


# ============================================================================
# USING PYTEST (Alternative)
# ============================================================================

# Install pytest-django (if not already installed)
pip install pytest pytest-django

# Run all tests
pytest

# Run specific directory
pytest apps/inventory/tests/

# Run with verbose output
pytest -v

# Run tests matching a keyword
pytest -k "fifo"
pytest -k "concurrent"
pytest -k "idempotency"

# Run with coverage
pytest --cov=apps --cov-report=html

# Run in parallel (requires pytest-xdist)
pip install pytest-xdist
pytest -n auto


# ============================================================================
# DEBUGGING TESTS
# ============================================================================

# Run with Python debugger (pdb)
python -m pdb manage.py test apps.inventory.tests

# Run single test with print statements visible
python manage.py test apps.inventory.tests --verbosity=2

# Run with warnings
python -Wd manage.py test


# ============================================================================
# CI/CD COMMANDS
# ============================================================================

# Fast test run for CI
python manage.py test --parallel --failfast

# With coverage for CI reporting
coverage run --source='.' manage.py test
coverage xml  # For CI tools like Jenkins, GitLab CI

# Generate JSON report
coverage json


# ============================================================================
# COMMON TEST FILTERS
# ============================================================================

# Run only fast tests (exclude slow tests)
python manage.py test --exclude-tag=slow

# Run only integration tests
python manage.py test tests.test_integration

# Run tests modified recently (using git)
git diff --name-only HEAD~1 | grep test_ | xargs python manage.py test


# ============================================================================
# TEST DATA CLEANUP
# ============================================================================

# Drop test database (if stuck)
# SQLite: Just delete db.sqlite3
# PostgreSQL:
# DROP DATABASE test_vendor_db;

# Recreate test database
python manage.py test --keepdb=False


# ============================================================================
# PERFORMANCE TESTING
# ============================================================================

# Time test execution
time python manage.py test

# Profile test execution
python -m cProfile -o test_profile.prof manage.py test
python -c "import pstats; p=pstats.Stats('test_profile.prof'); p.sort_stats('cumulative'); p.print_stats(20)"


# ============================================================================
# EXAMPLES: TYPICAL WORKFLOWS
# ============================================================================

# During development (fast feedback)
python manage.py test apps.inventory.tests --keepdb --failfast

# Before commit (comprehensive)
python run_tests.py --coverage

# For CI pipeline
python manage.py test --parallel --failfast && coverage report --fail-under=80

# Debugging a specific failure
python manage.py test apps.accounting.tests.test_concurrent_posting.ConcurrentPostingTest.test_double_posting_protection --verbosity=2


# ============================================================================
# EXPECTED OUTPUT
# ============================================================================

"""
When tests pass, you should see:

Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.................................................................
----------------------------------------------------------------------
Ran 65 tests in 15.234s

OK
Destroying test database for alias 'default'...
"""


# ============================================================================
# TROUBLESHOOTING
# ============================================================================

# If tests fail with import errors:
# 1. Check virtual environment is activated
# 2. Install requirements: pip install -r requirements.txt
# 3. Run migrations: python manage.py migrate

# If tests fail with database errors:
# 1. Drop test database
# 2. Run: python manage.py test --keepdb=False

# If specific test fails:
# 1. Run with verbosity=2 to see details
# 2. Check test data setup in setUp()
# 3. Verify model relationships

# If coverage is low:
# 1. Identify untested files: coverage report -m
# 2. Add tests for missing coverage
# 3. Target: 85%+ coverage
