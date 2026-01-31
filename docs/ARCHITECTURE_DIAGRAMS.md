# Architecture Diagrams & Quick Reference

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND APP                            │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐        │
│  │ Login    │    │ Role Select  │    │ Company Setup  │        │
│  │ Screen   │───▶│ Screen       │───▶│ Screen         │        │
│  └──────────┘    └──────────────┘    └────────────────┘        │
│       │                                                         │
│       └─ Stores JWT tokens, routes based on context            │
└─────────────────────────────────────────────────────────────────┘
          │
          │ HTTP Requests with Authorization header
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DJANGO BACKEND                               │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 1. Authentication Middleware                              │ │
│  │    - Validates JWT token                                  │ │
│  │    - Attaches User to request                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │                                      │
│                          ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 2. PostLoginRoutingMiddleware                              │ │
│  │    - Checks role selected                                 │ │
│  │    - Checks company existence                             │ │
│  │    - Checks company selection                             │ │
│  │    - Returns 307 redirect if needed                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                          │                                      │
│              ┌───────────┴───────────┐                          │
│              │                       │                          │
│              ▼                       ▼                          │
│         REDIRECT              CONTINUE                         │
│         (needs action)       (allowed)                         │
│              │                       │                         │
│              ▼                       ▼                          │
│         Return 307          ┌────────────────────────────────┐ │
│         + routing info      │ 3. Request View Dispatcher    │ │
│                             │    - Route to specific view   │ │
│                             │    - Pass parameters          │ │
│                             └────────────────────────────────┘ │
│                                       │                         │
│                                       ▼                         │
│                             ┌────────────────────────────────┐ │
│                             │ 4. Permission Classes         │ │
│                             │    - Check CompanyUser        │ │
│                             │    - Validate role            │ │
│                             │    - Attach to request        │ │
│                             └────────────────────────────────┘ │
│                                       │                         │
│                        ┌──────────────┴──────────────┐          │
│                        │                             │          │
│                        ▼                             ▼          │
│                    ALLOWED                      FORBIDDEN      │
│                    (200 OK)                      (403)         │
│                        │                             │          │
│                        ▼                             ▼          │
│             ┌──────────────────────┐      ┌───────────────────┐│
│             │ View Business Logic  │      │ Return Error JSON ││
│             │ - Query DB           │      └───────────────────┘│
│             │ - Format response    │                            │
│             └──────────────────────┘                            │
│                        │                                        │
│                        ▼                                        │
│             ┌──────────────────────┐                            │
│             │ Response Serializer  │                            │
│             │ - Convert ORM → JSON │                            │
│             └──────────────────────┘                            │
│                        │                                        │
└────────────────────────┼───────────────────────────────────────┘
                         │
                         ▼ Response
         ┌───────────────────────────────────┐
         │  JSON Response (200/301/403/etc)  │
         └───────────────────────────────────┘
                         │
                         ▼
              Frontend processes response
              and routes accordingly
```

---

## User Journey Flowchart

```
                        START
                         │
                         ▼
              ┌─────────────────────┐
              │ User Credentials    │
              │ (email, password)   │
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ POST /auth/login    │
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ JWT Token Received  │
              │ Store in localStorage
              └─────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ GET /me/context     │
              │ Check user state    │
              └─────────────────────┘
                         │
                    ┌────┴─────┬─────────────────┐
                    │           │                 │
                    ▼           ▼                 ▼
              role_selected  has_company    multiple_companies
              = false?        = false?          & no active?
                 YES             YES                 YES
                    │             │                   │
         ┌──────────┴─┐  ┌───────┴──┐    ┌──────────┴──┐
         │             │  │          │    │             │
         ▼             ▼  ▼          ▼    ▼             ▼
     Redirect     Redirect        Redirect        Check Company
    to Role       to Company      to Company      User Access
    Select       Creation        Selection
         │           │              │              │
         └───────┬───┴──────┬───────┴──────────────┘
                 │          │
                 NO         YES
                 │          │
                 ▼          ▼
          Proceed      Return 307
          Normal API   + redirect_to
          Call         (frontend
          (200 OK)      handles)
                 │          │
                 └────┬─────┘
                      │
                      ▼
               Dashboard Access ✅
