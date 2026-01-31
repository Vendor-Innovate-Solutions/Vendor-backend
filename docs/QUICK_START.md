# Quick Start Guide - Role-Based Access Control

## 🎯 What This Is

A complete backend system for:
1. **User Role Selection** - Users choose their business role (MANUFACTURER, RETAILER, etc.)
2. **Company Management** - MANUFACTURER users create companies with automatic defaults
3. **Server-Side Routing** - Middleware enforces redirect rules based on user state
4. **Authorization** - Every API checks if user has access to company resources

---

## 🚀 Quick Start (5 minutes)

### Step 1: Understand the Roles

```
MANUFACTURER → Creates own company → OWNER role
RETAILER     → Joins companies    → Limited role
SUPPLIER     → Similar to retailer
DISTRIBUTOR  → Logistics partner
LOGISTICS    → Shipping partner
SERVICE_PROVIDER → Services
```

### Step 2: Understand the Flow

```
User Signs Up → Selects Role → Creates Company (MFGR only) → Uses App
```

### Step 3: Test the API

```bash
# 1. Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -d '{"username":"user@example.com","password":"pass"}'

# Copy the "access" token

# 2. Select Role
curl -X POST http://localhost:8000/api/users/select-role/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"role":"MANUFACTURER"}'

# 3. Check Context
curl http://localhost:8000/api/users/me/context/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# 4. Create Company (MFGR only)
curl -X POST http://localhost:8000/api/company/onboarding/create-company/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"MyCompany","code":"MC001","legal_name":"My Company Pvt Ltd","base_currency":"<currency-uuid>"}'
```

---

## 📚 Key Concepts

### 1. **User.selected_role** (Post-Signup Selection)
- User's chosen business identity
- Set once during onboarding via `/api/users/select-role/`
- Determines workflow and features
- Example: MANUFACTURER gets full ERP

### 2. **CompanyUser.role** (Per-Company Role)
- User's role within a specific company
- Can be different across companies
- Examples: OWNER in Company A, MANAGER in Company B
- Permission checks validate this

### 3. **Routing Rules** (Middleware Enforcement)
```
Rule 1: No role selected? → Redirect to /select-role
Rule 2: MANUFACTURER without company? → Redirect to /create-company
Rule 3: Multiple companies, none selected? → Redirect to /select-company
```

### 4. **Permission Checks** (Per Request)
```
Every company-scoped API verifies:
✓ User is authenticated
✓ CompanyUser exists for that company
✓ CompanyUser is active
✓ User's role has permission for action
```

---

## 📖 API Reference

### User APIs
```
POST   /api/users/select-role/           # Choose role
GET    /api/users/me/context/            # Get user context
GET    /api/users/me/                    # Get profile
```

### Company Creation (MANUFACTURER only)
```
POST   /api/company/onboarding/create-company/
```

### Company Operations
```
GET    /api/company/                     # List companies
GET    /api/company/{id}/                # Get details
GET    /api/company/{id}/setup-status/   # Setup progress
GET    /api/company/{id}/business-settings/
PUT    /api/company/{id}/business-settings/
GET    /api/company/{id}/features/
GET    /api/company/{id}/addresses/
POST   /api/company/{id}/addresses/
```

---

## 🔐 Authorization Examples

### Scenario 1: User Has No Access
```
GET /api/company/company-uuid-999/invoices/
Authorization: Bearer token_for_user_without_access

Response: 403 Forbidden
{
  "error": "You do not have access to this company"
}
```

### Scenario 2: User Has Access
```
GET /api/company/company-uuid-1/invoices/
Authorization: Bearer token_for_user_with_owner_role

Response: 200 OK
[invoices list...]
```

### Scenario 3: Insufficient Role
```
DELETE /api/company/company-uuid-1/users/user-id/
Authorization: Bearer token_for_user_with_manager_role

Response: 403 Forbidden
{
  "error": "You do not have permission to access this resource",
  "detail": "This action requires one of these roles: ADMIN, OWNER"
}
```

---

## 🎬 Frontend Implementation

### After Login:
```javascript
// Get user context to determine routing
const context = await fetch('/api/users/me/context/').then(r => r.json());

if (!context.role_selected) {
  navigate('/select-role');  // Show role selection
} else if (context.role === 'MANUFACTURER' && !context.has_company) {
  navigate('/create-company');  // Show company creation
} else if (context.companies.length > 1) {
  navigate('/select-company');  // Show company selector
} else {
  navigate('/dashboard');  // Proceed to app
}
```

### Making API Calls:
```javascript
// All company-scoped APIs need company ID
fetch(`/api/company/${companyId}/invoices/`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
```

---

## 📊 Database Schema

```
User
├─ id, email, password
├─ phone, phone_verified
├─ selected_role (MANUFACTURER|RETAILER|etc)
├─ active_company (currently selected)
├─ is_internal_user (ERP staff?)
└─ is_portal_user (retailer portal?)

CompanyUser (relationship)
├─ user_id (FK → User)
├─ company_id (FK → Company)
├─ role (OWNER|ADMIN|MANAGER|etc)
├─ is_default (primary company)
└─ is_active (can access?)

Company
├─ id, code, name, legal_name
├─ timezone, language
├─ base_currency
└─ is_active, is_deleted
```

