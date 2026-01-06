# GST & FY API Quick Reference

**Quick access guide for GST returns and Financial Year management.**

---

## 🔐 Authentication

All endpoints require:
```http
Authorization: Bearer <jwt-token>
Company-ID: <company-uuid>
```

---

## 📊 GST APIs

### Generate GSTR-1

```bash
curl -X POST http://localhost:8000/api/gst/gstr1/generate/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID" \
  -H "Content-Type: application/json" \
  -d '{"period": "2024-07"}'
```

**Response:**
```json
{
  "status": "GENERATED",
  "gstr1_id": "uuid",
  "outward_taxable": "100000.00",
  "cgst": "9000.00",
  "sgst": "9000.00",
  "igst": "0.00",
  "total_tax": "18000.00"
}
```

---

### Generate GSTR-3B

```bash
curl -X POST http://localhost:8000/api/gst/gstr3b/generate/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID" \
  -H "Content-Type: application/json" \
  -d '{"period": "2024-07"}'
```

**Response:**
```json
{
  "status": "GENERATED",
  "gstr3b_id": "uuid",
  "cgst_payable": "4000.00",
  "sgst_payable": "4000.00",
  "igst_payable": "0.00",
  "total_payable": "8000.00"
}
```

---

### Get Returns by Period

```bash
curl -X GET http://localhost:8000/api/gst/returns/2024-07/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"
```

---

### List All Returns

```bash
# All returns
curl -X GET http://localhost:8000/api/gst/returns/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"

# Filter by year
curl -X GET http://localhost:8000/api/gst/returns/?year=2024 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"

# Filter by type
curl -X GET http://localhost:8000/api/gst/returns/?type=gstr1 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"
```

---

## 📅 Financial Year APIs

### List Financial Years

```bash
curl -X GET http://localhost:8000/api/company/financial_year/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"
```

**Response:**
```json
{
  "financial_years": [
    {
      "id": "uuid",
      "name": "FY 2023-24",
      "start_date": "2023-04-01",
      "end_date": "2024-03-31",
      "is_current": true,
      "is_closed": false
    }
  ]
}
```

---

### Close Financial Year

```bash
curl -X POST http://localhost:8000/api/company/financial_year/{fy_id}/close/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"
```

**Permissions:** ADMIN, ACCOUNTANT

---

### Reopen Financial Year

```bash
curl -X POST http://localhost:8000/api/company/financial_year/{fy_id}/reopen/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Company-ID: YOUR_COMPANY_UUID"
```

**⚠️ Permissions:** ADMIN only

---

## 🔄 Complete Workflow

### GST Return Filing

```bash
# 1. Post sales invoices for the month
POST /api/invoices/{invoice_id}/post/

# 2. Generate GSTR-1
POST /api/gst/gstr1/generate/
{"period": "2024-07"}

# 3. Generate GSTR-3B
POST /api/gst/gstr3b/generate/
{"period": "2024-07"}

# 4. Review returns
GET /api/gst/returns/2024-07/

# 5. Download/export for filing (future feature)
```

---

### Month-End Close

```bash
# 1. Ensure all vouchers posted
POST /api/vouchers/{voucher_id}/post/

# 2. Generate GST returns
POST /api/gst/gstr1/generate/
POST /api/gst/gstr3b/generate/

# 3. Review financials
GET /api/accounting/trial_balance/

# 4. Close previous FY (if end of year)
POST /api/company/financial_year/{fy_id}/close/
```

---

## ⚠️ Common Errors

### GST Errors

**Error:** `Invalid period format`
```json
{
  "error": "Invalid period format. Use YYYY-MM (e.g., 2024-07)"
}
```
**Fix:** Use format `YYYY-MM` (e.g., `2024-07`)

---

**Error:** `No invoices found for period`
```json
{
  "gstr1": {
    "outward_taxable": "0.00",
    "total_tax": "0.00"
  }
}
```
**Fix:** Normal - means no posted invoices for that period

---

### Financial Year Errors

**Error:** `Financial year is closed`
```json
{
  "error": "Financial year FY 2023-24 is closed. Posting and reversal are not allowed."
}
```
**Fix:** Contact ADMIN to reopen FY, or post in current FY

---

**Error:** `Cannot close current financial year`
```json
{
  "error": "Cannot close the current financial year. Please set another FY as current first."
}
```
**Fix:** Set next FY as current before closing this one

---

**Error:** `Only ADMIN can reopen financial years`
```json
{
  "error": "You do not have permission to perform this action."
}
```
**Fix:** Contact ADMIN user

---

## 🎯 Permission Matrix

| Endpoint | ADMIN | ACCOUNTANT | SALES | RETAILER |
|----------|-------|------------|-------|----------|
| Generate GSTR-1 | ✅ | ✅ | ❌ | ❌ |
| Generate GSTR-3B | ✅ | ✅ | ❌ | ❌ |
| View Returns | ✅ | ✅ | ✅ | ✅ |
| List Returns | ✅ | ✅ | ✅ | ✅ |
| Close FY | ✅ | ✅ | ❌ | ❌ |
| Reopen FY | ✅ | ❌ | ❌ | ❌ |

---

## 📝 Period Format

**GST Period:** `YYYY-MM`

Examples:
- January 2024: `2024-01`
- July 2024: `2024-07`
- December 2024: `2024-12`

**Important:** Always use 2-digit month (e.g., `01` not `1`)

---

## 🔍 Testing

```bash
# Test GST generation
python manage.py shell
>>> from integrations.gst.services.returns_service import GSTReturnService
>>> from apps.company.models import Company
>>> company = Company.objects.first()
>>> gstr1 = GSTReturnService.generate_gstr1(company, "2024-07")
>>> print(gstr1.total_tax)

# Test FY guard
>>> from core.services.guards import guard_fy_open
>>> from apps.voucher.models import Voucher
>>> voucher = Voucher.objects.first()
>>> guard_fy_open(voucher)  # Should pass if FY open
```

---

## 📚 Related Documentation

- [COMPLIANCE_IMPLEMENTATION_COMPLETE.md](COMPLIANCE_IMPLEMENTATION_COMPLETE.md) - Full implementation guide
- [POSTING_SERVICE_QUICKREF.md](POSTING_SERVICE_QUICKREF.md) - Posting engine
- [VOUCHER_REVERSAL_API_QUICKREF.md](VOUCHER_REVERSAL_API_QUICKREF.md) - Reversal API

---

**Version:** 1.0  
**Last Updated:** December 26, 2025
