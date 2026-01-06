# Ledger & Account APIs - Quick Reference

Complete guide to the financial accounting APIs including ledger management and financial reporting.

## Table of Contents
- [Authentication](#authentication)
- [Company Scoping](#company-scoping)
- [Ledger Management](#ledger-management)
- [Account Groups](#account-groups)
- [Financial Years](#financial-years)
- [Financial Reports](#financial-reports)
- [Role-Based Access](#role-based-access)
- [Error Handling](#error-handling)

---

## Authentication

All API endpoints require JWT authentication:

```http
Authorization: Bearer <access_token>
```

The token contains:
- `user_id`: User identification
- `active_company`: Current company context
- `roles`: User roles for permission checking

---

## Company Scoping

**All data is automatically scoped to the user's `active_company`.**

- You cannot create/read/update/delete data from other companies
- When creating records, `company` field is auto-populated
- Queries automatically filter by company
- Attempting to access other companies' data returns `404 Not Found`

To switch companies, use the auth endpoint:
```http
POST /auth/switch-company/
{
  "company_id": 2
}
```

---

## Ledger Management

### List Ledgers
```http
GET /api/accounting/ledgers/
```

**Query Parameters:**
- `group`: Filter by account group ID
- `is_active`: Filter by active status (true/false)
- `search`: Search by name or code
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20)

**Response:**
```json
{
  "count": 50,
  "next": "http://api/accounting/ledgers/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "company": 1,
      "group": {
        "id": 1,
        "name": "Current Assets",
        "code": "CA",
        "group_type": "ASSET"
      },
      "name": "Cash",
      "code": "CASH",
      "opening_balance": "50000.00",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Create Ledger
```http
POST /api/accounting/ledgers/
Content-Type: application/json

{
  "name": "Petty Cash",
  "code": "PCASH",
  "group": 1,
  "opening_balance": "5000.00",
  "is_active": true
}
```

**Validation:**
- `name`: Required, max 200 chars
- `code`: Required, unique within company, max 50 chars
- `group`: Required, must belong to same company
- `opening_balance`: Optional, decimal (default: 0.00)

**Response:** `201 Created` with ledger object

### Get Ledger Details
```http
GET /api/accounting/ledgers/{id}/
```

**Response:**
```json
{
  "id": 1,
  "company": 1,
  "group": {
    "id": 1,
    "name": "Current Assets",
    "code": "CA",
    "group_type": "ASSET"
  },
  "name": "Cash",
  "code": "CASH",
  "opening_balance": "50000.00",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Update Ledger
```http
PATCH /api/accounting/ledgers/{id}/
Content-Type: application/json

{
  "name": "Main Cash Account",
  "is_active": false
}
```

**Response:** `200 OK` with updated ledger

### Delete Ledger
```http
DELETE /api/accounting/ledgers/{id}/
```

**Response:** `204 No Content`

**Note:** Cannot delete ledgers with transactions. Soft delete by setting `is_active=false` instead.

### Get Ledger Balance
```http
GET /api/accounting/ledgers/{id}/balance/?financial_year_id={year_id}
```

**Query Parameters:**
- `financial_year_id`: Required, ID of financial year

**Response:**
```json
{
  "ledger_id": 1,
  "ledger_name": "Cash",
  "financial_year": "FY2024",
  "balance_dr": "50000.00",
  "balance_cr": "0.00",
  "net": "50000.00"
}
```

### Get Ledger Statement
```http
GET /api/accounting/ledgers/{id}/statement/
  ?financial_year_id={year_id}
  &start_date=2024-04-01
  &end_date=2024-09-30
```

**Query Parameters:**
- `financial_year_id`: Required, ID of financial year
- `start_date`: Optional, filter from date (YYYY-MM-DD)
- `end_date`: Optional, filter to date (YYYY-MM-DD)

**Response:**
```json
{
  "ledger": {
    "id": 1,
    "name": "Cash",
    "code": "CASH"
  },
  "financial_year": "FY2024",
  "opening_balance": "50000.00",
  "transactions": [
    {
      "date": "2024-04-05",
      "voucher_number": "JV-001",
      "voucher_type": "JOURNAL",
      "particulars": "Cash received from customer",
      "debit": "25000.00",
      "credit": "0.00",
      "running_balance": "75000.00"
    },
    {
      "date": "2024-04-10",
      "voucher_number": "PV-001",
      "voucher_type": "PAYMENT",
      "particulars": "Rent payment",
      "debit": "0.00",
      "credit": "10000.00",
      "running_balance": "65000.00"
    }
  ],
  "closing_balance": "65000.00"
}
```

---

## Account Groups

### List Account Groups
```http
GET /api/accounting/groups/
```

**Query Parameters:**
- `group_type`: Filter by type (ASSET, LIABILITY, INCOME, EXPENSE, EQUITY)
- `is_active`: Filter by active status

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "company": 1,
      "name": "Current Assets",
      "code": "CA",
      "group_type": "ASSET",
      "parent": null,
      "is_active": true
    }
  ]
}
```

### Create Account Group
```http
POST /api/accounting/groups/
Content-Type: application/json

{
  "name": "Fixed Assets",
  "code": "FA",
  "group_type": "ASSET",
  "parent": null,
  "is_active": true
}
```

**Group Types:**
- `ASSET`: Assets
- `LIABILITY`: Liabilities
- `INCOME`: Income/Revenue
- `EXPENSE`: Expenses
- `EQUITY`: Equity/Capital

---

## Financial Years

### List Financial Years
```http
GET /api/accounting/financial-years/
```

**Response:**
```json
{
  "results": [
    {
      "id": 1,
      "company": 1,
      "year_code": "FY2024",
      "start_date": "2024-04-01",
      "end_date": "2025-03-31",
      "is_active": true,
      "is_closed": false
    }
  ]
}
```

### Create Financial Year
```http
POST /api/accounting/financial-years/
Content-Type: application/json

{
  "year_code": "FY2025",
  "start_date": "2025-04-01",
  "end_date": "2026-03-31",
  "is_active": true
}
```

**Validation:**
- `start_date` must be before `end_date`
- Cannot have overlapping financial years for same company
- `year_code` must be unique within company

---

## Financial Reports

### Trial Balance

**Permissions Required:** `ADMIN`, `ACCOUNTANT`, or `MANAGER`

```http
GET /api/accounting/reports/trial-balance/?financial_year_id={year_id}
```

**Query Parameters:**
- `financial_year_id`: Required, ID of financial year

**Response:**
```json
{
  "company": {
    "id": 1,
    "name": "Test Company",
    "code": "TST001"
  },
  "financial_year": {
    "id": 1,
    "year_code": "FY2024",
    "start_date": "2024-04-01",
    "end_date": "2025-03-31"
  },
  "ledgers": [
    {
      "ledger_id": 1,
      "name": "Cash",
      "group": "Current Assets",
      "balance_dr": "50000.00",
      "balance_cr": "0.00",
      "net": "50000.00"
    },
    {
      "ledger_id": 5,
      "name": "Capital",
      "group": "Liabilities",
      "balance_dr": "0.00",
      "balance_cr": "150000.00",
      "net": "-150000.00"
    }
  ],
  "total_debit": "250000.00",
  "total_credit": "250000.00",
  "difference": "0.00",
  "is_balanced": true,
  "generated_at": "2024-01-15T14:30:00Z"
}
```

**Interpretation:**
- `is_balanced: true` → Trial balance is correct (difference < 0.01)
- `is_balanced: false` → There's an error in accounting entries
- All DR balances should equal all CR balances

### Profit & Loss Statement

**Permissions Required:** `ADMIN`, `ACCOUNTANT`, or `MANAGER`

```http
GET /api/accounting/reports/pl/?financial_year_id={year_id}
```

**Query Parameters:**
- `financial_year_id`: Required, ID of financial year

**Response:**
```json
{
  "company": {
    "id": 1,
    "name": "Test Company",
    "code": "TST001"
  },
  "financial_year": {
    "id": 1,
    "year_code": "FY2024",
    "start_date": "2024-04-01",
    "end_date": "2025-03-31"
  },
  "income_ledgers": [
    {
      "ledger_id": 10,
      "name": "Sales",
      "group": "Income",
      "amount": "500000.00"
    },
    {
      "ledger_id": 11,
      "name": "Service Income",
      "group": "Income",
      "amount": "150000.00"
    }
  ],
  "total_income": "650000.00",
  "expense_ledgers": [
    {
      "ledger_id": 20,
      "name": "Rent Expense",
      "group": "Expense",
      "amount": "120000.00"
    },
    {
      "ledger_id": 21,
      "name": "Salary Expense",
      "group": "Expense",
      "amount": "300000.00"
    }
  ],
  "total_expense": "420000.00",
  "net_profit": "230000.00",
  "generated_at": "2024-01-15T14:30:00Z"
}
```

**Interpretation:**
- `net_profit > 0` → Profit (Income > Expenses)
- `net_profit < 0` → Loss (Expenses > Income)
- Formula: `Net Profit = Total Income - Total Expenses`

### Balance Sheet

**Permissions Required:** `ADMIN`, `ACCOUNTANT`, or `MANAGER`

```http
GET /api/accounting/reports/bs/?financial_year_id={year_id}
```

**Query Parameters:**
- `financial_year_id`: Required, ID of financial year

**Response:**
```json
{
  "company": {
    "id": 1,
    "name": "Test Company",
    "code": "TST001"
  },
  "financial_year": {
    "id": 1,
    "year_code": "FY2024",
    "start_date": "2024-04-01",
    "end_date": "2025-03-31"
  },
  "asset_ledgers": [
    {
      "ledger_id": 1,
      "name": "Cash",
      "group": "Current Assets",
      "amount": "50000.00"
    },
    {
      "ledger_id": 2,
      "name": "Bank Account",
      "group": "Current Assets",
      "amount": "200000.00"
    }
  ],
  "total_assets": "250000.00",
  "liability_ledgers": [
    {
      "ledger_id": 30,
      "name": "Capital",
      "group": "Liabilities",
      "amount": "200000.00"
    },
    {
      "ledger_id": 31,
      "name": "Loan",
      "group": "Liabilities",
      "amount": "50000.00"
    }
  ],
  "total_liabilities": "250000.00",
  "equity_ledgers": [],
  "total_equity": "0.00",
  "difference": "0.00",
  "balance_check": true,
  "generated_at": "2024-01-15T14:30:00Z"
}
```

**Interpretation:**
- `balance_check: true` → Balance sheet is correct
- Formula: `Assets = Liabilities + Equity`
- `difference` should be near zero (< 0.01)

---

## Role-Based Access

### Permission Matrix

| Endpoint | ADMIN | ACCOUNTANT | MANAGER | SALES | VIEW_ONLY |
|----------|-------|------------|---------|-------|-----------|
| List Ledgers | ✅ | ✅ | ✅ | ✅ | ✅ |
| Create Ledger | ✅ | ✅ | ❌ | ❌ | ❌ |
| Update Ledger | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete Ledger | ✅ | ✅ | ❌ | ❌ | ❌ |
| Trial Balance | ✅ | ✅ | ✅ | ❌ | ❌ |
| Profit & Loss | ✅ | ✅ | ✅ | ❌ | ❌ |
| Balance Sheet | ✅ | ✅ | ✅ | ❌ | ❌ |
| Ledger Balance | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ledger Statement | ✅ | ✅ | ✅ | ✅ | ✅ |

### Role Enforcement

Roles are automatically enforced based on JWT token claims:

```python
# In views.py
class TrialBalanceView(APIView):
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT', 'MANAGER'])]
```

If user lacks required role:
```json
{
  "detail": "You do not have permission to perform this action."
}
```
HTTP Status: `403 Forbidden`

---

## Error Handling

### Common Error Responses

#### 400 Bad Request
```json
{
  "code": ["This field is required."],
  "name": ["Ensure this field has no more than 200 characters."]
}
```

#### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### 404 Not Found
```json
{
  "detail": "Not found."
}
```

**Note:** Attempting to access another company's data returns 404 (not 403) for security.

#### 404 Financial Year Not Found
```json
{
  "error": "Financial year not found or does not belong to your company"
}
```

### Validation Errors

#### Duplicate Ledger Code
```json
{
  "code": ["Ledger with this code already exists in this company."]
}
```

#### Invalid Financial Year Dates
```json
{
  "end_date": ["End date must be after start date."]
}
```

---

## Performance Notes

### Caching Strategy

All financial reports use the `LedgerBalance` model instead of querying `VoucherLine` directly:

- ✅ **Fast:** Queries pre-computed balances
- ✅ **Scalable:** Works with millions of transactions
- ⚠️ **Cache Invalidation:** Requires updating LedgerBalance when vouchers are posted

### Future Enhancements

Signals in `apps/voucher/signals.py` provide hooks for:
- Redis cache invalidation
- Materialized view refresh
- Background report regeneration
- Real-time balance updates

---

## Code Examples

### Python (requests)

```python
import requests

# Login
response = requests.post('http://api/auth/login/', json={
    'username': 'admin@company.com',
    'password': 'secret'
})
token = response.json()['access']

# Get Trial Balance
headers = {'Authorization': f'Bearer {token}'}
response = requests.get(
    'http://api/accounting/reports/trial-balance/',
    params={'financial_year_id': 1},
    headers=headers
)
trial_balance = response.json()

print(f"Total Debit: {trial_balance['total_debit']}")
print(f"Total Credit: {trial_balance['total_credit']}")
print(f"Is Balanced: {trial_balance['is_balanced']}")
```

### JavaScript (fetch)

```javascript
// Login
const loginResponse = await fetch('http://api/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin@company.com',
    password: 'secret'
  })
});
const { access } = await loginResponse.json();

// Create Ledger
const ledgerResponse = await fetch('http://api/accounting/ledgers/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Petty Cash',
    code: 'PCASH',
    group: 1,
    opening_balance: '5000.00',
    is_active: true
  })
});
const ledger = await ledgerResponse.json();
console.log('Created ledger:', ledger);
```

---

## Testing

Run the test suite:

```bash
# All accounting API tests
pytest tests/test_accounting_apis.py -v

