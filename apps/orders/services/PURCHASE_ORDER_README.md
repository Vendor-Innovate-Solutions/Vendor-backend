# Purchase Order Service

## Overview

The Purchase Order Service provides ERP-aligned procurement order management with GRN (Goods Receipt Note) workflow support.

## Features

✅ **Multi-Company Isolation** - All operations respect company boundaries  
✅ **GRN Workflow** - Supports PARTIAL_RECEIVED status for partial receipts  
✅ **No Stock Reservation** - Procurement doesn't check existing stock  
✅ **Optional Vendor Approval** - Configurable vendor access validation  
✅ **Price List Resolution** - Automatic cost price lookup  
✅ **Idempotent Sequencing** - Safe PO number generation  
✅ **Transaction Safety** - All operations atomic  
✅ **Audit Trail** - Tracks creation, confirmation, posting, cancellation

## Key Differences from Sales Orders

| Feature | Sales Order | Purchase Order |
|---------|-------------|----------------|
| Stock Check | ✅ Validates availability | ❌ No check (inbound) |
| Credit Check | ✅ Enforces limit | ❌ Not applicable |
| Party Type | Customer | Supplier |
| Approval | Retailer approval required | Vendor approval optional |
| Partial Status | None | PARTIAL_RECEIVED for GRN |
| Price Type | Selling price | Cost/purchase price |

## Architecture

### Service Layer
- `PurchaseOrderService` - Main service class
- Helper functions for validation and pricing
- Clean separation from data layer

### Key Functions
1. **Sequence Generation** - `_next_po_number()` - Thread-safe PO numbering
2. **Cost Price Resolution** - `_get_cost_price()` - Finds vendor pricing
3. **Vendor Access** - `_check_vendor_access()` - Optional approval check (disabled by default)

### State Machine

```
DRAFT → CONFIRMED → PARTIAL_RECEIVED → POSTED
   ↓                       ↓
CANCELLED              CANCELLED
```

- **DRAFT**: Initial state, can be modified
- **CONFIRMED**: Approved, ready for GRN
- **PARTIAL_RECEIVED**: Some items received (GRN created partial StockMovement)
- **POSTED**: Fully received and posted to accounting
- **CANCELLED**: Order cancelled (cannot cancel after POSTED)

## Usage

### Create Purchase Order

```python
from apps.orders.services import PurchaseOrderService

po = PurchaseOrderService.create_order(
    company=company,
    supplier_party_id=supplier.id,
    currency_id=currency.id,
    price_list_id=vendor_price_list.id,
    created_by=request.user,
    expected_date=delivery_date
)
```

### Add Items

```python
item_line = PurchaseOrderService.add_item(
    order=po,
    item_id=product.id,
    quantity=Decimal("50.00"),
    override_rate=Decimal("75.00")  # Optional negotiated price
)
```

### Update Item

```python
PurchaseOrderService.update_item(
    order=po,
    item_line_id=item_line.id,
    quantity=Decimal("100.00")
)
```

### Confirm Order

```python
# Ready to send to vendor and receive goods
confirmed_po = PurchaseOrderService.confirm_order(order=po)
```

### Mark Partial Receipt (GRN Flow)

```python
# Called by GRN service after partial receipt
PurchaseOrderService.mark_partial_received(order=po)
```

### Mark as Posted

```python
# After full receipt or invoice posting
PurchaseOrderService.mark_posted(order=po)
```

### Cancel Order

```python
PurchaseOrderService.cancel_order(
    order=po,
    reason="Vendor cannot fulfill order"
)
```

## ERP-Correct Flow

```
1. Create PurchaseOrder (DRAFT)
2. Add line items
3. Confirm order → CONFIRMED
4. Vendor ships goods
5. GRN Service:
   - Validates received quantity
   - Creates StockMovement(IN) with from_godown=None, to_godown=warehouse
   - Updates StockBalance (+quantity)
   - Updates supplier ledger
   - Calls mark_partial_received() or mark_posted()
6. Purchase Invoice posting (if separate from GRN)
```

## Integration Points

### With Inventory
- Uses `StockItem` for product catalog
- No stock reservation (inbound procurement)
- GRN creates StockMovement(IN) separately
- StockBalance updated by PostingService