```

---

## Database Schema

```
┌────────────────────────────────────────────────────────────────┐
│                          User                                   │
│  (core.auth.models.User extends AbstractUser)                 │
├────────────────────────────────────────────────────────────────┤
│  id (PK)                  │ Integer AutoField                  │
│  username                 │ CharField(150)                     │
│  email                    │ EmailField                         │
│  password                 │ CharField (hashed)                 │
│  phone                    │ CharField(20) [NEW]                │
│  phone_verified           │ BooleanField (default=False)       │
│  selected_role            │ CharField(50, choices) [NEW]       │
│  active_company (FK)      │ ForeignKey(Company, null=True)     │
│  is_internal_user         │ BooleanField (default=False)       │
│  is_portal_user           │ BooleanField (default=False)       │
│  created_at               │ DateTimeField (auto_now_add)       │
│  updated_at               │ DateTimeField (auto_now)           │
└────────────────────────────────────────────────────────────────┘
     ▲                                                    ▲
     │ (1)                                           (1) │
     │                                                   │
     │                                                   │
┌────┴───────────────────────────────────────────────────┴────────┐
│                      CompanyUser                               │
│  (apps.company.models.CompanyUser extends CompanyScopedModel)  │
├────────────────────────────────────────────────────────────────┤
│  id (PK, UUID)            │ UUIDField (primary_key)            │
│  company (FK)             │ ForeignKey(Company)                │
│  user (FK)                │ ForeignKey(User) ← related_name:   │
│                           │ company_memberships                │
│  role                     │ CharField(50, choices) [REQUIRED]  │
│                           │ Options:                           │
│                           │ - OWNER                            │
│                           │ - ADMIN                            │
│                           │ - MANAGER                          │
│                           │ - ACCOUNTANT                       │
│                           │ - STOCK_KEEPER                     │
│                           │ - SALES                            │
│                           │ - VIEWER                           │
│                           │ - EXTERNAL                         │
│  is_default               │ BooleanField (default=False)       │
│  is_active                │ BooleanField (default=True)        │
│  created_at               │ DateTimeField (auto_now_add)       │
│  updated_at               │ DateTimeField (auto_now)           │
│  Constraint               │ unique_together=(user, company)    │
└────────────────────────────────────────────────────────────────┘
                           (N)
                            │
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                        Company                                  │
│  (apps.company.models.Company extends BaseModel)               │
├────────────────────────────────────────────────────────────────┤
│  id (PK, UUID)            │ UUIDField                          │
│  code                     │ CharField(20, unique) [Business ID]
│  name                     │ CharField(255)                     │
│  legal_name               │ CharField(255)                     │
│  company_type             │ CharField(50, choices)             │
│  timezone                 │ CharField(50, default='UTC')       │
│  language                 │ CharField(20, default='en')        │
│  base_currency (FK)       │ ForeignKey(Currency)               │
│  is_active                │ BooleanField (default=True)        │
│  is_deleted               │ BooleanField (default=False)       │
│  created_at               │ DateTimeField (auto_now_add)       │
│  updated_at               │ DateTimeField (auto_now)           │
└────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Company Creation

