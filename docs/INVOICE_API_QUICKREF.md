# INVOICE APIs — QUICK REFERENCE

## Overview

Complete RESTful APIs for managing invoices in the ERP system. Handles invoice generation from orders, posting to accounting, and payment tracking.

**Features:**
- Generate invoices from sales/purchase orders
- Post invoices (creates vouchers, updates stock, updates ledgers)
- Track outstanding/unpaid invoices
- Payment application tracking
- Multi-company scoping
- Role-based permissions
- Atomic posting with idempotency

**Base URL:** `/api/invoices/`

---

## 🔑 Authentication

All endpoints require JWT authentication:

```
Authorization: Bearer <jwt_token>
```

Company context is derived from the user's active company.

---

## 📋 Invoice Endpoints

### 1. Generate Invoice from Sales Order

**POST** `/api/invoices/from_sales_order/{so_id}/`

Generate an invoice from a confirmed sales order.

**Permissions:** Requires `ADMIN`, `ACCOUNTANT`, or `SALES_MANAGER` role.

**Request:**
```json
{
  "partial_allowed": false,  // optional, default: false
  "apply_gst": true,  // optional, default: true
  "company_state_code": "MH"  // optional, for GST calculation
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "invoice_number": "INV-2025-00001",
  "invoice_date": "2025-12-26",
  "due_date": "2026-01-26",
  "party": "party-uuid",
  "party_name": "Customer Name",
  "invoice_type": "SALES",
  "status": "DRAFT",
  "currency": "currency-uuid",
  "currency_code": "USD",
  "sales_order": "so-uuid",
  "sales_order_number": "SO-00001",
  "total_value": "1050.00",
  "amount_received": "0.00",
  "outstanding_amount": "1050.00",
  "lines": [
    {
      "id": "line-uuid",
      "line_no": 1,
      "item": "item-uuid",
      "item_name": "Product A",
      "item_sku": "SKU001",
      "quantity": "10.000",
      "unit_rate": "100.00",
      "discount_pct": "5.00",
      "line_total": "950.00",
      "tax_amount": "100.00"
    }
  ],
  "created_at": "2025-12-26T10:00:00Z"
}
```

**Business Logic:**
- Validates sales order is CONFIRMED or IN_PROGRESS
- Copies all order items to invoice lines
- Applies pricing from order
- Calculates GST if `apply_gst=true`
- Generates unique invoice number
- Sets status to DRAFT

**Error Responses:**

- `400 Bad Request`: Order not in valid status
- `404 Not Found`: Sales order not found
- `500 Internal Server Error`: Invoice generation failed

---

### 2. Post Invoice to Accounting

**POST** `/api/invoices/{invoice_id}/post_voucher/`

Post an invoice to the accounting system (creates voucher, updates stock, updates ledgers).

**Permissions:** Requires `ADMIN` or `ACCOUNTANT` role.

**Response:** `200 OK`
```json
{
  "voucher_id": "voucher-uuid",
  "voucher_number": "JV-2025-00001",
  "status": "POSTED",
  "message": "Invoice posted successfully"
}
```

**Business Logic:**
1. Creates accounting voucher from invoice
2. Posts voucher to general ledger
3. Creates stock OUT movements (for sales invoices)
4. Updates customer/supplier ledger balances
5. Updates invoice status to POSTED
6. Updates related order status to INVOICED
7. Triggers accounting signals

**What Happens During Posting:**

```
Invoice Posting Flow:
┌─────────────────────────────────────────────────────────┐
│ 1. Create Voucher                                       │
│    - Customer/Supplier account (Debit/Credit)          │
│    - Sales/Purchase account (Credit/Debit)             │
│    - Tax accounts (if applicable)                      │
├─────────────────────────────────────────────────────────┤
│ 2. Post Voucher                                         │
│    - Validate double-entry                             │
│    - Lock ledgers (SELECT FOR UPDATE)                  │
│    - Create ledger entries                             │
│    - Update ledger balances                            │
├─────────────────────────────────────────────────────────┤
│ 3. Stock Movements (Sales Invoice only)                │
│    - Create OUT movements for each item                │
│    - Reduce stock balance                              │
│    - FIFO batch allocation                             │
│    - Release stock reservations                        │
├─────────────────────────────────────────────────────────┤
│ 4. Update Order Status                                 │
│    - Mark order as INVOICED                            │
│    - Record invoiced_at timestamp                      │
├─────────────────────────────────────────────────────────┤
│ 5. Audit Trail                                          │
│    - Log posting event                                 │
│    - Record user and timestamp                         │
│    - Generate integration events                       │
└─────────────────────────────────────────────────────────┘
```

**Error Responses:**

- `400 Bad Request`: Invoice already posted or cancelled
- `404 Not Found`: Invoice not found
- `500 Internal Server Error`: Posting failed

