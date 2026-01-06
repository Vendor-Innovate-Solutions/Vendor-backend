# Test Suite for Vendor ERP Backend

This directory contains comprehensive tests for the Vendor ERP backend system based on enterprise-grade ERP standards (Tally/SAP-class systems).

## Test Structure

```
tests/
├── apps/
│   ├── accounting/
│   │   └── tests/
│   │       ├── test_concurrent_posting.py
│   │       └── __init__.py
│   ├── company/
│   │   └── tests/
│   │       ├── test_financial_year.py
│   │       └── __init__.py
│   ├── inventory/
│   │   └── tests/
│   │       ├── test_fifo_stock_movement.py
│   │       └── __init__.py
│   ├── party/
│   │   └── tests/
│   │       ├── test_party_ledger.py
│   │       └── __init__.py
│   ├── system/
│   │   └── tests/
│   │       ├── test_idempotency.py
│   │       └── __init__.py
│   └── voucher/
│       └── tests/
│           ├── test_voucher_posting.py
│           └── __init__.py
```

## Test Categories

### 1. Inventory Tests (`apps/inventory/tests/`)

**File:** `test_fifo_stock_movement.py`

Tests FIFO (First-In-First-Out) stock valuation and batch allocation:
- ✅ FIFO consumption logic - oldest batches consumed first
- ✅ Multi-batch consumption across multiple stock batches
- ✅ Stock receipt and balance updates
- ✅ Insufficient stock error handling
- ✅ Weighted average rate calculations
- ✅ Stock movement tracking

**Key Test Classes:**
- `FIFOStockMovementTest` - Core FIFO logic
- `StockValuationTest` - Valuation calculations

### 2. Accounting Tests (`apps/accounting/tests/`)

**File:** `test_concurrent_posting.py`

Tests thread-safe posting and concurrency protection:
- ✅ Double-posting protection - only one thread can post
- ✅ SELECT FOR UPDATE locking mechanism
- ✅ Sequential posting of multiple vouchers
- ✅ Double-entry balance validation (DR = CR)
- ✅ Unbalanced voucher error handling
- ✅ Complex multi-line voucher validation

**Key Test Classes:**
- `ConcurrentPostingTest` - Thread safety with `TransactionTestCase`
- `DoubleEntryValidationTest` - Accounting rules validation

### 3. Company Tests (`apps/company/tests/`)

**File:** `test_financial_year.py`

Tests financial year closing and company lock enforcement:
- ✅ FY closing blocks posting - audit compliance
- ✅ FY opening allows posting
- ✅ Company lock (accounting freeze) enforcement
- ✅ Only one current FY per company constraint
- ✅ FY date validation (start < end)
- ✅ Company configuration and multi-tenancy

**Key Test Classes:**
- `FinancialYearCloseTest` - FY closing rules
- `CompanyLockTest` - Company-wide freezes
- `CompanyConfigurationTest` - Setup validation

### 4. Voucher Tests (`apps/voucher/tests/`)

**File:** `test_voucher_posting.py`

Tests core voucher posting operations:
- ✅ Simple journal voucher posting
- ✅ Payment voucher posting
- ✅ Receipt voucher posting
- ✅ Already-posted voucher protection
- ✅ Inactive voucher type validation
- ✅ Multi-line vouchers with complex entries
- ✅ Auto-numbering and sequence generation
- ✅ Voucher status transitions

**Key Test Classes:**
- `VoucherPostingTest` - Core posting logic
- `VoucherNumberingTest` - Sequential numbering
- `VoucherCancellationTest` - Cancellation flow

### 5. System Tests (`apps/system/tests/`)

**File:** `test_idempotency.py`

Tests idempotency keys and audit logging:
- ✅ Idempotency key creation and uniqueness
- ✅ API replay protection - same key blocks repost
- ✅ Different keys don't interfere
- ✅ Optional idempotency (works without key too)
- ✅ Audit log creation and tracking
- ✅ Change tracking in audit logs
- ✅ Integration event emission

**Key Test Classes:**
- `IdempotencyKeyTest` - Replay protection
- `AuditLogTest` - Comprehensive audit trail
- `IntegrationEventTest` - Event-driven architecture

### 6. Party Tests (`apps/party/tests/`)

**File:** `test_party_ledger.py`

Tests party management and ledger integration:
- ✅ Party creation with ledger linkage
- ✅ GST and PAN registration
- ✅ Multiple addresses per party
- ✅ Party bank accounts
- ✅ Customer transaction flow (sales)
- ✅ Supplier transaction flow (purchases)
- ✅ Dual-type parties (both customer & supplier)
- ✅ Credit limit tracking
- ✅ Party filtering and search

