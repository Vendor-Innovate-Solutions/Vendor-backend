# Test Documentation

Comprehensive test suite for the ERP system covering all critical business logic.

## Test Coverage Overview

### 1. Posting & Reversal Engine
**File:** `test_posting_reversal.py`  
**Tests:** 16  
**Lines:** 620

#### Coverage Areas
- ✅ Voucher posting with double-entry validation
- ✅ Unbalanced voucher rejection (DR ≠ CR)
- ✅ Duplicate posting prevention
- ✅ Voucher number generation (sequence)
- ✅ Audit log creation
- ✅ Integration event emission
- ✅ Voucher reversal functionality
- ✅ Reversal audit trail
- ✅ Idempotency key handling
- ✅ Concurrent posting (thread-safe)
- ✅ Financial year validation
- ✅ Decimal precision (2 decimal places)

#### Key Test Classes
- `PostingServiceTestCase` - Base setup
- `TestVoucherPosting` - 7 tests
- `TestVoucherReversal` - 4 tests
- `TestIdempotencyHandling` - 1 test
- `TestConcurrentPosting` - 1 test
- `TestFinancialYearValidation` - 2 tests
- `TestDecimalPrecision` - 1 test

#### Run Tests
```bash
python -m pytest tests/test_posting_reversal.py -v
```

---

### 2. Stock Reservation & Balance Updates
**File:** `test_stock_reservation.py`  
**Tests:** 13  
**Lines:** 580

#### Coverage Areas
- ✅ FIFO allocation (First In First Out)
- ✅ Multi-batch allocation
- ✅ Insufficient stock error handling
- ✅ Expired batch exclusion
- ✅ Stock IN/OUT balance updates
- ✅ Available quantity calculation
- ✅ Godown-wise stock isolation
- ✅ Stock movement tracking
- ✅ Concurrent allocation (thread-safe)
- ✅ Stock reservation locking

#### Key Test Classes
- `StockTestCase` - Base setup
- `TestFIFOAllocation` - 4 tests
- `TestStockBalanceUpdates` - 3 tests
- `TestGodownWiseStock` - 2 tests
- `TestStockMovements` - 2 tests
- `TestConcurrentStockAllocation` - 1 test
- `TestStockReservation` - 1 test

#### Run Tests
```bash
python -m pytest tests/test_stock_reservation.py -v
```

---

### 3. Invoice Generation & Outstanding
**File:** `test_invoice_outstanding.py`  
**Tests:** 23  
**Lines:** 560

#### Coverage Areas
- ✅ Invoice creation with line items
- ✅ Invoice number generation
- ✅ Outstanding calculation (invoice-based)
- ✅ Payment tracking (amount_received)
- ✅ Invoice status transitions (DRAFT → POSTED → PARTIALLY_PAID → PAID)
- ✅ Credit status calculation (OK/WARNING/EXCEEDED/NO_LIMIT)
- ✅ Overdue amount calculation
- ✅ Invoice aging buckets (0-30, 31-60, 61-90, 90+)
- ✅ Draft invoice exclusion from outstanding
- ✅ Fully paid invoice exclusion

#### Key Test Classes
- `InvoiceTestCase` - Base setup
- `TestInvoiceGeneration` - 3 tests
- `TestOutstandingCalculation` - 5 tests
- `TestPaymentTracking` - 3 tests
- `TestCreditStatus` - 4 tests
- `TestOverdueCalculation` - 3 tests
- `TestInvoiceStatusTransitions` - 3 tests
- `TestInvoiceAging` - 2 tests

#### Run Tests
```bash
python -m pytest tests/test_invoice_outstanding.py -v
```

---

### 4. Payment Allocation
**File:** `test_payment_allocation.py`  
**Tests:** 13  
**Lines:** 650

#### Coverage Areas
- ✅ Single invoice full payment
- ✅ Single invoice partial payment
- ✅ Multiple partial payments
- ✅ Payment split across multiple invoices
- ✅ FIFO payment allocation (oldest first)
- ✅ Overpayment handling (advance)
- ✅ Advance payment application
- ✅ Payment reversal
- ✅ Automatic knock-off matching
- ✅ Manual knock-off selection
- ✅ Cash payment
- ✅ Bank payment
- ✅ Payment aging