**Idempotency:**
- If invoice already posted, returns existing voucher details
- Safe to retry on network failures
- Uses database-level locking to prevent duplicate posts

---

### 3. List Outstanding Invoices

**GET** `/api/invoices/outstanding/`

List all outstanding (unpaid or partially paid) invoices.

**Query Parameters:**
- `invoice_type` - Filter by type (SALES, PURCHASE)
- `party` - Filter by party ID (UUID)
- `start_date` - Filter from date (YYYY-MM-DD)
- `end_date` - Filter to date (YYYY-MM-DD)

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "invoice_number": "INV-2025-00001",
    "invoice_date": "2025-12-26",
    "due_date": "2026-01-26",
    "party_name": "Customer Name",
    "invoice_type": "SALES",
    "status": "PARTIALLY_PAID",
    "currency_code": "USD",
    "total_value": "1050.00",
    "amount_received": "500.00",
    "outstanding_amount": "550.00",
    "created_at": "2025-12-26T10:00:00Z"
  }
]
```

**Business Logic:**
- Excludes invoices with status = PAID
- Calculates `outstanding_amount = total_value - amount_received`
- Orders by invoice date (newest first)

---

### 4. List All Invoices

**GET** `/api/invoices/`

List all invoices for the company with filters.

**Query Parameters:**
- `status` - Filter by status (DRAFT, POSTED, PAID, etc.)
- `invoice_type` - Filter by type (SALES, PURCHASE)
- `party` - Filter by party ID (UUID)
- `start_date` - Filter from date (YYYY-MM-DD)
- `end_date` - Filter to date (YYYY-MM-DD)

**Response:** `200 OK` (same format as outstanding invoices)

---

### 5. Get Invoice Details

**GET** `/api/invoices/{invoice_id}/`

Get complete invoice details including line items.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "invoice_number": "INV-2025-00001",
  "invoice_date": "2025-12-26",
  "due_date": "2026-01-26",
  "party": "party-uuid",
  "party_name": "Customer Name",
  "invoice_type": "SALES",
  "status": "POSTED",
  "currency": "currency-uuid",
  "currency_code": "USD",
  "sales_order": "so-uuid",
  "sales_order_number": "SO-00001",
  "voucher": "voucher-uuid",
  "voucher_number": "JV-2025-00001",
  "total_value": "1050.00",
  "amount_received": "500.00",
  "outstanding_amount": "550.00",
  "shipping_address": "123 Main St",
  "billing_address": "123 Main St",
  "notes": "Special delivery instructions",
  "lines": [
    {
      "id": "line-uuid",
      "line_no": 1,
      "item": "item-uuid",
      "item_name": "Product A",
      "item_sku": "SKU001",
      "description": "High quality product",
      "quantity": "10.000",
      "unit_rate": "100.00",
      "uom": "uom-uuid",
      "uom_name": "Piece",
      "discount_pct": "5.00",
      "line_total": "950.00",
      "tax_amount": "100.00"
    }
  ],
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T11:00:00Z"
}
```

---

## 🔒 Permissions & Roles

| Endpoint | Roles Required |
|----------|----------------|
| Generate from order | `ADMIN`, `ACCOUNTANT`, `SALES_MANAGER` |
| **Post invoice** | `ADMIN`, `ACCOUNTANT` |
| List outstanding | Any authenticated user |
| List all invoices | Any authenticated user |
| Get invoice details | Any authenticated user |

---

## 📊 Invoice Status Flow

```
DRAFT → POSTED → PARTIALLY_PAID → PAID
  ↓
CANCELLED
```

### Status Definitions

- **DRAFT**: Invoice created but not posted
- **POSTING**: Invoice is being posted (temporary state)
- **POSTED**: Invoice posted to accounting, awaiting payment
- **PARTIALLY_PAID**: Some payment received
- **PAID**: Fully paid
- **OVERDUE**: Past due date with outstanding balance
- **CANCELLED**: Invoice cancelled

---

## 🔧 Business Rules

### Invoice Generation

1. **Order Prerequisites:**
   - Sales order must be CONFIRMED or IN_PROGRESS
   - Order must have at least one item
   - Cannot generate invoice from CANCELLED orders

2. **Invoice Number:**
   - Auto-generated from company sequence
   - Format: `INV-{year}-{sequence}`
   - Unique per company

3. **Pricing:**
   - Copies rates from order items
   - Applies discounts from order
   - Calculates taxes (GST if enabled)

### Invoice Posting

1. **Prerequisites:**
   - Invoice must be in DRAFT status
   - Cannot post CANCELLED invoices
   - Cannot re-post POSTED invoices (idempotent)