```
┌────────────────────────────────────┐
│ Frontend Request                   │
│ POST /company/onboarding/          │
│         create-company/            │
│                                    │
│ {                                  │
│   "name": "ABC Mfg",              │
│   "code": "ABC001",               │
│   "legal_name": "...",            │
│   "base_currency": "uuid"         │
│ }                                  │
└────────────────────────────────────┘
              │
              │ Authenticated request
              │ (JWT token)
              ▼
┌────────────────────────────────────┐
│ ManufacturerCompanyCreationView    │
│ .post() method                     │
└────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│ Authorization Checks:              │
│ 1. Is authenticated? ✓             │
│ 2. selected_role ==                │
│    'MANUFACTURER'? ✓               │
│ 3. No existing company? ✓          │
│ 4. Fields present? ✓               │
└────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────────┐
│ Database Atomic Transaction                │
│ @transaction.atomic                        │
│                                            │
│ 1. Create Company                          │
│    ├─ code (unique check)                  │
│    ├─ name                                 │
│    ├─ legal_name                           │
│    ├─ company_type                         │
│    ├─ timezone                             │
│    ├─ language                             │
│    └─ base_currency (FK)                   │
│                                            │
│ 2. Create CompanyUser (OWNER)              │
│    ├─ user (FK)                            │
│    ├─ company (FK)                         │
│    ├─ role = 'OWNER'                       │
│    └─ is_default = True                    │
│                                            │
│ 3. Create CompanyFeature (defaults)        │
│    ├─ inventory_enabled = True             │
│    ├─ accounting_enabled = True            │
│    └─ ... other flags                      │
│                                            │
│ 4. Create FinancialYear (April-March)      │
│    ├─ start_date = April 1                 │
│    ├─ end_date = March 31                  │
│    └─ is_current = True                    │
│                                            │
│ 5. Update User                             │
│    └─ active_company = created_company     │
│                                            │
│ Success? Commit all. Fail? Rollback all.   │
└────────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│ Response: 201 Created              │
│                                    │
│ {                                  │
│   "message": "...",               │
│   "company": {...},               │
│   "company_user": {...},          │
│   "financial_year": {...}         │
│ }                                  │
└────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────┐
│ Frontend                           │
│ - Store company ID                 │
│ - Redirect to dashboard            │
│ - Include company_id in future     │
│   API requests                     │
└────────────────────────────────────┘
```

---

## Permission Check Flow

```
                  API Request
                     │
                     ▼
        ┌─────────────────────────┐
        │ permission_classes =    │
        │ [CompanyUserPermission] │
        └─────────────────────────┘
                     │
                     ▼
        ┌─────────────────────────┐
        │ Is authenticated?       │
        │ (JWT valid)             │
        └─────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
        YES               NO
         │                 │
         ▼                 ▼
   Continue         Return 401
                    Unauthorized
         │
         ▼
   ┌─────────────────────────┐
   │ Extract company_id from │
   │ URL kwargs or params    │
   └─────────────────────────┘
         │
         ▼
   ┌─────────────────────────┐
   │ Query: CompanyUser.     │
   │ objects.get(            │
   │   user=user,            │
   │   company_id=company_id,│
   │   is_active=True        │
   │ )                       │
   └─────────────────────────┘
         │
    ┌────┴─────┐
    │           │
    ▼           ▼
  FOUND      NOT FOUND
    │           │
    ▼           ▼
  Continue  Return 403
             "You do not have
              access to this
              company"
    │
    ▼
┌─────────────────────────┐
│ Check required_roles    │
│ (if specified in view)  │
└─────────────────────────┘
    │
    ├────────────────┬──────────┐
    │                │          │
    ▼                ▼          ▼
  MATCH         NOT MATCH    NOT SPECIFIED
    │                │          │
    ▼                ▼          ▼
Continue       Return 403   Continue
               "Insufficient  (allow all roles)
                permissions"
    │
    ▼
┌─────────────────────────┐
│ Attach to request:      │
│ - request.company_user  │
│ - request.active_       │
│   company_id            │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│ Execute View Logic      │
│ (200 OK response)       │
└─────────────────────────┘
```

---

## Role Hierarchy