#### Key Test Classes
- `PaymentTestCase` - Base setup
- `TestSingleInvoicePayment` - 3 tests
- `TestMultipleInvoicePayment` - 2 tests
- `TestOverpaymentHandling` - 2 tests
- `TestPaymentReversal` - 2 tests
- `TestKnockOffLogic` - 2 tests
- `TestPaymentMethods` - 2 tests

#### Run Tests
```bash
python -m pytest tests/test_payment_allocation.py -v
```

---

### 5. Credit Limit Guards
**File:** `test_credit_guards.py`  
**Tests:** 18  
**Lines:** 650

#### Coverage Areas
- ✅ Order within credit limit
- ✅ Order exceeding credit limit (blocked)
- ✅ Order at exact credit limit
- ✅ No credit limit allows any order
- ✅ Zero outstanding calculation
- ✅ Multiple invoices outstanding
- ✅ Draft invoice exclusion
- ✅ Credit status: OK (<80%)
- ✅ Credit status: WARNING (≥80%)
- ✅ Credit status: EXCEEDED (>100%)
- ✅ Credit status: NO_LIMIT
- ✅ Credit limit validation function
- ✅ Overdue amount calculation
- ✅ Invoice-based vs ledger-based outstanding

#### Key Test Classes
- `CreditGuardTestCase` - Base setup
- `TestCreditLimitEnforcement` - 4 tests
- `TestOutstandingCalculation` - 4 tests
- `TestCreditStatusCalculation` - 4 tests
- `TestCreditLimitValidation` - 2 tests
- `TestOverdueCalculation` - 4 tests

#### Run Tests
```bash
python -m pytest tests/test_credit_guards.py -v
```

---

### 6. Financial Year Lock
**File:** `test_financial_year_lock.py`  
**Tests:** 14  
**Lines:** 700

#### Coverage Areas
- ✅ Financial year close functionality
- ✅ FY close audit trail
- ✅ Financial year reopen
- ✅ Reopen requires admin privileges
- ✅ Posting prevention in closed FY
- ✅ Posting allowed in open FY
- ✅ Reversal prevention in closed FY
- ✅ Lock guard passes for open FY
- ✅ Lock guard fails for closed FY
- ✅ Override mechanism
- ✅ Multiple financial years handling
- ✅ FY boundary date handling
- ✅ Voucher outside all FYs rejection
- ✅ Company-level lock feature

#### Key Test Classes
- `FinancialYearLockTestCase` - Base setup
- `TestFinancialYearClose` - 2 tests
- `TestFinancialYearReopen` - 2 tests
- `TestPostingPreventionInClosedFY` - 2 tests
- `TestReversalPreventionInClosedFY` - 1 test
- `TestLockGuardEnforcement` - 3 tests
- `TestMultipleFinancialYears` - 2 tests
- `TestFYBoundaryDates` - 3 tests
- `TestCompanyLockFeature` - 1 test

#### Run Tests
```bash
python -m pytest tests/test_financial_year_lock.py -v
```

---

## Total Test Coverage

| Area | Tests | Lines | Status |
|------|-------|-------|--------|
| Posting & Reversal | 16 | 620 | ✅ Complete |
| Stock Reservation | 13 | 580 | ✅ Complete |
| Invoice Outstanding | 23 | 560 | ✅ Complete |
| Payment Allocation | 13 | 650 | ✅ Complete |
| Credit Guards | 18 | 650 | ✅ Complete |
| Financial Year Lock | 14 | 700 | ✅ Complete |
| **TOTAL** | **97** | **~3,760** | **✅ Complete** |

---

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/test_posting_reversal.py -v
```

### Run Specific Test Class
```bash
python -m pytest tests/test_posting_reversal.py::TestVoucherPosting -v
```

### Run Specific Test Method
```bash
python -m pytest tests/test_posting_reversal.py::TestVoucherPosting::test_simple_voucher_posting -v
```

### Run with Coverage Report
```bash
python -m pytest tests/ --cov=core --cov=apps --cov-report=html
```

### Run with Detailed Output
```bash
python -m pytest tests/ -v --tb=short
```

### Run Parallel (Fast)
```bash
python -m pytest tests/ -n auto
```

---

## Test Architecture

### Base Test Cases
Each test file has a base test case class that provides:
- Company setup
- Financial year setup
- User creation
- Common test data (ledgers, parties, products, etc.)

### Test Naming Convention
```python
def test_<scenario>_<expected_outcome>(self):
    """Test description"""