---

## ❌ Common Mistakes (Avoid These!)

❌ **Not checking role_selected**: Frontend should call `/me/context` after login
❌ **Not including company_id**: All company APIs need company_id in URL
❌ **Forgetting authorization header**: Include JWT token in header
❌ **Using old CompanyUser without is_active check**: Always verify is_active=True
❌ **Hardcoding roles**: Use CompanyUser.role field, not user.selected_role for company access

---

## ✅ Common Patterns (Do These!)

✅ **After Login**: Call GET /users/me/context/ to determine routing
✅ **Before Company API**: Verify user has CompanyUser in context
✅ **In Headers**: Always include Authorization: Bearer token
✅ **Company Operations**: Include company_id in URL path
✅ **Error Handling**: Check HTTP status code (301=redirect, 403=forbidden, 401=auth)

---

## 🧪 Testing Checklist

- [ ] User can sign up
- [ ] User can select role
- [ ] Context endpoint returns correct data
- [ ] MANUFACTURER can create company
- [ ] RETAILER cannot create company (gets 403)
- [ ] Middleware redirects without role selected
- [ ] Middleware redirects without company (MFGR)
- [ ] User cannot access company they don't belong to (403)
- [ ] User can access company they own (200)
- [ ] Multi-company user can see all companies in context

---

## 📋 Troubleshooting

### "User not found" Error
- Check: JWT token is valid
- Check: User still exists in database
- Fix: Re-login to get fresh token

### "No access to this company" (403)
- Check: CompanyUser record exists
- Check: CompanyUser.is_active = True
- Check: Company ID is correct in URL
- Fix: Verify user was added to company

### "Role not selected" Redirect
- Expected: New users see this
- Fix: Have user call POST /select-role/
- Then: Call GET /me/context/ again

### "Role not permitted" (403)
- Check: User's CompanyUser.role in endpoint requirements
- Check: Correct authorization middleware applied
- Fix: Promote user to required role or use different endpoint

---

## 📞 Documentation Files

| File | Purpose |
|------|---------|
| API_DOCUMENTATION.md | Full endpoint reference |
| ROLE_BASED_ACCESS_CONTROL.md | Complete system guide |
| IMPLEMENTATION_SUMMARY.md | What was built |
| ARCHITECTURE_DIAGRAMS.md | Visual diagrams |
| VERIFICATION_CHECKLIST.md | Quality assurance checklist |

---

## 🎯 Next Steps

1. **Read**: Full documentation in docs/ folder
2. **Test**: Use curl examples to test APIs
3. **Implement Frontend**: Follow frontend guide in IMPLEMENTATION_SUMMARY
4. **Deploy**: Follow deployment checklist in VERIFICATION_CHECKLIST
5. **Monitor**: Watch authorization logs for issues

---

## 💡 Pro Tips

1. **Use context endpoint first**: Always call GET /me/context/ after login to guide routing
2. **Store company_id in state**: Keep active company ID in frontend state for API calls
3. **Check 307 responses**: Middleware returns 307 with redirect info, not 301
4. **Verify timestamps**: Check role_selected and company creation timestamps for debugging
5. **Use required_roles in views**: Specify `required_roles = ['ADMIN']` for permission enforcement

---

## 🔍 Under the Hood

### When User Makes Request:
```
1. JWT middleware validates token → attach user to request
2. Routing middleware checks if redirects needed → return 307 or pass through
3. View's permission_classes validate company access → 200 or 403
4. View processes request → return data
5. Serializer converts ORM → JSON → frontend
```

### When Authorization Fails:
```
Route 1: No token → 401 Unauthorized (JWT)
Route 2: No role selected → 307 Redirect to /select-role
Route 3: No company access → 403 Forbidden (permission)
Route 4: Wrong role in company → 403 Forbidden (permission)
```

---

## 📝 Code Examples

### Check if User Has Company Access
```python
def can_access_company(user, company_id):
    return user.company_memberships.filter(
        company_id=company_id,
        is_active=True
    ).exists()
```

### Get User's Role in Company
```python
def get_user_role_in_company(user, company_id):
    try:
        cu = user.company_memberships.get(company_id=company_id)
        return cu.role
    except CompanyUser.DoesNotExist:
        return None
```

### Decorator for Company-Scoped Views
```python
@permission_classes([CompanyUserPermission])
@required_roles = ['ADMIN', 'OWNER']
class MyView(APIView):
    def post(self, request, company_id):
        # request.company_user is attached by permission class
        # request.active_company_id = company_id
```

---

## 🎓 Learning Path

**Beginner**: Read this Quick Start first
**Intermediate**: Study IMPLEMENTATION_SUMMARY and API examples
**Advanced**: Review ARCHITECTURE_DIAGRAMS and permission logic
**Expert**: Study middleware code and authorization patterns

---

## 🚀 Ready to Go!

You now understand:
- ✅ Role selection system
- ✅ Company creation flow
- ✅ Server-side routing
- ✅ Authorization model
- ✅ API endpoints
- ✅ Common patterns

**Next**: Implement frontend and test the system!

---

**Questions?** Check the documentation files or review code comments.
**Issues?** See VERIFICATION_CHECKLIST.md troubleshooting section.

---