2. **Double-Entry Accounting:**
   - **Sales Invoice:**
     - Debit: Customer Account (Accounts Receivable)
     - Credit: Sales Revenue Account
     - Credit: Tax Payable Account (if taxes)
   
   - **Purchase Invoice:**
     - Debit: Purchase/Expense Account
     - Debit: Tax Receivable Account (if taxes)
     - Credit: Supplier Account (Accounts Payable)

3. **Stock Movements:**
   - **Sales Invoice:** Creates OUT movements (reduces stock)
   - **Purchase Invoice:** No stock movement (handled at goods receipt)

4. **Order Updates:**
   - Sales/Purchase order status updated to INVOICED
   - `invoiced_at` timestamp recorded

### Outstanding Calculation

```python
outstanding_amount = total_value - amount_received

# Status logic:
if amount_received >= total_value:
    status = "PAID"
elif amount_received > 0:
    status = "PARTIALLY_PAID"
else:
    status = "POSTED"  # or other non-paid status
```

---

## 🎯 Example Workflows

### Complete Sales Order to Payment Flow

```python
import requests

base_url = "http://localhost:8000/api"
headers = {"Authorization": f"Bearer {token}"}

# 1. Create and confirm sales order (from previous phase)
order_response = requests.post(
    f"{base_url}/orders/sales/",
    json={"customer_id": "customer-uuid", "currency_id": "currency-uuid"},
    headers=headers
)
order_id = order_response.json()["id"]

# Add items and confirm order...
requests.post(f"{base_url}/orders/sales/{order_id}/confirm/", headers=headers)

# 2. Generate invoice from order
invoice_response = requests.post(
    f"{base_url}/invoices/from_sales_order/{order_id}/",
    json={"apply_gst": True},
    headers=headers
)
invoice = invoice_response.json()
invoice_id = invoice["id"]
print(f"Invoice created: {invoice['invoice_number']}")

# 3. Post invoice to accounting
post_response = requests.post(
    f"{base_url}/invoices/{invoice_id}/post_voucher/",
    headers=headers
)
voucher_info = post_response.json()
print(f"Invoice posted, voucher: {voucher_info['voucher_number']}")

# 4. Check outstanding invoices
outstanding = requests.get(
    f"{base_url}/invoices/outstanding/",
    headers=headers
)
print(f"Outstanding invoices: {len(outstanding.json())}")

# 5. Later: Apply payment (Phase 8)
# payment_response = requests.post(
#     f"{base_url}/payments/",
#     json={
#         "invoice_id": invoice_id,
#         "amount": "1050.00",
#         "payment_date": "2025-12-27"
#     },
#     headers=headers
# )
```

### Check Invoice Details

```python
# Get full invoice with line items
invoice = requests.get(
    f"{base_url}/invoices/{invoice_id}/",
    headers=headers
).json()

print(f"Invoice: {invoice['invoice_number']}")
print(f"Status: {invoice['status']}")
print(f"Total: {invoice['total_value']}")
print(f"Received: {invoice['amount_received']}")
print(f"Outstanding: {invoice['outstanding_amount']}")
print(f"Items: {len(invoice['lines'])}")
```

### Filter Outstanding Invoices

```python
# Get overdue sales invoices
from datetime import date

outstanding = requests.get(
    f"{base_url}/invoices/outstanding/",
    params={
        "invoice_type": "SALES",
        "end_date": date.today().isoformat()
    },
    headers=headers
).json()

for inv in outstanding:
    print(f"{inv['invoice_number']}: {inv['outstanding_amount']} overdue")
```

---

## ⚠️ Error Handling

### Common Error Responses

**400 Bad Request** - Validation error
```json
{
  "error": "Cannot create invoice from CANCELLED order"
}
```

**403 Forbidden** - Insufficient permissions
```json
{
  "error": "Permission denied. Requires ACCOUNTANT role."
}
```

**404 Not Found** - Resource not found
```json
{
  "error": "Sales order not found"
}
```

**500 Internal Server Error** - Server error
```json
{
  "error": "Failed to post invoice: Database connection error"
}
```

### Validation Errors

- Order must be confirmed before invoicing
- Invoice must be DRAFT to post
- Cannot post cancelled invoices
- Duplicate posting prevented by idempotency

---

## 🔗 Integration Points

### With Order System

- **Invoice Generation:** Creates invoice from confirmed orders
- **Status Updates:** Order marked as INVOICED after posting
- **Item Details:** Copies items, quantities, rates from order

### With Accounting System

- **Voucher Creation:** Creates accounting voucher on posting
- **Ledger Updates:** Updates customer/supplier balances
- **Double-Entry:** Maintains accounting equation balance

### With Inventory System

- **Stock Movements:** Creates OUT movements on sales invoice posting
- **FIFO Allocation:** Uses oldest stock first
- **Balance Updates:** Reduces available stock