```

Examples:
- `test_simple_voucher_posting()` - Happy path
- `test_unbalanced_voucher_rejection()` - Error handling
- `test_concurrent_voucher_posting()` - Edge case

### Assertion Patterns
- `assertEqual(actual, expected)` - Exact match
- `assertGreater/assertLess` - Comparisons
- `assertIsNotNone` - Existence checks
- `assertRaises(Exception)` - Error testing
- `assertTrue/assertFalse` - Boolean conditions

### Database Isolation
- Each test uses `setUp()` to create fresh data
- `refresh_from_db()` used to verify database changes
- TransactionTestCase for concurrent tests

---

## Critical Test Scenarios

### 1. Double-Entry Accounting
```python
# Every posting must have DR = CR
debit_total = sum(line.debit_amount for line in lines)
credit_total = sum(line.credit_amount for line in lines)
assert debit_total == credit_total
```

### 2. FIFO Allocation
```python
# Stock allocated from oldest batch first
batch1 = create_batch(mfg_date=30_days_ago)
batch2 = create_batch(mfg_date=15_days_ago)
allocated = allocate_stock(quantity=50)
assert allocated[0].batch == batch1  # Oldest first
```

### 3. Invoice-Based Outstanding
```python
# Outstanding = grand_total - amount_received (NOT ledger balance)
invoice = Invoice(grand_total=100000, amount_received=30000)
outstanding = get_outstanding_for_party(party)
assert outstanding == 70000  # Invoice-based
```

### 4. Credit Limit Guards
```python
# Block orders when limit exceeded
existing_outstanding = 80000
credit_limit = 100000
new_order_amount = 30000
result = can_create_order(party, new_order_amount)
assert not result['allowed']  # 80k + 30k > 100k
```

### 5. Financial Year Lock
```python
# Prevent posting in closed FY
fy.is_closed = True
voucher = Voucher(voucher_date=closed_fy_date)
with pytest.raises(FinancialYearClosed):
    posting_service.post_voucher(voucher)
```

---

## Test Data Patterns

### Decimal Precision
```python
# Always use Decimal for money
amount = Decimal('1000.00')  # Not 1000 or 1000.0
```

### Date Handling
```python
from datetime import date, timedelta
invoice_date = date.today()
due_date = invoice_date + timedelta(days=30)
```

### Status Transitions
```python
# Invoice: DRAFT → POSTED → PARTIALLY_PAID → PAID
invoice.status = 'DRAFT'
invoice.post()  # → POSTED
invoice.apply_payment(5000)  # → PARTIALLY_PAID
invoice.apply_payment(remaining)  # → PAID
```

---

## Coverage Gaps & Future Tests

### Areas to Expand
1. **Batch Expiry Edge Cases**: Expiry on exact date
2. **Concurrent Payment Allocation**: Race conditions
3. **GST Calculations**: Tax validation
4. **Approval Workflow**: Multi-level approvals
5. **Event Bus**: Event delivery guarantees
6. **Aging Reports**: Complex date ranges

### Performance Tests
- Load testing with 10,000+ vouchers
- Concurrent posting stress test
- Large outstanding calculation (1000+ invoices)

### Integration Tests
- End-to-end order → invoice → payment flow
- GST return generation
- Month-end closing process

---

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Run Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: pytest tests/ --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Debugging Failed Tests

### View Full Traceback
```bash
python -m pytest tests/test_posting_reversal.py::test_simple_voucher_posting -v --tb=long
```

### Print Debug Info
```python
def test_debug_example(self):
    voucher = create_voucher()
    print(f"Voucher ID: {voucher.id}")  # Will show in -v output
    print(f"Status: {voucher.status}")
    assert voucher.status == 'POSTED'
```

### Interactive Debugging
```bash
python -m pytest tests/ --pdb  # Drop into debugger on failure
```

---

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clarity**: Test names should be descriptive
3. **Coverage**: Test happy path + edge cases + errors
4. **Speed**: Keep tests fast (<1 second each)
5. **Data**: Use realistic test data
6. **Assertions**: One logical assertion per test
7. **Cleanup**: Use setUp/tearDown properly
8. **Documentation**: Add docstrings to complex tests

---

## Contact & Support

For test-related questions or issues:
- Review this documentation
- Check test file docstrings
- Run tests with `-v --tb=short` for context
- Refer to [ARCHITECTURE.md](ARCHITECTURE.md) for system design

---

*Last Updated: 2024*  
*Test Framework: pytest + Django TestCase*  
*Total Coverage: 97 tests, ~3,760 lines*
