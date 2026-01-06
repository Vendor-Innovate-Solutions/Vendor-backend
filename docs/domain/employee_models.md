# Employee Models Architecture

**Last Updated**: December 26, 2025  
**Status**: 🟢 ACTIVE DESIGN PATTERN

---

## Overview

The Vendor ERP maintains **two distinct Employee models** for different purposes:

1. **`users.Employee`** - User Identity & Access Control
2. **`hr.Employee`** - HR/Payroll Management

This separation enables clean separation between authentication/authorization and HR operations.

---

## Model Responsibilities

### 🔐 users.Employee - Identity & Access

**Purpose**: Links system users to companies for authentication and RBAC

**Location**: `apps/users/models.py`

**Primary Use**: User identity, login, and company access

**Responsibilities**:
- ✅ User-to-Company relationship
- ✅ System login authentication
- ✅ Role-based access control (via CompanyUser)
- ✅ Multi-company context switching
- ✅ Portal vs internal user distinction

**Key Fields**:
```python
class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)  # Simple ID
    company = models.ForeignKey('company.Company', ...)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
        null=True,
        blank=True
    )
    contact = models.CharField(max_length=20)
    designation = models.CharField(max_length=100)
    department = models.CharField(max_length=100)  # Simple string
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField(null=True, blank=True)
```

**Used By**:
- 🔐 Authentication middleware
- 👤 User profile screens
- 🏢 Company switching logic
- 📋 Simple employee dropdowns
- 🔑 Access control checks

**Characteristics**:
- ✅ Lightweight
- ✅ Auto-increment ID (legacy)
- ✅ Simple fields
- ✅ Fast lookups
- ✅ Not multi-tenant (has explicit company FK)

---

### 👔 hr.Employee - HR & Payroll

**Purpose**: Complete HR personnel management with payroll integration

**Location**: `apps/hr/models.py`

**Primary Use**: HR operations, payroll, attendance, performance

**Responsibilities**:
- ✅ Complete employee lifecycle (hiring → exit)
- ✅ Payroll processing
- ✅ Salary structure management
- ✅ Department hierarchy
- ✅ Attendance tracking
- ✅ Leave management
- ✅ Performance reviews
- ✅ Statutory compliance (PF, ESI, etc.)
- ✅ Employee ledger for accounting

**Key Fields**:
```python
class Employee(CompanyScopedModel):  # UUID-based
    employee_code = models.CharField(max_length=50, db_index=True)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='employee_profiles'  # Note: plural
    )
    
    # Personal details
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    
    # Employment details
    department = models.ForeignKey(
        Department,                    # Structured hierarchy
        on_delete=models.SET_NULL,
        null=True,
        related_name='employees'
    )
    designation = models.CharField(max_length=100)
    date_of_joining = models.DateField()
    date_of_exit = models.DateField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Related models:
    # - EmployeeLedger (accounting integration)
    # - EmployeePayStructure (salary components)
    # - PayrollRun entries
    # - Attendance records
```

**Used By**:
- 💰 Payroll processing
- 📊 HR reports
- 🏢 Department management
- 📅 Attendance systems
- 💳 Salary disbursement
- 📄 Employment records
- 🔗 Accounting (Employee Ledger)
- 📋 Leave management

**Characteristics**:
- ✅ Full-featured HR model
- ✅ UUID primary key (CompanyScopedModel)
- ✅ Multi-company safe
- ✅ Rich relationships (Department, Payroll, Ledger)
- ✅ Accounting integration

---

## Relationship Between Models

### Current Architecture

```
┌─────────────────────────────────────────────────┐
│  AUTHENTICATION LAYER                            │
├─────────────────────────────────────────────────┤
│                                                  │
│  core_auth.User (Django User)                    │
│  ├── username, email, password                   │
│  ├── is_internal_user                            │
│  ├── is_portal_user                              │
│  └── active_company                              │
│      │                                            │
│      ├──────────────────┬────────────────────┐  │
│      │                  │                     │  │
│      ↓                  ↓                     ↓  │
│                                                  │
├──────────────────┬──────────────────────────────┤
│  IDENTITY        │  HR/PAYROLL                   │
├──────────────────┼──────────────────────────────┤
│                  │                               │
│  users.Employee  │  hr.Employee                  │
│  (OneToOne)      │  (ForeignKey, nullable)       │
│  ├── employee_id │  ├── employee_code            │
│  ├── company     │  ├── company (inherited)      │
│  ├── contact     │  ├── first_name, last_name    │
│  ├── designation │  ├── department (FK)          │
│  └── is_active   │  ├── date_of_joining          │
│                  │  │                             │
│  Related:        │  Related:                     │
│  - CompanyUser   │  - EmployeeLedger             │
│    (role mapping)│  - EmployeePayStructure       │
│                  │  - PayrollRun                 │
│                  │  - Department                 │
│                  │                               │
└──────────────────┴──────────────────────────────┘
```

### User Scenarios

#### Scenario A: Internal ERP Staff (No HR Record)

**Example**: System Administrator, IT Support

