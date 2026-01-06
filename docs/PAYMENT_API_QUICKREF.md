# Payment API Quick Reference

Complete guide for Payment and Receipt management APIs in the Vendor ERP Backend.

## Table of Contents
1. [Overview](#overview)
2. [Endpoints](#endpoints)
3. [Models](#models)
4. [Payment Lifecycle](#payment-lifecycle)
5. [Usage Examples](#usage-examples)
6. [Integration](#integration)

---

## Overview

Payment APIs handle both **Payments** (outgoing) and **Receipts** (incoming) for your company. The system:

- Creates draft payments/receipts linked to vouchers
- Allocates payments to outstanding invoices
- Posts payments to accounting ledgers
- Auto-updates invoice outstanding amounts
- Maintains full audit trail

**Key Features:**
- Company-scoped operations
- Role-based access (ADMIN, ACCOUNTANT)
- Draft → Posted workflow
- Idempotent posting
- Automatic voucher generation
- Real-time outstanding updates

**Payment Types:**
- `PAYMENT`: Outgoing payments to suppliers
- `RECEIPT`: Incoming receipts from customers

**Payment Modes:**
- CASH, CHEQUE, BANK_TRANSFER, UPI, CARD, OTHER

**Status Flow:**
```
DRAFT → POSTED
  ↓
CANCELLED (terminal)
```

---

## Endpoints

### 1. Create Payment (POST)
**URL:** `POST /api/payments/create/`  
**Role:** ADMIN, ACCOUNTANT  
**Creates:** Draft payment/receipt with associated voucher

**Request Body:**
```json
{
  "party_id": "uuid",
  "bank_account_id": "uuid",
  "payment_type": "PAYMENT",
  "payment_date": "2024-01-15",
  "payment_mode": "BANK_TRANSFER",
  "reference_number": "TXN123456",
  "notes": "Payment for Invoice INV-2024-001"
}
```

**Response:** `201 Created`
```json
{
  "id": "payment-uuid",
  "voucher": {
    "id": "voucher-uuid",
    "voucher_number": "PAY-2024-0001",
    "voucher_type": {
      "code": "PAYMENT",
      "name": "Payment Voucher"
    }
  },
  "party": {
    "id": "party-uuid",
    "name": "Acme Supplier Ltd"
  },
  "bank_account": {
    "id": "bank-uuid",
    "account_name": "Company Current Account",
    "account_number": "1234567890"
  },
  "payment_date": "2024-01-15",
  "payment_mode": "BANK_TRANSFER",
  "reference_number": "TXN123456",
  "status": "DRAFT",
  "notes": "Payment for Invoice INV-2024-001",
  "lines": [],
  "total_allocated": 0,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### 2. List Payments (GET)
**URL:** `GET /api/payments/`  
**Role:** Any authenticated user  
**Returns:** All payments for current company

**Query Parameters:**
- `status`: Filter by status (DRAFT, POSTED, CANCELLED)
- `payment_type`: Filter by type (PAYMENT, RECEIPT)
- `party`: Filter by party ID
- `start_date`: Filter from date (YYYY-MM-DD)
- `end_date`: Filter to date (YYYY-MM-DD)

**Example:**
```
GET /api/payments/?status=DRAFT&payment_type=PAYMENT
```

**Response:** `200 OK`
```json
[
  {
    "id": "payment-uuid",
    "voucher_number": "PAY-2024-0001",
    "party_name": "Acme Supplier Ltd",
    "payment_date": "2024-01-15",
    "payment_mode": "BANK_TRANSFER",
    "status": "DRAFT",
    "total_allocated": 50000.00,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### 3. Get Payment Details (GET)
**URL:** `GET /api/payments/{payment_id}/`  
**Role:** Any authenticated user  
**Returns:** Full payment details with allocations

**Response:** `200 OK`
```json
{
  "id": "payment-uuid",
  "voucher": {
    "id": "voucher-uuid",
    "voucher_number": "PAY-2024-0001"
  },
  "party": {
    "id": "party-uuid",
    "name": "Acme Supplier Ltd"
  },
  "bank_account": {
    "id": "bank-uuid",
    "account_name": "Company Current Account"
  },
  "payment_date": "2024-01-15",
  "payment_mode": "BANK_TRANSFER",
  "status": "DRAFT",
  "lines": [
    {
      "id": "line-uuid",
      "invoice": {
        "id": "invoice-uuid",
        "invoice_number": "INV-2024-001",
        "party_name": "Acme Supplier Ltd",
        "total_amount": 100000.00,
        "outstanding": 50000.00
      },
      "amount_applied": 50000.00
    }
  ],
  "total_allocated": 50000.00
}
```

---

### 4. Allocate Payment to Invoice (POST)
**URL:** `POST /api/payments/{payment_id}/allocate/`  
**Role:** ADMIN, ACCOUNTANT  
**Purpose:** Link payment to an invoice

**Request Body:**
```json
{
  "invoice_id": "uuid",
  "amount_applied": 50000.00
}
```

**Validations:**
- Payment must be in DRAFT status
- Invoice must belong to same company
- Amount cannot exceed invoice outstanding
- Amount cannot exceed unallocated payment amount

**Response:** `201 Created`
```json
{
  "id": "line-uuid",
  "payment": "payment-uuid",
  "invoice": {
    "id": "invoice-uuid",
    "invoice_number": "INV-2024-001",
    "party_name": "Acme Supplier Ltd",
    "total_amount": 100000.00,
    "outstanding": 50000.00
  },
  "amount_applied": 50000.00
}
```

**Triggers:**
- Creates/updates PaymentLine
- Fires signal to refresh invoice outstanding
- Updates invoice status (PAID/PARTIALLY_PAID if needed)

---

### 5. Remove Allocation (DELETE)
**URL:** `DELETE /api/payments/{payment_id}/lines/{line_id}/`  
**Role:** ADMIN, ACCOUNTANT  
**Purpose:** Remove payment allocation

**Response:** `204 No Content`

**Validations:**
- Payment must be in DRAFT status

---

### 6. Post Payment to Accounting (POST)
**URL:** `POST /api/payments/{payment_id}/post_voucher/`  
**Role:** ADMIN, ACCOUNTANT  
**Purpose:** Finalize payment and create accounting entries

**Request Body:** (none)

**Validations:**
- Payment must be in DRAFT status
- Payment must have at least one allocation
- Cannot post cancelled payments

**Response:** `200 OK`
```json
{
  "voucher_id": "voucher-uuid",
  "voucher_number": "PAY-2024-0001",
  "status": "POSTED",
  "message": "Payment posted successfully"
}
```

**What Happens:**
1. Calls `PaymentPostingService.post_payment_voucher()`
2. Creates ledger entries:
   - Debit: Party Ledger (for payment to supplier)
   - Credit: Bank Account Ledger
3. Updates invoice outstanding amounts
4. Changes payment status to POSTED
5. Updates invoice status if fully paid
6. Creates voucher entries (idempotent)

**Idempotency:** 
If payment already posted, returns error with existing voucher_id.

---

## Models

### Payment
```python
Payment:
  - id: UUID
  - company: FK(Company)
  - voucher: FK(Voucher) - Auto-generated on creation
  - party: FK(Party) - Customer/Supplier
  - bank_account: FK(BankAccount) - Company's bank account
  - payment_date: Date
  - payment_mode: Choice (CASH, CHEQUE, etc.)
  - reference_number: String (optional)
  - status: Choice (DRAFT, POSTED, CANCELLED)
  - notes: Text
  - created_by: FK(User)
  - posted_voucher: FK(Voucher) - Final posted voucher
```

### PaymentLine
```python
PaymentLine:
  - id: UUID
  - payment: FK(Payment)
  - invoice: FK(Invoice)
  - amount_applied: Decimal
```

### Voucher (Auto-created)
```python
Voucher:
  - voucher_number: Auto-generated (PAY-YYYY-####)
  - voucher_type: Payment/Receipt
  - status: DRAFT/POSTED
  - lines: Ledger entries created on posting
```

---

## Payment Lifecycle

### 1. Create Draft Payment
```
POST /api/payments/create/
↓
Creates Payment (status=DRAFT)
Creates Voucher (status=DRAFT, auto-sequence number)
```

### 2. Allocate to Invoices
```
POST /api/payments/{id}/allocate/
↓
Creates PaymentLine
Fires signal → invoice.refresh_outstanding()
Updates invoice status if needed
```

You can allocate to multiple invoices by calling allocate multiple times.

### 3. Review & Adjust
```
GET /api/payments/{id}/
↓
View all allocations and total_allocated

DELETE /api/payments/{id}/lines/{line_id}/
↓
Remove incorrect allocations
```

### 4. Post to Accounting
```
POST /api/payments/{id}/post_voucher/
↓
Calls PaymentPostingService
Creates ledger entries (Debit/Credit)
Updates voucher status to POSTED
Updates payment status to POSTED
Updates invoice outstanding
Invoice status changes to PAID if fully settled
```

### 5. View Posted Payment
```
GET /api/payments/{id}/
↓
Status: POSTED
posted_voucher: Contains final voucher with entries
All invoices updated
```

---

## Usage Examples

### Example 1: Payment to Supplier

**Step 1: Create Draft Payment**
```bash
curl -X POST http://localhost:8000/api/payments/create/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "party_id": "supplier-uuid",
    "bank_account_id": "bank-uuid",
    "payment_type": "PAYMENT",
    "payment_date": "2024-01-15",
    "payment_mode": "BANK_TRANSFER",
    "reference_number": "TXN123456",
    "notes": "Payment for January purchases"
  }'
```

**Step 2: Allocate to Invoice 1**
```bash
curl -X POST http://localhost:8000/api/payments/{payment_id}/allocate/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "invoice-1-uuid",
    "amount_applied": 30000.00
  }'
```

**Step 3: Allocate to Invoice 2**
```bash
curl -X POST http://localhost:8000/api/payments/{payment_id}/allocate/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "invoice-2-uuid",
    "amount_applied": 20000.00
  }'
```

**Step 4: Review Payment**
```bash
curl http://localhost:8000/api/payments/{payment_id}/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response shows:
# - total_allocated: 50000.00
# - 2 payment lines
# - Both invoices with updated outstanding
```

**Step 5: Post Payment**
```bash
curl -X POST http://localhost:8000/api/payments/{payment_id}/post_voucher/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Creates:
# - Debit: Supplier Ledger (30000 + 20000)
# - Credit: Bank Account (50000)
# Updates:
# - Invoice 1 outstanding reduced by 30000
# - Invoice 2 outstanding reduced by 20000
# - Payment status → POSTED
```

---

### Example 2: Customer Receipt

**Create Receipt**
```bash
curl -X POST http://localhost:8000/api/payments/create/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "party_id": "customer-uuid",
    "bank_account_id": "bank-uuid",
    "payment_type": "RECEIPT",
    "payment_date": "2024-01-16",
    "payment_mode": "UPI",
    "reference_number": "UPI/123456789",
    "notes": "Receipt from ABC Corp"
  }'
```

**Allocate to Sales Invoice**
```bash
curl -X POST http://localhost:8000/api/payments/{receipt_id}/allocate/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "sales-invoice-uuid",
    "amount_applied": 100000.00
  }'
```

**Post Receipt**
```bash
curl -X POST http://localhost:8000/api/payments/{receipt_id}/post_voucher/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Creates:
# - Debit: Bank Account (100000)
# - Credit: Customer Ledger (100000)
# Updates:
# - Sales invoice outstanding reduced by 100000
# - Invoice status → PAID
```

---

### Example 3: List Outstanding Payments

**Draft Payments (Need Posting)**
```bash
curl "http://localhost:8000/api/payments/?status=DRAFT" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Posted Payments This Month**
```bash
curl "http://localhost:8000/api/payments/?status=POSTED&start_date=2024-01-01&end_date=2024-01-31" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**All Receipts**
```bash
curl "http://localhost:8000/api/payments/?payment_type=RECEIPT" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Integration

### With Invoice System

**Automatic Outstanding Update:**
When PaymentLine is created, a signal automatically:
1. Calls `invoice.refresh_outstanding()`
2. Recalculates `amount_received` from all PaymentLines
3. Updates invoice status:
   - `outstanding == 0` → Status: PAID
   - `0 < outstanding < total` → Status: PARTIALLY_PAID
   - `outstanding == total` → Status: UNPAID

**Invoice Outstanding Query:**
```python
# In your code
invoice = Invoice.objects.get(id=invoice_id)
outstanding = invoice.total_amount - invoice.amount_received
```

### With Accounting System

**Posting Flow:**
```
PaymentPostingService.post_payment_voucher()
↓
Creates VoucherLines:
  For PAYMENT:
    - Debit: Party Ledger (Accounts Payable)
    - Credit: Bank Account
  
  For RECEIPT:
    - Debit: Bank Account
    - Credit: Party Ledger (Accounts Receivable)
↓
Updates LedgerBalance for affected ledgers
↓
Invoice.refresh_outstanding() via signal
```

### With Voucher System

**Voucher Auto-Generation:**
- On payment creation, a voucher is automatically created
- Voucher number: `PAY-YYYY-####` or `REC-YYYY-####`
- Voucher type determined by payment_type
- Voucher status mirrors payment status

**Sequence Numbers:**
```python
# Handled by SequenceService
PAY-2024-0001  # First payment of 2024
PAY-2024-0002  # Second payment
REC-2024-0001  # First receipt
```

---

## Error Handling

### Common Errors

**400 Bad Request:**
```json
{
  "error": "Payment already posted"
}
```
- Cannot modify posted payments
- Cannot allocate after posting

```json
{
  "error": "Amount exceeds invoice outstanding"
}
```
- Allocation amount too high

```json
{
  "error": "Payment must have at least one allocation"
}
```
- Cannot post without allocations

**404 Not Found:**
```json
{
  "error": "Payment not found"
}
```
- Payment doesn't exist or wrong company

**403 Forbidden:**
- User lacks ADMIN or ACCOUNTANT role

---

## Best Practices

1. **Always Allocate Before Posting**
   - Draft payments without allocations cannot be posted
   - Allocate to specific invoices for accurate tracking

2. **Use Reference Numbers**
   - Store bank transaction IDs, cheque numbers, UPI refs
   - Helps reconciliation

3. **Check Outstanding First**
   - GET invoice details before allocating
   - Ensure amount doesn't exceed outstanding

4. **Review Before Posting**
   - Use GET payment details to review all allocations
   - Remove incorrect allocations with DELETE

5. **Monitor Status**
   - List DRAFT payments to find unposted entries
   - Post regularly to keep accounting up to date

6. **Handle Partial Payments**
   - Allocate partial amounts to multiple invoices
   - System tracks total_allocated automatically

---

## Related APIs

- **[Order APIs](ORDER_API_QUICKREF.md)**: Create sales/purchase orders
- **[Invoice APIs](INVOICE_API_QUICKREF.md)**: Generate invoices from orders
- **[Accounting APIs](POSTING_SERVICE_QUICKREF.md)**: Voucher posting system

---

## Support

For issues or questions:
1. Check model validations in `apps/voucher/models.py`
2. Review service logic in `apps/voucher/services/payment_service.py`
3. Check posting logic in `apps/accounting/services/payment_posting_service.py`
4. Review signals in `apps/voucher/signals.py`

**Payment Lifecycle Diagram:**
```
CREATE → ALLOCATE → ALLOCATE → ... → POST → DONE
DRAFT     DRAFT      DRAFT           POSTED   (terminal)
```
