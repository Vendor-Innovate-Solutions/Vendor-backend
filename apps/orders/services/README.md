# Sales Order Service

## Overview

The Sales Order Service provides a complete, production-ready order management system aligned with ERP best practices.

## Features

✅ **Multi-Company Isolation** - All operations respect company boundaries  
✅ **Retailer Approval** - Validates retailer has approved access to company  
✅ **Credit Limit Enforcement** - Prevents orders exceeding customer credit limits  
✅ **Stock Validation** - Checks against StockBalance cache for availability  
✅ **Price List Resolution** - Automatic price lookup from configured price lists  
✅ **Idempotent Sequencing** - Safe, concurrent sequence number generation  
✅ **Transaction Safety** - All operations wrapped in atomic transactions  
✅ **Audit Trail** - Tracks creation, confirmation, posting, and cancellation

## Architecture

### Service Layer
- `SalesOrderService` - Main service class with static methods
- Helper functions for validation and business logic
- Clean separation of concerns

### Key Validations
1. **Company Access** - `_check_company_access()` - Ensures retailer approved
2. **Credit Limit** - `_check_credit_limit()` - Validates against ledger balance
3. **Stock Availability** - `_check_stock_availability()` - Checks StockBalance cache
4. **Price Resolution** - `_get_item_price()` - Finds active price from price list

### State Machine

```
DRAFT → CONFIRMED → POSTED
   ↓
CANCELLED
```

- **DRAFT**: Initial state, can be modified
- **CONFIRMED**: Validated and locked, ready for fulfillment
- **POSTED**: Invoiced and posted to accounting
- **CANCELLED**: Order cancelled (cannot cancel after POSTED)

## Usage

### Create Order

```python
from apps.orders.services import SalesOrderService

order = SalesOrderService.create_order(
    company=company,
    customer_party_id=customer.id,
    currency_id=currency.id,
    price_list_id=price_list.id,
    created_by=request.user
)
```

### Add Items

```python
item_line = SalesOrderService.add_item(
    order=order,
    item_id=product.id,
    quantity=Decimal("10.00"),
    override_rate=None  # Optional manual price
)
```

### Update Item

```python
SalesOrderService.update_item(
    order=order,
    item_line_id=item_line.id,
    quantity=Decimal("15.00")  # Update quantity
)
```

### Confirm Order

```python
# Validates stock and credit
confirmed_order = SalesOrderService.confirm_order(
    order=order,
    validate_stock=True,
    enforce_credit=True
)
```

### Cancel Order

```python
SalesOrderService.cancel_order(
    order=order,
    reason="Customer requested cancellation"
)
```

### Mark as Posted

```python
# Called by invoice posting service
SalesOrderService.mark_posted(order=order)
```

## Integration Points

### With Inventory
- Reads from `StockBalance` cache for availability
- Does NOT create reservations (uses cached balance only)
- Stock movements created during invoice posting

### With Accounting
- Checks `LedgerBalance` for credit limit validation
- Links to customer's accounting ledger via Party
- Order posting creates accounting entries via invoice

### With Portal
- Validates `RetailerCompanyAccess` for retailer users
- Allows internal users (employees) without approval
- Respects company access permissions

### With Pricing
- Resolves prices from `PriceList` and `ItemPrice`
- Supports time-bound pricing (valid_from/valid_to)
- Falls back to most recent valid price

## Error Handling

### ValidationError
Raised for business logic violations:
- Order not in correct status
- Customer not approved
- Credit limit exceeded
- Insufficient stock
- No price found

### AlreadyPosted
Raised when attempting to modify/cancel posted order

### DoesNotExist
Raised when referenced entities not found:
- Customer party not found
- Item not found
- Order item not found

## Database Design

### New Fields in SalesOrder
- `price_list` - ForeignKey to PriceList
- `confirmed_at` - DateTime when confirmed
- `posted_at` - DateTime when posted
- `cancelled_at` - DateTime when cancelled
- `cancellation_reason` - Text field
- `created_by` - ForeignKey to User
- `status` - Added 'POSTED' to OrderStatus choices

## Testing

Run tests:
```bash
python manage.py test apps.orders.tests.test_sales_order_service
```

Test coverage:
- Order creation
- Item addition/update/removal
- Confirmation with validations
- Cancellation
- Status transitions

## Concurrency & Safety

- Uses `select_for_update()` for sequence generation
- All operations in atomic transactions
- No race conditions in sequence numbering
- Proper locking for multi-user scenarios

## Performance Considerations

- Uses StockBalance cache (fast) instead of aggregating movements
- Price lookups optimized with proper indexing
- Minimal database queries per operation
- Efficient validation checks

## Migration

Migration file: `apps/orders/migrations/0002_salesorder_fields.py`

Adds:
- price_list field
- Lifecycle tracking fields (confirmed_at, posted_at, cancelled_at)
- cancellation_reason field
- created_by field
- POSTED status choice

Apply with:
```bash
python manage.py migrate orders
```

## Future Enhancements

Potential additions:
- Partial fulfillment tracking
- Order approval workflow
- Discount rules engine
- Tax calculation integration
- Multi-currency support with exchange rates
- Delivery scheduling
- Order amendments and revisions