```python
# Create User
user = User.objects.create_user(
    username="admin",
    is_internal_user=True
)

# Create Identity (users.Employee)
users.Employee.objects.create(
    user=user,
    company=company,
    contact="+91-9876543210",
    designation="System Administrator"
)

# Create Company Access
CompanyUser.objects.create(
    user=user,
    company=company,
    role='ADMIN'
)

# NO hr.Employee created
# Result: Can login, access ERP, but not in payroll
```

**Use Case**: 
- ✅ Login to ERP
- ✅ Access based on role
- ✅ Company switching
- ❌ Not on payroll
- ❌ No salary processing
- ❌ No attendance tracking

---

#### Scenario B: Payroll Employee (With HR Record)

**Example**: Accountant, Warehouse Manager

```python
# Create User
user = User.objects.create_user(
    username="john.doe",
    is_internal_user=True
)

# Create Identity (users.Employee)
users.Employee.objects.create(
    user=user,
    company=company,
    contact="+91-9876543210",
    designation="Accountant"
)

# Create HR Record (hr.Employee)
hr_employee = hr.Employee.objects.create(
    user=user,  # Link to same user
    company=company,
    employee_code="EMP-001",
    first_name="John",
    last_name="Doe",
    department=accounts_dept,
    date_of_joining="2024-01-15"
)

# Create Accounting Link
EmployeeLedger.objects.create(
    employee=hr_employee,
    ledger=employee_ledger
)

# Create Pay Structure
EmployeePayStructure.objects.create(
    employee=hr_employee,
    pay_head=basic_salary,
    amount=50000
)
```

**Use Case**:
- ✅ Login to ERP (via users.Employee)
- ✅ Access based on role
- ✅ On payroll (via hr.Employee)
- ✅ Salary processing
- ✅ Attendance tracking
- ✅ Leave management

---

#### Scenario C: HR Employee Without Login

**Example**: Factory Worker, Security Guard

```python
# NO User account created

# Only HR Record (hr.Employee)
hr_employee = hr.Employee.objects.create(
    user=None,  # No login access
    company=company,
    employee_code="EMP-102",
    first_name="Ramesh",
    last_name="Kumar",
    department=production_dept,
    date_of_joining="2023-06-01"
)

# Create Pay Structure
EmployeePayStructure.objects.create(
    employee=hr_employee,
    pay_head=basic_salary,
    amount=18000
)
```

**Use Case**:
- ❌ Cannot login to ERP
- ✅ On payroll
- ✅ Biometric attendance (using employee_code)
- ✅ Salary processing
- ✅ Leave tracking
- ✅ Provident fund, ESI

---

## Comparison Matrix

| Feature | users.Employee | hr.Employee |
|---------|----------------|-------------|
| **Purpose** | Identity/Login | HR Management |
| **Primary Key** | Auto-increment ID | UUID (inherited) |
| **Base Model** | models.Model | CompanyScopedModel |
| **User Link** | OneToOne (required) | ForeignKey (nullable) |
| **Multi-Company** | Explicit FK | Inherited (tenant-safe) |
| **Department** | CharField (simple) | FK to Department hierarchy |
| **Payroll** | ❌ No | ✅ Yes |
| **Accounting Link** | ❌ No | ✅ EmployeeLedger |
| **Pay Structure** | ❌ No | ✅ Yes |
| **Attendance** | ❌ No | ✅ Yes |
| **Leave Management** | ❌ No | ✅ Yes |
| **Biometric ID** | ❌ No | ✅ employee_code |
| **Related Name** | `user.employee_profile` | `user.employee_profiles` |
| **API Usage** | Auth, profile, RBAC | Payroll, HR reports |

---

## API Design

### Employee Profile API (Identity)

**Endpoint**: `GET /api/users/me/`

**Response** (uses `users.Employee`):
```json
{
  "id": 123,
  "username": "john.doe",
  "email": "john@company.com",
  "employee": {
    "employee_id": 45,
    "company": {
      "id": "uuid...",
      "name": "Acme Corp"
    },
    "designation": "Accountant",
    "contact": "+91-9876543210",
    "is_active": true
  },
  "companies": [
    {
      "company": "Acme Corp",
      "role": "ACCOUNTANT"
    }
  ]
}
```

---

### HR Employee API (Payroll)

**Endpoint**: `GET /api/hr/employees/`

**Response** (uses `hr.Employee`):
```json
{
  "results": [
    {
      "id": "uuid-123",
      "employee_code": "EMP-001",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@company.com",
      "phone": "+91-9876543210",
      "department": {
        "code": "ACC",
        "name": "Accounts"
      },
      "designation": "Senior Accountant",
      "date_of_joining": "2024-01-15",
      "is_active": true,
      "has_user_access": true,
      "salary_structure": {
        "basic": 50000,
        "hra": 20000,
        "total": 70000
      }
    }
  ]
}
```

---

## When to Create Which Model

### Decision Tree