```
                    BASE USER
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      INTERNAL     EXTERNAL      NEITHER
      USER TYPE    USER TYPE     (Portal)
          │            │            │
          │            │            │
      (Staff in    (Partners,   (Pending
       company)     retailers,   selection)
                    suppliers)
          │            │
          ├────────────┴────────────┬──────────┐
          │                         │          │
          ▼ CompanyUser.role        │          │
      [Internal Only]               ▼          ▼
                                EXTERNAL      none
      ├─ OWNER                 [Partner      (needs
      │  (full control)         only]         role
      │                                    selection)
      ├─ ADMIN
      │  (admin tasks)        └─ EXTERNAL
      │                          (partner
      ├─ MANAGER                  access)
      │  (management)
      │
      ├─ ACCOUNTANT
      │  (accounting ops)
      │
      ├─ STOCK_KEEPER
      │  (inventory ops)
      │
      ├─ SALES
      │  (sales ops)
      │
      └─ VIEWER
         (read-only)
```

---

## Routing Decision Tree

```
                    User Logs In
                         │
                         ▼
                  PostLoginMiddleware
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
        Is this a    Is this an
        protected    exempt
        endpoint?    endpoint?
                │        │
                YES      YES
                │        │
                ▼        ▼
           Continue   Skip routing
           routing    checks
           checks        │
                │        └────────┐
                │                 │
                ▼                 ▼
        ┌─────────────────────────────┐
        │ ROUTING RULE 1              │
        │ Check: user.selected_role   │
        │ is not None?                │
        └─────────────────────────────┘
                │
         ┌──────┴──────┐
         │             │
         ▼             ▼
        YES            NO
         │             │
         ▼             ▼
    Continue      Return 307
    to Rule 2     code='ROLE_NOT_SELECTED'
                  redirect='/select-role'
         │
         ▼
    ┌─────────────────────────────┐
    │ ROUTING RULE 2              │
    │ Check: If MANUFACTURER,     │
    │ has CompanyUser?            │
    └─────────────────────────────┘
         │
    ┌────┴─────┐
    │           │
    ▼           ▼
  MFGR      NOT MFGR
   │          │
   ▼          ▼
  Has?    Continue
   │      to Rule 3
  ┌┴┐
  │ │
  ▼ ▼
 YES NO
  │  │
  ▼  ▼
  C  R307: 'NO_COMPANY'
  o  redirect='/onboarding/company'
  n
  t  │
  i  ▼
  n
  u  Continue
  e  to Rule 3
         │
         ▼
    ┌─────────────────────────────┐
    │ ROUTING RULE 3              │
    │ Check: Multiple companies?  │
    │ Is active_company set?      │
    └─────────────────────────────┘
         │
    ┌────┴─────┐
    │           │
    ▼           ▼
  1+ Co      Multiple Co
   │          │
   ▼          ▼
 OK       Active set?
   │          │
   ▼      ┌───┴───┐
   │      │       │
   ▼      ▼       ▼
Proceed  YES     NO
 to API   │       │
   │     ▼       ▼
   │    Proceed  R307:
   │   to API    'SELECT_COMPANY'
   │      │      '/select-company'
   └──────┴──────┘
          │
          ▼
     Request View
     (Normal API call)
```

---

## Quick Reference Table

| Scenario | User State | Middleware Action | Frontend Response |
|----------|-----------|-------------------|------------------|
| New user, logged in | `selected_role=NULL` | Return 307 | Navigate to /select-role |
| Role selected, no co | `selected_role='MFGR'`, no co | Return 307 | Navigate to /create-company |
| Multi-company, no active | 2+ cos, `active_company=NULL` | Return 307 | Navigate to /select-company |
| All set | co selected, role ok | Pass through | Execute API normally |
| Public endpoint | Any | Skip checks | Execute API |

---

## Stubs for Future Implementation

Currently stubbed endpoints that return 501 Not Implemented:

```python
# 1. Company Invite System
POST /api/companies/{id}/invite/
# Creates invitation token
# Sends email to external user

# 2. Invite Acceptance  
POST /api/invites/{token}/accept/
# Validates token
# Creates CompanyUser(role=EXTERNAL)

# 3. External User Profile
POST /api/partner/profile/
# Creates independent external profile
# No company ownership required
```

---

End of Architecture & Reference Guide