**Key Test Classes:**
- `PartyLedgerIntegrationTest` - Party-ledger sync
- `PartySearchAndFilterTest` - Query operations

## Running Tests

### Run All Tests
```bash
python manage.py test
```

### Run Specific App Tests
```bash
# Inventory tests
python manage.py test apps.inventory.tests

# Accounting tests
python manage.py test apps.accounting.tests

# Company tests
python manage.py test apps.company.tests

# Voucher tests
python manage.py test apps.voucher.tests

# System tests
python manage.py test apps.system.tests

# Party tests
python manage.py test apps.party.tests
```

### Run Specific Test Class
```bash
python manage.py test apps.inventory.tests.test_fifo_stock_movement.FIFOStockMovementTest
```

### Run Specific Test Method
```bash
python manage.py test apps.accounting.tests.test_concurrent_posting.ConcurrentPostingTest.test_double_posting_protection
```

### Run with Coverage
```bash
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML report
```

### Run with Verbose Output
```bash
python manage.py test --verbosity=2
```

### Run with Parallel Execution
```bash
python manage.py test --parallel
```

## Test Database

Tests use a separate test database automatically created and destroyed by Django:
- Database name: `test_<your_database_name>`
- Automatically cleaned between test runs
- Uses `TransactionTestCase` for tests requiring database transaction control

## Key Testing Patterns

### 1. Test Fixtures
Each test class has a `setUp()` method creating common test data:
- Company with currency and financial year
- User accounts
- Account groups and ledgers
- Voucher types

### 2. Transaction Testing
Use `TransactionTestCase` for:
- Concurrent posting tests
- Sequence generation tests
- Any test requiring database transaction control

Use regular `TestCase` for:
- Standard CRUD operations
- Validation tests
- Read-only operations

### 3. Assertion Patterns
```python
# Status checks
self.assertEqual(voucher.status, "POSTED")

# Error handling
with self.assertRaises(UnbalancedVoucher):
    service.post_voucher(voucher.id, user)

# Decimal comparisons
self.assertEqual(balance.quantity, Decimal("10.00"))

# Existence checks
self.assertIsNotNone(voucher.posted_at)
```

## Enterprise-Grade Features Tested

✅ **FIFO Stock Valuation** - First-In-First-Out inventory costing
✅ **Transaction Safety** - Atomic operations with rollback
✅ **Concurrency Protection** - SELECT FOR UPDATE locking
✅ **Idempotent Posting** - API replay protection
✅ **Financial Year Lock** - Audit compliance
✅ **Company Lock** - Accounting freeze
✅ **Double-Entry Validation** - DR = CR enforcement
✅ **Audit Trail** - Comprehensive change tracking
✅ **Multi-Tenancy** - Company-scoped data isolation
✅ **Sequential Numbering** - Thread-safe voucher numbers

## Test Data Philosophy

Tests create minimal, focused data:
- One company per test (unless testing multi-company)
- One financial year
- Minimal ledgers (only what's needed)
- Clear, descriptive names (e.g., "Test Company", "Customer ABC")

## Continuous Integration

These tests are designed to run in CI/CD pipelines:
- Fast execution (< 5 minutes for full suite)
- No external dependencies
- Deterministic results
- Proper cleanup between tests

## Common Test Failures

### 1. IntegrityError
**Cause:** Duplicate unique constraints (e.g., company code)
**Fix:** Use unique values in test data

### 2. UnbalancedVoucher
**Cause:** Debit != Credit in voucher lines
**Fix:** Ensure DR and CR amounts match exactly

### 3. AlreadyPosted
**Cause:** Attempting to post same voucher twice
**Fix:** Check voucher status before posting

### 4. InsufficientStock
**Cause:** Consuming more stock than available
**Fix:** Verify stock balances before consumption

## Future Test Additions

- [ ] Invoice posting tests
- [ ] GST calculation tests
- [ ] Report generation tests
- [ ] User permission tests
- [ ] API endpoint tests
- [ ] Performance/load tests

## Contributing

When adding new tests:
1. Follow existing patterns and structure
2. Use descriptive test names (test_what_is_being_tested)
3. Include docstrings explaining test purpose
4. Clean up test data in setUp/tearDown
5. Test both success and failure paths
6. Use appropriate TestCase or TransactionTestCase

## Contact

For questions about tests, refer to:
- `DOCUMENTATION_INDEX.md` - Overall architecture
- `PHASE1_DATABASE_HARDENING.md` - Database design
- `PHASE2_POSTING_SERVICE.md` - Posting service details
- `core/services/posting.py` - Implementation reference
