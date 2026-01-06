# Test Suite Index

This test suite contains comprehensive enterprise-grade tests for the Vendor ERP Backend.

## Quick Start

```bash
# Run all tests
python run_tests.py

# Run specific app tests
python run_tests.py inventory

# Run with coverage
python run_tests.py --coverage

# Run in parallel
python run_tests.py --parallel
```

## Test Coverage

### ✅ Inventory Module
- FIFO stock valuation
- Batch allocation
- Stock movements
- Insufficient stock handling

### ✅ Accounting Module
- Concurrent posting protection
- Double-entry validation
- Thread safety
- Ledger balance updates

### ✅ Company Module
- Financial year closing
- Company lock enforcement
- Multi-tenancy
- Configuration validation

### ✅ Voucher Module
- Voucher posting
- Auto-numbering
- Status transitions
- Multi-line entries

### ✅ System Module
- Idempotency keys
- Audit logging
- Integration events
- Change tracking

### ✅ Party Module
- Party-ledger integration
- Customer/supplier management
- Address and bank accounts
- Transaction flows

## Documentation

See `tests/README.md` for detailed documentation.

## Test Statistics

- **Total Test Files:** 6
- **Test Classes:** 18+
- **Test Methods:** 60+
- **Code Coverage Target:** 85%

## Enterprise Features Tested

✅ FIFO Stock Valuation
✅ Thread-Safe Posting
✅ Double-Entry Validation
✅ Financial Year Lock
✅ Idempotency Protection
✅ Audit Trail
✅ Multi-Tenancy
✅ Transaction Safety