```
New Person Added
     │
     ├─→ Needs ERP Login?
     │   ├─→ YES: Create User + users.Employee + CompanyUser
     │   └─→ NO: Skip user creation
     │
     └─→ On Payroll?
         ├─→ YES: Create hr.Employee
         │   ├─→ Link to User if exists
         │   └─→ Create EmployeeLedger, PayStructure
         └─→ NO: Skip hr.Employee
```

### Examples

| Person Type | User | users.Employee | hr.Employee | CompanyUser |
|-------------|------|----------------|-------------|-------------|
| System Admin | ✅ | ✅ | ❌ | ✅ ADMIN |
| Manager (on payroll) | ✅ | ✅ | ✅ | ✅ MANAGER |
| Accountant | ✅ | ✅ | ✅ | ✅ ACCOUNTANT |
| Factory Worker | ❌ | ❌ | ✅ | ❌ |
| Consultant (no payroll) | ✅ | ✅ | ❌ | ✅ VIEWER |
| Security Guard | ❌ | ❌ | ✅ | ❌ |

---

## Migration Considerations

### Current State Issues

1. **users.Employee uses auto-increment ID**
   - Inconsistent with rest of system (UUID-based)
   - ✅ **Keep as-is** - It's a simple identity model, doesn't need UUID

2. **No automatic linking between models**
   - Creating hr.Employee doesn't auto-create users.Employee
   - ✅ **Intentional** - Not all HR employees need login

3. **Separate related_names**
   - `user.employee_profile` (users.Employee)
   - `user.employee_profiles` (hr.Employee, plural)
   - ✅ **Correct** - No conflict, clear distinction

---

## Best Practices

### ✅ DO

1. **Create users.Employee for all login users**
   ```python
   if user.is_internal_user:
       users.Employee.objects.get_or_create(
           user=user,
           defaults={'company': company}
       )
   ```

2. **Create hr.Employee for payroll staff**
   ```python
   hr.Employee.objects.create(
       user=user,  # Can be None
       employee_code=generate_code(),
       company=company,
       ...
   )
   ```

3. **Link both to same User when needed**
   ```python
   user = User.objects.create(...)
   users.Employee.objects.create(user=user, ...)
   hr.Employee.objects.create(user=user, ...)
   # Both can access via user.employee_profile and user.employee_profiles
   ```

4. **Use appropriate model in queries**
   ```python
   # For authentication/RBAC:
   employee = request.user.employee_profile  # users.Employee
   
   # For payroll:
   hr_employees = hr.Employee.objects.filter(
       company=company,
       is_active=True
   )
   ```

---

### ❌ DON'T

1. **Don't use users.Employee for payroll**
   ```python
   # ❌ WRONG
   users.Employee.objects.filter(company=company)  # For payroll report
   
   # ✅ CORRECT
   hr.Employee.objects.filter(company=company)
   ```

2. **Don't assume every User has hr.Employee**
   ```python
   # ❌ WRONG
   hr_employee = request.user.employee_profiles  # May not exist
   
   # ✅ CORRECT
   hr_employee = getattr(request.user, 'employee_profiles', None)
   if hr_employee:
       process_payroll(hr_employee)
   ```

3. **Don't create duplicate records**
   ```python
   # ❌ WRONG - Creating both unnecessarily
   users.Employee.objects.create(user=user, ...)
   hr.Employee.objects.create(user=user, ...)
   
   # ✅ CORRECT - Create based on need
   if needs_login:
       users.Employee.objects.create(...)
   if on_payroll:
       hr.Employee.objects.create(...)
   ```

---

## Future Enhancements

### Optional: Link HR Employee to Login User

Currently, `hr.Employee.user` is nullable. Consider making it required for staff:

```python
class Employee(CompanyScopedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,  # Allow None for workers without login
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hr_employee'
    )
    
    # Add flag
    requires_login = models.BooleanField(
        default=False,
        help_text="Employee requires system login access"
    )
    
    def save(self, *args, **kwargs):
        if self.requires_login and not self.user:
            raise ValidationError("Login required but no user assigned")
        super().save(*args, **kwargs)
```

---

## Conclusion

**Recommended Pattern**: **Keep Both Models - Clear Separation**

```
User (Auth) → users.Employee (Identity) → CompanyUser (Role)
           → hr.Employee (HR) → Payroll, Attendance, Ledger
```

**Benefits**:
1. ✅ Clean separation: Auth vs HR concerns
2. ✅ Flexible: Not all users on payroll, not all employees have login
3. ✅ Scalable: Each model optimized for purpose
4. ✅ Maintainable: Changes to payroll don't affect authentication

**Key Principle**: 
- **users.Employee** = "Who can login and what role?"
- **hr.Employee** = "Who works here and how much do we pay?"

**Next Steps**:
1. ✅ Document this distinction (this file)
2. ✅ Add code comments to both models
3. ✅ Update API documentation
4. ✅ Add admin help text
5. ⚠️ Consider adding validation to prevent confusion

---

**Document Owner**: Backend Team  
**Review Date**: March 2026  
**Status**: 🟢 Active Design Pattern