### With Payment System (Phase 8)

- **Payment Application:** Links payments to invoices
- **Outstanding Tracking:** Updates `amount_received` field
- **Status Updates:** Marks as PAID when fully paid

---

## 🧪 Testing Checklist

### Invoice Generation

- [ ] Generate invoice from confirmed sales order
- [ ] Verify invoice number auto-generated
- [ ] Check all order items copied to invoice
- [ ] Verify GST calculation (if enabled)
- [ ] Try generating from DRAFT order (should fail)
- [ ] Try generating from CANCELLED order (should fail)

### Invoice Posting

- [ ] Post invoice to accounting
- [ ] Verify voucher created
- [ ] Check ledger entries created
- [ ] Verify stock OUT movements created
- [ ] Check order status updated to INVOICED
- [ ] Try posting same invoice twice (should be idempotent)
- [ ] Try posting cancelled invoice (should fail)

### Outstanding Invoices

- [ ] List all outstanding invoices
- [ ] Filter by party
- [ ] Filter by date range
- [ ] Verify outstanding calculation correct
- [ ] Check PAID invoices excluded

### Signals

- [ ] Verify order status updated on invoice posting
- [ ] Check payment updates invoice outstanding (Phase 8)

---

## 📚 API Architecture

### Files Structure

```
apps/invoice/
├── api/
│   ├── __init__.py
│   ├── serializers.py          # DRF serializers
│   ├── views.py                # API views
│   └── urls.py                 # URL routing
├── services/
│   └── invoice_generation_service.py  # Business logic
├── models.py                   # Invoice & InvoiceLine models
├── selectors.py                # Query helpers
└── signals.py                  # Invoice status handlers
```

### Service Layer Methods

**InvoiceGenerationService:**
- `generate_from_sales_order()` - Create invoice from order
- `apply_gst()` - Calculate and apply GST
- `mark_invoiced()` - Update order status

**PostingService:**
- `create_voucher_from_invoice()` - Generate voucher
- `post_voucher()` - Post to accounting
- `create_stock_movements()` - Handle inventory

---

## 🎉 Prerequisites Verification

All prerequisites for Invoice APIs are implemented:

| Component | Status | Location |
|-----------|--------|----------|
| ✅ InvoiceGenerationService | Implemented | [apps/invoice/services/invoice_generation_service.py](apps/invoice/services/invoice_generation_service.py) |
| ✅ Posting Engine | Implemented | [core/services/posting.py](core/services/posting.py) |
| ✅ GST Engine | Implemented | Part of posting service |
| ✅ Order Status Transitions | Implemented | Order services |
| ✅ Stock OUT on Posting | Implemented | Posting service handles stock movements |

---

## 🔄 Signals Implementation

### Invoice Status Signal

Located in [apps/invoice/signals.py](apps/invoice/signals.py)

```python
@receiver(post_save, sender=Invoice)
def update_order_invoice_status(sender, instance, created, **kwargs):
    """
    Update sales/purchase order when invoice is posted.
    
    Triggered when invoice status changes to POSTED:
    - Updates order status to INVOICED
    - Records invoiced_at timestamp
    """
```

### Payment Signal (Future - Phase 8)

Located in `apps/payment/signals.py` (to be implemented)

```python
@receiver(post_save, sender=PaymentLine)
def update_invoice_outstanding(sender, instance, created, **kwargs):
    """
    Update invoice outstanding when payment is applied.
    
    Calls invoice.refresh_outstanding() to recalculate:
    - amount_received (sum of payments)
    - status (PAID if fully paid, PARTIALLY_PAID if partial)
    """
```

---

## 📈 Outstanding Calculation Method

Added to `Invoice` model in [apps/invoice/models.py](apps/invoice/models.py):

```python
def refresh_outstanding(self):
    """
    Recalculate and update outstanding amount based on payments.
    
    Aggregates PaymentLine records and updates:
    - amount_received
    - status (PAID / PARTIALLY_PAID)
    """
```

This method will be called automatically when payments are applied (Phase 8).

---

## 🎊 Implementation Complete!

All Invoice API endpoints are now live and ready for:

1. **Generating invoices** from confirmed orders
2. **Posting invoices** to accounting (creates vouchers, updates stock)
3. **Tracking outstanding** invoices
4. **Integration** with orders, accounting, and inventory systems

### Next Steps

1. **Test invoice generation** from sales orders
2. **Test posting** and verify voucher creation
3. **Verify stock movements** after posting
4. **Check ledger balances** updated correctly
5. **Implement payment system** (Phase 8) to track payments

---

**Documentation Version:** 1.0  
**Last Updated:** December 26, 2025  
**API Version:** Phase 7
