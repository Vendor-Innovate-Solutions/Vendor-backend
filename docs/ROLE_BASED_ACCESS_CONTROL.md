# Role-Based Access Control & Post-Login Routing Implementation

## Summary

Implemented complete role-based access control system with multi-phase onboarding, server-side routing enforcement, and company-scoped authorization.

---

## What Was Implemented

### 1. User Model Enhancement
- Added `UserRole` enum with business roles: MANUFACTURER, RETAILER, SUPPLIER, DISTRIBUTOR, LOGISTICS, SERVICE_PROVIDER
- Added `selected_role` field to User model (nullable, stores user's chosen role)
- Created migration: `core/auth/migrations/0002_add_selected_role.py`

### 2. Onboarding Flow APIs

#### A. Role Selection
```
POST /api/users/select-role/
```
- Authenticated users select their business role
- Sets `user.selected_role` and marks `is_internal_user=True`

#### B. Context Resolution
```
GET /api/users/me/context/
```
Returns:
- User's selected role
- All companies user belongs to (CompanyUser relationships)
- Default company
- Company-level roles
- Flags for routing decisions

#### C. Manufacturer Company Creation
```
POST /api/company/onboarding/create-company/
```
- **AUTHORIZATION**: Only `selected_role == 'MANUFACTURER'` and `no existing company`
- **ATOMIC TRANSACTION** creates:
  - Company record
  - CompanyUser(role=OWNER)
  - CompanyFeature with default flags
  - FinancialYear for current fiscal year
  - Sets user.active_company

### 3. Post-Login Routing Middleware
**File**: `core/middleware/routing.py` → `PostLoginRoutingMiddleware`

Enforces server-side routing rules:

```
Rule 1: If user.selected_role == NULL
        → Return redirect to /select-role
        
Rule 2: If user.selected_role == 'MANUFACTURER' AND no company
        → Return redirect to /onboarding/company
        
Rule 3: If user has multiple companies AND active_company == NULL
        → Return redirect to /select-company
```

**Response Format**:
```json
{
  "error": "REDIRECT_REQUIRED",
  "status_code": 307,
  "code": "ROLE_NOT_SELECTED",
  "message": "Please select your role to continue",
  "redirect_to": "/select-role"
}
```

**Exempt Endpoints** (don't trigger redirects):
- /auth/login
- /auth/logout
- /auth/signup
- /auth/select-role
- /users/me/context
- /invites/*
- /partner/profile
- /health
- /admin

### 4. Authorization & Permissions System
**File**: `core/permissions/company.py`

Created reusable permission classes:

#### `CompanyUserPermission`
- Checks if user has active CompanyUser for company
- Validates user role against required_roles list
- Attaches company_user to request for view access

#### `IsCompanyOwner`
- Only users with CompanyUser.role == 'OWNER'

#### `IsCompanyAdmin`  
- Users with CompanyUser.role in ['OWNER', 'ADMIN']

#### `IsInternalUser`
- Users with is_internal_user=True (ERP staff)

#### `IsExternalUser`
- Users with is_portal_user=True (retailers/suppliers)

#### Usage in Views:
```python
class MyCompanyView(APIView):
    permission_classes = [IsAuthenticated, CompanyUserPermission]
    required_roles = ['ADMIN', 'OWNER']
    
    def get(self, request, company_id):
        # request.company_user is auto-attached by permission class
        # request.active_company_id is company being accessed
```

### 5. API Endpoints Created

#### User APIs (`apps/users/api.py`):
- `RoleSelectionView` → POST /api/users/select-role/
- `UserContextView` → GET /api/users/me/context/

#### Company Onboarding APIs (`apps/company/api/views_onboarding.py`):
- `ManufacturerCompanyCreationView` → POST /api/company/onboarding/create-company/
- `CompanyInviteView` → POST /api/companies/{id}/invite (stub)
- `InviteAcceptView` → POST /api/invites/{token}/accept (stub)
- `ExternalUserProfileView` → POST /api/partner/profile (stub)

### 6. Serializers
**File**: `apps/users/serializers.py`

New serializers:
- `RoleSelectionSerializer` - Input validation for role selection
- `UserContextSerializer` - Complete user context response with company information

### 7. Middleware Registration
**File**: `main/settings.py`

Added middleware to MIDDLEWARE list:
```python
'core.middleware.routing.PostLoginRoutingMiddleware',
```
Positioned after AuthenticationMiddleware to access authenticated user.

### 8. URL Configuration Updates

#### Users URLs (`apps/users/urls.py`):
```python
path('select-role/', RoleSelectionView.as_view(), name='select_role'),
path('me/context/', UserContextView.as_view(), name='user_context'),
```

#### Company URLs (`apps/company/api/urls.py`):
```python
path('onboarding/create-company/', ManufacturerCompanyCreationView.as_view()),
path('<uuid:company_id>/invite/', CompanyInviteView.as_view()),
```

---

## Frontend Implementation Guide

### Complete Login & Redirect Flow

```javascript
// 1. User submits credentials
const response = await fetch('/api/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username, password })
});

const { access, refresh } = await response.json();
localStorage.setItem('access_token', access);

// 2. Call context endpoint to determine routing
const context = await fetch('/api/users/me/context/', {
  headers: { 'Authorization': `Bearer ${access}` }
}).then(r => r.json());

// 3. Implement routing logic
if (!context.role_selected) {
  // Redirect to role selection
  navigate('/select-role');
  return;
}

if (context.role === 'MANUFACTURER' && !context.has_company) {
  // Redirect to company creation
  navigate('/onboarding/company');
  return;
}

if (context.companies.length > 1 && !context.default_company_id) {
  // Redirect to company selection
  navigate('/select-company');
  return;
}

// 4. All checks passed, redirect to dashboard
navigate('/dashboard');
```

### API Request with Company Context

All company-scoped API requests should include company_id in URL:

```javascript
// Example: Get company business settings
const response = await fetch(`/api/company/${companyId}/business-settings/`, {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

// If user doesn't have access, gets 403:
// {
//   "error": "You do not have access to this company"
// }
```

### Handling Redirect Responses

```javascript
// If you get 307 status with redirect info:
const response = await fetch('/api/accounting/invoices/', {
  headers: { 'Authorization': `Bearer ${token}` }
});

if (response.status === 307) {
  const data = await response.json();
  console.log(data.code); // 'ROLE_NOT_SELECTED', 'NO_COMPANY', 'SELECT_COMPANY'
  navigate(data.redirect_to);
  return;
}
```

---

## Database Schema Changes

### User Model
```sql
ALTER TABLE auth_user ADD COLUMN selected_role VARCHAR(50) NULL;
-- Values: MANUFACTURER, RETAILER, SUPPLIER, DISTRIBUTOR, LOGISTICS, SERVICE_PROVIDER
```

### CompanyUser Relationships
- User → CompanyUser (FK, one-to-many via company_memberships)
- CompanyUser.role (choices: ADMIN, MANAGER, ACCOUNTANT, STOCK_KEEPER, SALES, VIEWER, OWNER, EXTERNAL)
- CompanyUser.is_default (boolean, for selecting active company)

---

## Key Design Decisions

### 1. Role vs Company Role
- **User.selected_role**: User's business identity (MANUFACTURER, RETAILER, etc.)
- **CompanyUser.role**: User's role within a specific company (OWNER, ADMIN, MANAGER, etc.)

### 2. Atomic Company Creation
Manufacturing company creation is atomic to ensure:
- Company, CompanyUser, CompanyFeature, FinancialYear all created together
- No orphaned records if creation fails mid-transaction
- User.active_company automatically set after creation

### 3. Server-Side Routing Enforcement
Routing is enforced at middleware level (not just frontend) to:
- Prevent users from bypassing checks
- Ensure consistent behavior across all API consumers
- Make redirect information part of standard API response

### 4. Nullable Relationships for External Users
CompanyUser relationships allow for independent external profiles:
- Retailers can create profiles without company ownership
- Suppliers can exist without being assigned to specific company
- Future external user API (POST /partner/profile) creates independent identity

---

## Testing the Implementation

### 1. Test Role Selection
```bash
curl -X POST http://localhost:8000/api/users/select-role/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"role": "MANUFACTURER"}'
```

### 2. Test Context Resolution
```bash
curl -X GET http://localhost:8000/api/users/me/context/ \
  -H "Authorization: Bearer <token>"
```

### 3. Test Manufacturer Company Creation
```bash
curl -X POST http://localhost:8000/api/company/onboarding/create-company/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ABC Manufacturing",
    "code": "ABC001",
    "legal_name": "ABC Manufacturing Pvt Ltd",
    "base_currency": "<currency-uuid>"
  }'
```

### 4. Test Redirect Middleware
Try accessing a protected endpoint before role selection:
```bash
curl -X GET http://localhost:8000/api/accounting/invoices/ \
  -H "Authorization: Bearer <token>"
# Should return 307 with redirect to /select-role
```

---

## Files Created/Modified

### Created Files:
- `apps/company/api/views_onboarding.py` - Onboarding views
- `core/middleware/routing.py` - Post-login routing middleware
- `core/permissions/company.py` - Authorization permission classes
- `core/auth/migrations/0002_add_selected_role.py` - Database migration

### Modified Files:
- `core/auth/models.py` - Added UserRole enum and selected_role field
- `apps/users/api.py` - Added RoleSelectionView, UserContextView
- `apps/users/serializers.py` - Added RoleSelectionSerializer, UserContextSerializer
- `apps/users/urls.py` - Added new URL patterns
- `apps/company/api/urls.py` - Added onboarding routes
- `main/settings.py` - Registered routing middleware
- `docs/API_DOCUMENTATION.md` - Added comprehensive documentation

---

## Next Steps / Future Enhancements

1. **Invite System** (POST /companies/{id}/invite, POST /invites/{token}/accept)
   - Send email invites to external users
   - Token-based invite acceptance
   - Auto-create CompanyUser with specified role

2. **External User Profile** (POST /partner/profile)
   - Allow retailers/suppliers to create standalone profiles
   - No company required initially
   - Can be invited to companies later

3. **Company Selection** (POST /select-company)
   - Allow users with multiple companies to switch active company
   - Updates user.active_company
   - Affects subsequent API calls

4. **Role-Based Feature Flags**
   - Different modules available based on user role
   - MANUFACTURER: Full ERP access
   - RETAILER: Limited to sales/inventory
   - SUPPLIER: Limited to supplier portal

5. **Audit Logging**
   - Log all role changes
   - Log all company access changes
   - Log all authorization denials

---

## Troubleshooting

### Issue: Getting "REDIRECT_REQUIRED" on every request
- Check: User.selected_role is set correctly
- Check: CompanyUser exists and is_active=True
- Check: active_company is set for users with multiple companies

### Issue: 403 "No access to this company"
- Check: CompanyUser record exists for user + company
- Check: CompanyUser.is_active=True
- Check: User sending company_id in URL parameter

### Issue: Company creation atomic transaction failing
- Check: Currency UUID is valid
- Check: Company code is unique
- Check: Financial year dates are valid (start < end)
- Migration 0002_add_selected_role must be applied

---

## Dependencies

- Django 5.1+
- djangorestframework 3.14+
- djangorestframework-simplejwt 5.3+
- PostgreSQL (for atomic transactions)

---

## Security Notes

1. **Role Immutability**: Once MANUFACTURER creates company, cannot change role to RETAILER
   - Use admin interface to modify user.selected_role
   
2. **Middleware Protection**: Routing enforcement happens at middleware level
   - Prevents direct API access to protected endpoints
   
3. **Company User Validation**: Every API checks active CompanyUser
   - No company = no access to company-scoped resources
   
4. **Token-Based Invites** (future): Use short-lived tokens for user invites
   - Prevent invite link misuse

---

## API Cheat Sheet

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/auth/login` | POST | User login | No |
| `/users/register` | POST | Create account | No |
| `/users/select-role` | POST | Choose business role | Yes |
| `/users/me/context` | GET | Get user context (routing) | Yes |
| `/company/onboarding/create-company` | POST | Create company (MFGR) | Yes |
| `/company/{id}/business-settings` | GET/PUT | Configure company | Yes |
| `/company/{id}/addresses` | GET/POST | Manage addresses | Yes |
| `/company/{id}/setup-status` | GET | Check setup progress | Yes |
| `/company/{id}/invite` | POST | Invite external user | Yes |