# Specific test class
pytest tests/test_accounting_apis.py::TestTrialBalance -v

# Specific test
pytest tests/test_accounting_apis.py::TestTrialBalance::test_trial_balance_calculation -v
```

Expected output:
```
tests/test_accounting_apis.py::TestLedgerCRUD::test_list_ledgers PASSED
tests/test_accounting_apis.py::TestLedgerCRUD::test_create_ledger PASSED
tests/test_accounting_apis.py::TestTrialBalance::test_trial_balance_calculation PASSED
tests/test_accounting_apis.py::TestProfitLoss::test_pl_calculation PASSED
tests/test_accounting_apis.py::TestBalanceSheet::test_balance_sheet_equation PASSED

==================== 30 passed in 5.23s ====================
```

---

## API Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Ledgers** |
| GET | `/api/accounting/ledgers/` | List all ledgers |
| POST | `/api/accounting/ledgers/` | Create new ledger |
| GET | `/api/accounting/ledgers/{id}/` | Get ledger details |
| PATCH | `/api/accounting/ledgers/{id}/` | Update ledger |
| DELETE | `/api/accounting/ledgers/{id}/` | Delete ledger |
| GET | `/api/accounting/ledgers/{id}/balance/` | Get ledger balance |
| GET | `/api/accounting/ledgers/{id}/statement/` | Get ledger statement |
| **Account Groups** |
| GET | `/api/accounting/groups/` | List account groups |
| POST | `/api/accounting/groups/` | Create account group |
| GET | `/api/accounting/groups/{id}/` | Get group details |
| PATCH | `/api/accounting/groups/{id}/` | Update group |
| DELETE | `/api/accounting/groups/{id}/` | Delete group |
| **Financial Years** |
| GET | `/api/accounting/financial-years/` | List financial years |
| POST | `/api/accounting/financial-years/` | Create financial year |
| GET | `/api/accounting/financial-years/{id}/` | Get year details |
| PATCH | `/api/accounting/financial-years/{id}/` | Update year |
| DELETE | `/api/accounting/financial-years/{id}/` | Delete year |
| **Reports** |
| GET | `/api/accounting/reports/trial-balance/` | Generate trial balance |
| GET | `/api/accounting/reports/pl/` | Generate P&L statement |
| GET | `/api/accounting/reports/bs/` | Generate balance sheet |

---

## Need Help?

- **Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Authentication:** See [AUTH_LAYER_QUICKREF.md](AUTH_LAYER_QUICKREF.md)
- **Posting Service:** See [POSTING_SERVICE_QUICKREF.md](POSTING_SERVICE_QUICKREF.md)
- **Database Models:** See [ERD_diagram.md](ERD_diagram.md)

---

**Last Updated:** 2024-01-15  
**Version:** 1.0.0  
**Phase:** Phase 4 - Ledger & Account APIs