### With Accounting
- Links to supplier's accounting ledger via Party
- Purchase posting creates liability entries
- GRN and invoice can be separate or combined

### With Portal (Optional)
- Can validate `RetailerCompanyAccess` for vendor approval
- Disabled by default (see `_check_vendor_access()`)
- Enable for marketplace/multi-vendor scenarios

### With Pricing
- Resolves cost prices from `PriceList` and `ItemPrice`
- Supports vendor-specific pricing
- Time-bound pricing with valid_from/valid_to

## Vendor Approval (Optional)

By default, vendor approval is **disabled**. To enable:

```python
# In purchase_order_service.py, uncomment in _check_vendor_access():

access_exists = RetailerCompanyAccess.objects.filter(
    retailer__party=vendor_party,
    company=company,
    status='APPROVED'
).exists()

if not access_exists:
    raise ValidationError(
        f"Vendor '{vendor_party.name}' is not approved for procurement"
    )
```

This is useful for:
- Marketplace platforms
- Multi-vendor procurement portals
- Vendor onboarding workflows
- Compliance/audit requirements

## Error Handling

### ValidationError
Raised for:
- Order not in correct status
- Supplier party is not type SUPPLIER/BOTH
- Vendor not approved (if enabled)
- No price found
- Empty order (no items)

### AlreadyPosted
Raised when:
- Attempting to cancel posted order

### DoesNotExist
Raised when:
- Supplier party not found
- Item not found
- Order item not found

## Database Design

### New Fields in PurchaseOrder
- `price_list` - ForeignKey to PriceList (vendor pricing)
- `confirmed_at` - DateTime when confirmed
- `posted_at` - DateTime when posted
- `cancelled_at` - DateTime when cancelled
- `cancellation_reason` - Text field
- `created_by` - ForeignKey to User

### New Status
- `PARTIAL_RECEIVED` - Added to OrderStatus choices

## Testing

Run tests:
```bash
python manage.py test apps.orders.tests.test_purchase_order_service
```

Test coverage:
- Order creation
- Item addition/update/removal
- Confirmation
- Partial receipt marking
- Posting
- Cancellation
- Status transitions

## GRN (Goods Receipt Note) Integration

The PurchaseOrderService **does not** create stock movements. That's handled by a separate GRN service:

```python
# Example GRN Service (to be implemented)
class GRNService:
    @staticmethod
    @transaction.atomic
    def create_grn(purchase_order, received_items):
        # Validate PO is CONFIRMED
        # Create StockMovement(IN) records
        # Update StockBalance via PostingService
        # Update supplier ledger
        # Call PurchaseOrderService.mark_partial_received() or mark_posted()
        pass
```

## Concurrency & Safety

- Uses `select_for_update()` for sequence generation
- All operations in atomic transactions
- No race conditions in PO numbering
- Safe for multi-user environments

## Performance

- Fast price lookups with indexed queries
- No stock aggregation (not needed for procurement)
- Minimal queries per operation
- Efficient validation checks

## Migration

Migration file: `apps/orders/migrations/0003_purchaseorder_fields.py`

Adds:
- price_list field
- Lifecycle tracking fields
- PARTIAL_RECEIVED status choice

Apply with:
```bash
python manage.py migrate orders
```

## Comparison with Industry ERPs

| Feature | This Implementation | Tally | SAP | ERPNext |
|---------|---------------------|-------|-----|---------|
| Multi-company | ✅ | ❌ | ✅ | ✅ |
| GRN workflow | ✅ | ✅ | ✅ | ✅ |
| Partial receipts | ✅ | ✅ | ✅ | ✅ |
| Vendor approval | ✅ Optional | ❌ | ✅ | ✅ |
| Price lists | ✅ | ✅ | ✅ | ✅ |
| Stock reservation | ❌ (correct) | ❌ | ❌ | ❌ |

## Future Enhancements

Potential additions:
- Purchase requisition workflow
- Multi-level approval chains
- Automated reorder points
- Vendor performance tracking
- Quality inspection integration
- Landed cost calculation
- Import duty/tax tracking
- Purchase analytics
