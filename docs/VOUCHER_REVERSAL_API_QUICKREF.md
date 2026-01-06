# Voucher Reversal API - Quick Reference

Complete guide for reversing posted vouchers in the Vendor ERP Backend.

## Table of Contents
1. [Overview](#overview)
2. [Endpoint](#endpoint)
3. [Reversal Workflow](#reversal-workflow)
4. [Guards & Validations](#guards--validations)
5. [Usage Examples](#usage-examples)
6. [Integration](#integration)
7. [Permissions](#permissions)

---

## Overview

The Voucher Reversal API provides SAP/Oracle-grade reversal capability for correcting posted accounting entries.

**Key Features:**
- Immutable audit trail (original voucher never modified)
- Creates opposite DR/CR entries automatically
- Reverses stock movements (IN ↔ OUT swap)
- Financial year locking support
- Admin override for closed periods
- Auto-updates invoice outstanding
- Full integration with accounting and inventory

**What Gets Reversed:**
- ✅ Ledger entries (DR ↔ CR swap)
- ✅ Stock movements (IN ↔ OUT swap, godown swap)
- ✅ Invoice allocations (outstanding recalculated)
- ✅ Payment applications
- ❌ Original voucher (remains untouched for audit)

**Reversal Status Flow:**
```
Original Voucher: POSTED → REVERSED (marked, not modified)
Reversal Voucher: Created as POSTED with opposite entries
```

---

## Endpoint

### Reverse Voucher (POST)
**URL:** `POST /api/payments/vouchers/{voucher_id}/reverse/`  
**Role:** ADMIN, ACCOUNTANT  
**Purpose:** Create reversal voucher with opposite entries

**Request Body:**
```json
{
  "reason": "Incorrect invoice allocation - payment applied to wrong invoice",
  "override": false
}
```

**Parameters:**
- `reason` (string, **required**): Reason for reversal (audit trail)
- `override` (boolean, optional): Override financial year lock
  - Default: `false`
  - Only ADMIN role can use `true`
  - Allows reversal in closed financial year

**Response:** `200 OK`
```json
{
  "reversed_voucher": "reversal-voucher-uuid",
  "reversed_voucher_number": "REV-PAY-2024-0001",
  "original_voucher": "original-voucher-uuid",
  "original_voucher_number": "PAY-2024-0001",
  "status": "REVERSED",
  "reason": "Incorrect invoice allocation - payment applied to wrong invoice",
  "message": "Voucher PAY-2024-0001 reversed successfully"
}
```

**Error Responses:**

`400 Bad Request` - Validation errors:
```json
{
  "error": "Reason for reversal is required"
}
```

```json
{
  "error": "Cannot reverse voucher PAY-2024-0001. Only POSTED vouchers can be reversed (current status: DRAFT)."
}
```

```json
{
  "error": "Voucher PAY-2024-0001 has already been reversed."
}
```

```json
{
  "error": "Financial year 2023-2024 is closed. Cannot modify vouchers in closed periods."
}
```

`403 Forbidden` - Insufficient permissions:
```json
{
  "error": "User does not have required role: ADMIN or ACCOUNTANT"
}
```

`404 Not Found`:
```json
{
  "error": "Voucher not found"
}
```

---

## Reversal Workflow

### Step-by-Step Process

```
1. User initiates reversal
   ↓
2. API validates permissions (ADMIN or ACCOUNTANT)
   ↓
3. Fetch voucher with company scoping
   ↓
4. Guard: Check voucher is POSTED
   ↓
5. Guard: Check not already REVERSED
   ↓
6. Guard: Check financial year is open (or override)
   ↓
7. VoucherReversalService.reverse_voucher()
   ↓
   ├─ Create new reversal voucher
   ├─ Copy all lines with opposite DR/CR
   ├─ Reverse stock movements (swap IN/OUT)
   ├─ Update ledger balances
   ├─ Update stock balances
   ├─ Mark original as REVERSED
   ├─ Create audit log
   └─ Emit integration event
   ↓
8. Signal fires: rebuild_invoice_outstanding_after_reversal
   ↓
9. Invoices linked to voucher recalculate outstanding
   ↓
10. Return reversal voucher details
```

### What Happens Internally

**Original Voucher (PAY-2024-0001):**
```
DR: Supplier Ledger     50,000
CR: Bank Account        50,000
Status: POSTED → REVERSED
```

**Reversal Voucher (REV-PAY-2024-0001):**
```
DR: Bank Account        50,000
CR: Supplier Ledger     50,000
Status: POSTED (new voucher)
Reference: "REV-PAY-2024-0001"
```

**Net Effect:**
- Both vouchers remain in ledger
- Combined effect: Zero (DR = CR)
- Full audit trail maintained
- Can run trial balance anytime

---

## Guards & Validations

### 1. Voucher Status Guard
**Function:** `guard_voucher_posted(voucher)`

**Rule:** Only POSTED vouchers can be reversed

**Why:** Draft/Cancelled vouchers should be edited or deleted, not reversed

**Error:**
```
Cannot reverse voucher PAY-2024-0001. Only POSTED vouchers can be reversed (current status: DRAFT).
```

---

### 2. Already Reversed Guard
**Function:** `guard_voucher_not_reversed(voucher)`

**Rule:** Cannot reverse a voucher twice

**Why:** Prevents duplicate reversal entries

**Error:**
```
Voucher PAY-2024-0001 has already been reversed.
```

---

### 3. Financial Year Lock Guard
**Function:** `guard_financial_year_open(voucher, allow_override=False)`

**Rule:** Cannot reverse vouchers in closed financial year

**Why:** Maintains period closing integrity

**Override:** ADMIN can set `override: true` in request

**Error:**
```
Financial year 2023-2024 is closed. Cannot modify vouchers in closed periods.
```

**With Override (ADMIN only):**
```json
{
  "reason": "Year-end adjustment approved by management",
  "override": true
}
```

---

### 4. Company Scoping
**Automatic:** Built into `get_voucher(company, voucher_id)`

**Rule:** Users can only reverse vouchers in their current company

**Error:**
```
Voucher not found
```
(404 if wrong company or doesn't exist)

---

## Usage Examples

### Example 1: Reverse Payment Voucher

**Scenario:** Payment applied to wrong invoice

**Step 1: Check voucher details**
```bash
curl http://localhost:8000/api/payments/{payment_id}/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response shows voucher_id
```

**Step 2: Reverse the voucher**
```bash
curl -X POST http://localhost:8000/api/payments/vouchers/{voucher_id}/reverse/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Payment applied to wrong invoice - Invoice INV-2024-002 instead of INV-2024-001"
  }'
```

**Response:**
```json
{
  "reversed_voucher": "new-reversal-uuid",
  "reversed_voucher_number": "REV-PAY-2024-0001",
  "original_voucher": "original-uuid",
  "original_voucher_number": "PAY-2024-0001",
  "status": "REVERSED",
  "reason": "Payment applied to wrong invoice - Invoice INV-2024-002 instead of INV-2024-001",
  "message": "Voucher PAY-2024-0001 reversed successfully"
}
```

**What Happened:**
1. Original payment voucher marked as REVERSED
2. New reversal voucher created with opposite entries
3. Ledger balances restored to pre-payment state
4. Invoice outstanding recalculated (payment unapplied)
5. Invoice status changed back to UNPAID/PARTIALLY_PAID

**Step 3: Create correct payment**
```bash
# Now create new payment and allocate to correct invoice
curl -X POST http://localhost:8000/api/payments/create/ ...
```

---

### Example 2: Reverse with Financial Year Override

**Scenario:** Need to reverse entry in closed year (ADMIN only)

```bash
curl -X POST http://localhost:8000/api/payments/vouchers/{voucher_id}/reverse/ \
  -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Audit adjustment approved by CFO - Correction of FY2023 accruals",
    "override": true
  }'
```

**Requirements:**
- User must have ADMIN role
- `override: true` must be explicitly set
- Valid reason still required for audit

**Note:** ACCOUNTANT role **cannot** use override, even if they set `override: true`

---

### Example 3: Handle Already Reversed Error

**Attempt:**
```bash
curl -X POST http://localhost:8000/api/payments/vouchers/{voucher_id}/reverse/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Testing reversal"
  }'
```

**Response:** `400 Bad Request`
```json
{
  "error": "Voucher PAY-2024-0001 has already been reversed."
}
```

**Solution:** Check voucher status first
```bash
# Get payment details
curl http://localhost:8000/api/payments/{payment_id}/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response will show:
# "status": "REVERSED"
# "posted_voucher": { ... }  # Contains reversal voucher info
```

---

### Example 4: Bulk Reversal Workflow

**Scenario:** Reverse multiple incorrect payments

```bash
#!/bin/bash
# reversal_script.sh

VOUCHERS=("uuid1" "uuid2" "uuid3")
REASON="Batch correction - Wrong bank account used"
TOKEN="YOUR_JWT_TOKEN"

for voucher_id in "${VOUCHERS[@]}"; do
  echo "Reversing voucher: $voucher_id"
  
  curl -X POST "http://localhost:8000/api/payments/vouchers/$voucher_id/reverse/" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"reason\": \"$REASON\"}" \
    | jq '.'
  
  echo "---"
done
```

---

## Integration

### With Accounting System

**Ledger Entries:**

Original voucher (Payment):
```
Date: 2024-01-15
PAY-2024-0001
  DR: Supplier A/P      50,000
  CR: Bank Account      50,000
```

Reversal voucher:
```
Date: 2024-01-20 (reversal date)
REV-PAY-2024-0001
  DR: Bank Account      50,000
  CR: Supplier A/P      50,000
  Reference: "Reversal of PAY-2024-0001: Incorrect invoice allocation"
```

**Ledger Balances:**
- `LedgerBalance` updated for affected ledgers
- DR/CR direction swapped
- Running balances recalculated

---

### With Invoice System

**Automatic Outstanding Update:**

Signal: `rebuild_invoice_outstanding_after_reversal`

Triggered when voucher status changes to REVERSED

```python
# What happens automatically:
1. Find all invoices linked to reversed voucher
2. For each invoice:
   - Call invoice.refresh_outstanding()
   - Recalculate amount_received from PaymentLines
   - Update invoice status (PAID → PARTIALLY_PAID or UNPAID)
   - Save updated invoice
```

**Example:**

Before reversal:
```
Invoice INV-2024-001
  Total: 100,000
  Received: 50,000
  Outstanding: 50,000
  Status: PARTIALLY_PAID
```

After payment reversal:
```
Invoice INV-2024-001
  Total: 100,000
  Received: 0
  Outstanding: 100,000
  Status: UNPAID
```

---

### With Inventory System

**Stock Movement Reversal:**

Original voucher (Stock IN):
```
Stock Movement:
  Product: Widget A
  Godown: Main Warehouse (IN)
  Quantity: +100 units
  Type: INWARD
```

Reversal voucher (Stock OUT):
```
Stock Movement:
  Product: Widget A
  Godown: Main Warehouse (OUT)
  Quantity: -100 units
  Type: OUTWARD
  Reference: "Reversal of original stock IN"
```

**Stock Balance:**
- `StockBalance.quantity` adjusted
- Net effect: Zero change
- Full movement history preserved

---

### With Audit System

**Audit Trail:**

```python
AuditLog Entry:
  Company: XYZ Corp
  User: john@example.com
  Action: VOUCHER_REVERSED
  Object: Voucher PAY-2024-0001
  Details:
    - Original voucher: PAY-2024-0001
    - Reversal voucher: REV-PAY-2024-0001
    - Reason: "Incorrect invoice allocation"
    - Reversed by: john@example.com
    - Reversed at: 2024-01-20 14:30:00
  Timestamp: 2024-01-20 14:30:00
```

---

### With Integration Events

**Event Emitted:**

```json
IntegrationEvent {
  "event_type": "voucher.reversed",
  "company_id": "company-uuid",
  "payload": {
    "original_voucher": {
      "id": "original-uuid",
      "voucher_number": "PAY-2024-0001"
    },
    "reversal_voucher": {
      "id": "reversal-uuid",
      "voucher_number": "REV-PAY-2024-0001"
    },
    "reversal_reason": "Incorrect invoice allocation",
    "reversed_by": "john@example.com",
    "reversed_at": "2024-01-20T14:30:00Z"
  },
  "source_object_type": "Voucher",
  "source_object_id": "original-uuid",
  "created_at": "2024-01-20T14:30:00Z"
}
```

**Use Cases:**
- Notify external accounting systems
- Trigger report regeneration
- Send email notifications
- Update data warehouse
- Webhook to third-party apps

---

## Permissions

### Role Matrix

| Role | Reverse Allowed? | Override FY Lock? | Notes |
|------|-----------------|-------------------|-------|
| ADMIN | ✅ Yes | ✅ Yes | Full reversal rights including closed periods |
| ACCOUNTANT | ✅ Yes | ❌ No | Can reverse in open periods only |
| SALES_MANAGER | ❌ No | ❌ No | Cannot reverse vouchers |
| SALES | ❌ No | ❌ No | Cannot reverse vouchers |
| VIEWER | ❌ No | ❌ No | Read-only access |
| RETAILER | ❌ No | ❌ No | Portal users cannot reverse |

### Permission Enforcement

**API Level:**
```python
permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
```

**Override Check:**
```python
allow_override = override and 'ADMIN' in request.user.roles
guard_financial_year_open(voucher, allow_override=allow_override)
```

**Result:**
- ACCOUNTANT with `override: true` → **Still blocked** (no ADMIN role)
- ADMIN with `override: true` → **Allowed**
- ADMIN with `override: false` → **Blocked if FY closed**

---

## Best Practices

### 1. Always Provide Detailed Reason
```json
❌ Bad: {"reason": "error"}
✅ Good: {"reason": "Payment applied to Invoice INV-2024-002 instead of INV-2024-001 - Correcting allocation"}
```

### 2. Check Before Reversing
```bash
# Verify voucher status
curl http://localhost:8000/api/payments/{payment_id}/ \
  -H "Authorization: Bearer TOKEN"

# Check if already reversed
# Look for: "status": "REVERSED"
```

### 3. Use Override Sparingly
- Only for genuine period adjustments
- Document approval (CFO, auditor)
- Include approval reference in reason

### 4. Verify After Reversal
```bash
# 1. Check original voucher marked as REVERSED
# 2. Check reversal voucher created
# 3. Check invoice outstanding updated
# 4. Check ledger balances restored
```

### 5. Handle Errors Gracefully
```javascript
// Frontend example
async function reverseVoucher(voucherId, reason) {
  try {
    const response = await api.post(
      `/api/payments/vouchers/${voucherId}/reverse/`,
      { reason }
    );
    return { success: true, data: response.data };
  } catch (error) {
    if (error.response?.status === 400) {
      // Validation error - show to user
      return { success: false, error: error.response.data.error };
    } else if (error.response?.status === 403) {
      // Permission denied
      return { success: false, error: 'You do not have permission to reverse vouchers' };
    }
    throw error; // Unexpected error
  }
}
```

---

## Troubleshooting

### Issue: "Voucher not found"

**Causes:**
1. Wrong company context
2. Voucher ID incorrect
3. Voucher doesn't exist

**Solution:**
```bash
# 1. Verify company context
curl http://localhost:8000/auth/me/ -H "Authorization: Bearer TOKEN"

# 2. List payments to find correct voucher
curl http://localhost:8000/api/payments/ -H "Authorization: Bearer TOKEN"

# 3. Check voucher ID from payment details
curl http://localhost:8000/api/payments/{payment_id}/ -H "Authorization: Bearer TOKEN"
```

---

### Issue: "Financial year is closed"

**Causes:**
1. Voucher in closed period
2. No override permission

**Solution (ADMIN only):**
```json
{
  "reason": "Year-end audit adjustment - Approved by CFO",
  "override": true
}
```

**Solution (ACCOUNTANT):**
- Request ADMIN to perform reversal
- Or reopen financial year temporarily

---

### Issue: "Already reversed"

**Cause:** Voucher has been reversed previously

**Solution:**
1. Check reversal voucher details
2. If reversal was wrong, reverse the reversal voucher instead
3. This creates a "reverse of reverse" = back to original

---

## Related APIs

- **[Payment APIs](PAYMENT_API_QUICKREF.md)** - Create and manage payments
- **[Invoice APIs](INVOICE_API_QUICKREF.md)** - Invoice generation and posting
- **[Posting Service](POSTING_SERVICE_QUICKREF.md)** - Voucher posting system

---

## Architecture Notes

### Immutable Audit Trail

**Original voucher is NEVER modified:**
- Voucher number remains same
- All lines remain intact
- Posted date unchanged
- Only status field changes: POSTED → REVERSED
- Adds reversal tracking fields:
  - `reversed_voucher_id` → points to reversal
  - `reversed_at` → reversal timestamp
  - `reversal_reason` → audit note
  - `reversal_user` → who reversed it

**Reversal voucher is new record:**
- New UUID
- New voucher number (REV-XXX-####)
- Opposite DR/CR entries
- Reference to original
- Posted immediately (no draft state)

### Financial Integrity

**Double-entry accounting maintained:**
```
Original + Reversal = Zero net effect
DR total = CR total (always balanced)
```

**Ledger balance correctness:**
```
Running balance = Sum of all voucher lines
Including both original and reversal
```

**Stock accuracy:**
```
Stock balance = Sum of all movements
IN movements - OUT movements
Reversals properly swap IN/OUT
```

---

**Implementation Date:** December 2024  
**Status:** ✅ PRODUCTION READY
