# Authentication + Authorization Layer - Quick Reference

## 🔐 Overview

Complete JWT-based authentication with role-based access control, multi-company support, and service-layer decorators.

---

## 📍 API Endpoints

### Login
```http
POST /auth/login/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJh...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
}
```

**Token includes custom claims:**
- `username`, `email`
- `active_company` → `{id, name, code}`
- `roles` → `['ADMIN', 'ACCOUNTANT']`
- `available_companies` → list of companies user can access
- `is_internal_user`, `is_portal_user`
- `retailer` → party info (for portal users)

### Refresh Token
```http
POST /auth/refresh/
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJh..."
}
```

### Logout (Blacklist Token)
```http
POST /auth/logout/
Authorization: Bearer <access_token>

{
  "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
}
```

### Get Current User
```http
GET /auth/me/
Authorization: Bearer <access_token>

Response:
{
  "id": "123",
  "username": "john.doe",
  "email": "john@example.com",
  "is_internal_user": true,
  "active_company": { "id": "456", "name": "ABC Corp" },
  "roles": ["ADMIN"],
  "available_companies": [...]
}
```

### Switch Active Company
```http
POST /auth/switch-company/
Authorization: Bearer <access_token>

{
  "company_id": "123e4567-e89b-12d3-a456-426614174000"
}

Response:
{
  "detail": "Company switched successfully",
  "active_company": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "XYZ Ltd",
    "code": "XYZ"
  }
}
```

---

## 🔒 DRF Permission Classes

### HasCompanyContext
Requires `request.company` to be set (from middleware).

```python
from core.drf import CompanyScopedViewSet, HasCompanyContext

class InvoiceViewSet(CompanyScopedViewSet):
    permission_classes = [HasCompanyContext]
    queryset = Invoice.objects.all()
```

### RolePermission
Requires user to have specific role(s).

```python
from rest_framework.views import APIView
from core.drf import RolePermission

class VoucherPostingView(APIView):
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def post(self, request):
        # Only ADMIN or ACCOUNTANT can execute
        ...
```

### IsInternalUser
Blocks retailer/portal users.

```python
from core.drf import IsInternalUser

class CompanySettingsView(APIView):
    permission_classes = [IsInternalUser]
```

### IsRetailerUser
Allows only retailer/portal users.

```python
from core.drf import IsRetailerUser

class OrderHistoryView(APIView):
    permission_classes = [IsRetailerUser]
```

---

## 🛡️ Service-Layer Decorators

### @role_required
Enforce role check in service functions.

```python
from core.utils.decorators import role_required

@role_required(['ADMIN'])
def delete_company(user, company_id):
    # Only ADMIN can delete companies
    ...

@role_required(['ADMIN', 'ACCOUNTANT'])
def post_voucher(user, voucher_id):
    # ADMIN or ACCOUNTANT can post vouchers
    ...
```

### @company_required
Ensure user has active company.

```python
from core.utils.decorators import company_required

@company_required
def create_invoice(user, invoice_data):
    company = user.active_company  # Guaranteed to exist
    invoice = Invoice.objects.create(company=company, ...)
```

### @internal_user_only
Restrict to internal ERP users.

```python
from core.utils.decorators import internal_user_only

@internal_user_only
def manage_system_settings(user):
    # Only internal users can access
    ...
```

### @retailer_user_only
Restrict to retailer/portal users.

```python
from core.utils.decorators import retailer_user_only

@retailer_user_only
def place_order(user, order_data):
    # Only retailers can place orders
    ...
```

### @combined_role_and_company
Combine role + company checks.

```python
from core.utils.decorators import combined_role_and_company

@combined_role_and_company(['ADMIN', 'ACCOUNTANT'])
def reverse_voucher(user, voucher_id, reason):
    # Must have role AND active company
    company = user.active_company
    ...
```

---

## 🔄 Auto-Assign Company (Signals)

**What happens:**
1. When `CompanyUser` is created → user gets `active_company` automatically
2. When `RetailerCompanyAccess` is approved → retailer gets `active_company`
3. New users never have `None` company (if they have access)

**No manual setup needed** - signals handle it automatically.

---

## 📋 User Roles

Defined in `apps.company.models.UserRole`:

```python
ADMIN        # Full system access
MANAGER      # Operational management
ACCOUNTANT   # Financial operations
STOCK_KEEPER # Inventory management
SALES        # Sales operations
VIEWER       # Read-only access
```

---

## 🧪 Testing

```bash
# Run authentication tests
python manage.py test tests.test_auth_layer

# Run company scope tests
python manage.py test tests.test_company_scope
```

---

## 🎯 Common Patterns

### Pattern 1: Protected API View
```python
from rest_framework.views import APIView
from core.drf import RolePermission, HasCompanyContext

class ProtectedView(APIView):
    permission_classes = [HasCompanyContext, RolePermission.require(['ADMIN'])]
    
    def post(self, request):
        # Guaranteed: request.company exists, user is ADMIN
        ...
```

### Pattern 2: Service with Role Check
```python
from core.utils.decorators import combined_role_and_company

@combined_role_and_company(['ACCOUNTANT', 'ADMIN'])
def process_payment(user, payment_data):
    company = user.active_company
    # Create payment in company context
    ...
```

### Pattern 3: Multi-Company User Flow
```python
# 1. Login
POST /auth/login/ → get access + refresh tokens

# 2. Check available companies
GET /auth/me/ → see available_companies list

# 3. Switch company
POST /auth/switch-company/ → change active_company

# 4. Make requests with new company context
GET /api/invoices/ (automatically filtered by new company)
```

---

## ⚙️ Configuration

Already configured in `config/settings/base.py`:

```python
# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    ...
}

# DRF Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}
```

---

## 🔍 Verification Checklist

| Scenario | Expected Behavior |
|----------|------------------|
| Login with valid credentials | Returns access + refresh tokens |
| Token includes roles | ✅ Yes - check JWT claims |
| Token includes active_company | ✅ Yes - check JWT claims |
| User with no company | Auto-assigned when CompanyUser created |
| Switch to valid company | Updates user.active_company |
| Switch to unauthorized company | Returns 403 Forbidden |
| Admin-only endpoint + VIEWER role | Blocked (403) |
| Service with @role_required + wrong role | Raises PermissionDenied |
| Multi-company user | Can switch between companies |

---

## 📚 Related Files

- **Settings:** `config/settings/base.py`
- **Serializers:** `core/auth/serializers.py`
- **Views:** `core/auth/views.py`
- **Permissions:** `core/drf/permissions.py`
- **Decorators:** `core/utils/decorators.py`
- **Signals:** `core/auth/signals.py`
- **Tests:** `tests/test_auth_layer.py`, `tests/test_company_scope.py`

---

**Status:** ✅ Fully Implemented & Ready for Testing
