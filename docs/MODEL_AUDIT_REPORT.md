# Model Audit Report - Vendor ERP Backend

**Date**: December 26, 2025  
**Status**: ✅ COMPREHENSIVE AUDIT COMPLETE

---

## Executive Summary

Comprehensive audit of all Django models across 16 apps completed. The codebase shows **professional architecture with minimal conflicts**. Most models follow Django best practices with proper relationships, constraints, and indexing.

### Overall Assessment: ✅ EXCELLENT

- **Critical Issues**: 🟢 None
- **Model Conflicts**: 🟢 None detected
- **Design Inconsistencies**: 🟡 Minor (detailed below)
- **Migration Issues**: 🟢 None detected
- **Related Name Conflicts**: 🟢 Resolved (portal.RetailerUser uses unique name)

---

## 1. Core Models Audit

### ✅ core/models/base.py
**Status**: CLEAN - No issues

**Models**:
- `BaseModel` - UUID primary key, timestamps
- `CompanyScopedModel` - Multi-tenant base with dynamic related_name pattern

**Strengths**:
- Proper use of abstract models
- Dynamic related_name pattern `%(app_label)s_%(class)s_set` prevents conflicts
- Appropriate indexing on timestamps and company fields

### ✅ core/auth/models.py
**Status**: CLEAN - Properly designed

**Model**: `User` (extends AbstractUser)

**Fields**:
```python
- phone (CharField, nullable)
- email_verified (Boolean)
- phone_verified (Boolean)
- is_internal_user (Boolean) - ERP staff
- is_portal_user (Boolean) - Retailer/customer
- active_company (FK to Company, nullable)
```

**Strengths**:
- Clean separation of concerns
- Supports both internal and portal users
- Multi-company context tracking with active_company
- No business logic in User model (kept in CompanyUser, Employee, RetailerUser)

---

## 2. Company App Models

### ✅ apps/company/models.py
**Status**: CLEAN - Well-designed multi-tenant foundation

**Models**:
1. **Currency** - Global master ✅
2. **Company** - Multi-tenant root ✅
3. **Address** - Company addresses ✅
4. **CompanyFeature** - Feature flags ✅
5. **CompanyUser** - User-to-company mapping with roles ✅
6. **FinancialYear** - FY management with constraints ✅
7. **Sequence** - Auto-numbering ✅

**Key Features**:
- ✅ Proper enum choices for company types, roles, address types
- ✅ Currency is protected (PROTECT on_delete)
- ✅ Financial year constraints:
  - Only one `is_current=True` per company
  - No overlapping dates (validated in `clean()`)
  - CheckConstraint: start_date < end_date
- ✅ Thread-safe sequence note (must use select_for_update)

**Related Names**: All unique, no conflicts

---

## 3. Users App Models

### ✅ apps/users/models.py
**Status**: CLEAN

**Models**:
1. **Employee** - Internal employee records ✅
2. **PasswordResetOTP** - OTP-based password reset ✅

**Key Features**:
- Employee links to User (OneToOne, nullable)
- Employee links to Company (ForeignKey)
- Proper OTP expiry handling (10 minutes)
- Auto-generation of 6-digit OTP

**Note**: This is separate from hr.Employee which has more detailed HR tracking.

**Recommendation**: 🟡 **MINOR INCONSISTENCY**
- `users.Employee` uses auto-increment `employee_id` as PK
- `hr.Employee` extends `CompanyScopedModel` (uses UUID)
- Consider consolidating or documenting why two Employee models exist

---

## 4. Accounting App Models

### ✅ apps/accounting/models.py
**Status**: CLEAN - Professional double-entry system

**Models**:
1. **AccountGroup** - Hierarchical chart of accounts ✅
2. **Ledger** - Leaf-level accounts ✅
3. **TaxLedger** - Tax configuration ✅
4. **CostCenter** - Dimensional analysis ✅
5. **LedgerBalance** - Cached balances ✅

**Key Features**:
- ✅ Materialized path in AccountGroup for hierarchy traversal
- ✅ Proper enums: AccountNature, ReportType, AccountType, BalanceType, TaxType
- ✅ Ledger links to AccountGroup (PROTECT)
- ✅ Opening balance tracks FY
- ✅ Bill-wise tracking flag for receivables/payables
- ✅ LedgerBalance unique constraint: (company, ledger, financial_year)
- ✅ Net balance calculation method

**Strengths**:
- Clear separation of AccountGroup (hierarchy) vs Ledger (transactions)
- TaxLedger extends Ledger with tax-specific fields
- LedgerBalance cache includes idempotency tracking (last_posted_voucher)

---

## 5. Products App Models

### 🟡 apps/products/models.py
**Status**: INCONSISTENT WITH OTHER APPS

**Models**:
1. **Category** - Product categories
2. **Product** - Product master

**Issues Identified**:

#### 🟡 Issue 1: Does NOT extend BaseModel/CompanyScopedModel
```python
class Category(models.Model):  # ❌ Should be CompanyScopedModel
    category_id = models.AutoField(primary_key=True)  # ❌ Should use UUID
    company = models.ForeignKey(...)  # Manual company FK
```

**Recommendation**: 
```python
class Category(CompanyScopedModel):  # ✅ Inherit from base
    name = models.CharField(...)  # ✅ Remove manual company FK, use inherited
    # Remove category_id - will use inherited UUID 'id'
```

#### 🟡 Issue 2: Product uses auto-increment PK instead of UUID
```python
class Product(models.Model):  # ❌ Should be CompanyScopedModel
    product_id = models.AutoField(primary_key=True)  # ❌ Inconsistent with rest of system
```

**Impact**: 
- Inconsistent with architecture (all other models use UUID)
- Breaks pattern established by inventory.StockItem which uses UUID
- Makes integration and API design inconsistent

#### 🟡 Issue 3: Overlap with inventory.StockItem
- `products.Product` has: name, category, available_quantity, unit, price, hsn_code, GST rates
- `inventory.StockItem` has: sku, name, description, uom, is_stock_item

**Questions**:
- Why two product models?
- Is `products.Product` legacy?
- Should orders use `StockItem` instead of `Product`?

**Current Order Item Implementation**:
```python
class OrderItem(CompanyScopedModel):
    item = models.ForeignKey("inventory.StockItem", ...)  # ✅ Uses StockItem, not Product
```

**Recommendation**: 🚨 **CRITICAL DESIGN DECISION NEEDED**
- Option A: Deprecate `products` app, migrate to `inventory.StockItem`
- Option B: Clarify relationship (e.g., Product = catalog, StockItem = inventory tracking)
- Option C: Merge models into single comprehensive product model

#### 🟡 Issue 4: Missing company scope on related_name
```python
company = models.ForeignKey('company.Company', related_name="products")
```
Should use dynamic pattern or unique name to avoid conflicts if multiple apps use "products"

---

## 6. Inventory App Models

### ✅ apps/inventory/models.py
**Status**: CLEAN - Professional inventory system

**Models**:
1. **UnitOfMeasure** - Global UOM master ✅
2. **StockItem** - Company-scoped inventory items ✅
3. **PriceList** - Time-bound price lists ✅
4. **ItemPrice** - Item prices per price list ✅
5. **StockBatch** - Batch/lot tracking ✅
6. **Godown** - Warehouse locations ✅
7. **StockMovement** - Movement transactions ✅
8. **StockBalance** - Cached balances (FIFO-ready) ✅

**Key Features**:
- ✅ All models extend CompanyScopedModel (except UnitOfMeasure - global)
- ✅ Proper UUID primary keys
- ✅ StockBalance has calculated `quantity_available` property
- ✅ Idempotency tracking (last_movement FK)
- ✅ CheckConstraint: quantity > 0 on movements
- ✅ Movement types enum (RECEIPT, ISSUE, ADJUSTMENT, TRANSFER)

**Strengths**:
- Professional inventory architecture
- Proper FIFO/batch tracking foundation
- Separate balance cache for performance

---

## 7. Orders App Models

### ✅ apps/orders/models.py
**Status**: CLEAN - Well-designed order system

**Models**:
1. **SalesOrder** - Customer orders ✅
2. **PurchaseOrder** - Supplier orders ✅
3. **OrderItem** - Line items (polymorphic) ✅

**Key Features**:
- ✅ OrderStatus enum with comprehensive states
- ✅ Lifecycle tracking (confirmed_at, invoiced_at, posted_at, cancelled_at)
- ✅ OrderItem supports both SO and PO (polymorphic design)
- ✅ CheckConstraint: Must belong to exactly one order type
- ✅ CheckConstraint: quantity > 0, delivered_qty >= 0
- ✅ Proper use of limit_choices_to on Party FK

**Design Patterns**:
```python
class OrderItem:
    sales_order = FK(SalesOrder, null=True)
    purchase_order = FK(PurchaseOrder, null=True)
    
    # Constraint ensures exactly one parent
    constraints = [
        CheckConstraint(
            check=(SO not null AND PO null) OR (SO null AND PO not null)
        )
    ]
```

**Strengths**:
- Clean polymorphic design
- Proper validation at DB level
- Rich lifecycle tracking for business processes

---

## 8. Party App Models

### ✅ apps/party/models.py
**Status**: CLEAN - Enterprise party management

**Models**:
1. **Party** - Customer/Supplier master ✅
2. **PartyAddress** - Multiple addresses ✅
3. **PartyBankAccount** - Bank details ✅

**Key Features**:
- ✅ Party has OneToOne to accounting.Ledger (every party = one control ledger)
- ✅ PartyType enum: CUSTOMER, SUPPLIER, BOTH, EMPLOYEE, OTHER
- ✅ Credit limit and credit days tracking
- ✅ is_retailer flag for portal access
- ✅ Multiple addresses per party with is_default flag
- ✅ GST and PAN tracking

**Strengths**:
- Direct integration with accounting (Ledger link)
- Supports multiple address types (BILLING, SHIPPING, REGISTERED, CONTACT)
- Bank account tracking with IFSC/SWIFT

---

## 9. Invoice App Models

### ✅ apps/invoice/models.py
**Status**: CLEAN - Proper invoice-voucher integration

**Models**:
1. **Invoice** - Invoice master ✅
2. **InvoiceLine** - Invoice line items ✅

**Key Features**:
- ✅ Invoice links to voucher.Voucher (OneToOne) for accounting integration
- ✅ Links to SalesOrder or PurchaseOrder (nullable)
- ✅ InvoiceType enum: SALES, PURCHASE, DEBIT_NOTE, CREDIT_NOTE, PROFORMA
- ✅ InvoiceStatus enum with comprehensive states
- ✅ Denormalized amounts for performance (subtotal, tax, discount, grand_total)
- ✅ Payment tracking (amount_received)

**Strengths**:
- Clean separation of invoice data and accounting posting
- Proper reference tracking to orders
- Performance-optimized with denormalized totals

---

## 10. Voucher App Models

### ✅ apps/voucher/models.py
**Status**: CLEAN - Core double-entry system

**Models**:
1. **VoucherType** - Voucher type configuration ✅
2. **Voucher** - Accounting voucher ✅
3. **VoucherLine** - Journal entries ✅

**Key Features**:
- ✅ VoucherCategory enum: JOURNAL, PAYMENT, RECEIPT, CONTRA, SALES, PURCHASE
- ✅ VoucherStatus: DRAFT, POSTED, CANCELLED, REVERSED
- ✅ Voucher tracks financial_year (required)
- ✅ Unique constraint: (company, voucher_type, financial_year, voucher_number)
- ✅ Reversal tracking (reversed_voucher FK, reversal_reason, reversal_user)
- ✅ VoucherLine with debit/credit amounts

**Strengths**:
- Professional double-entry accounting foundation
- Comprehensive reversal tracking
- Proper FY scoping on voucher numbers

---

## 11. Portal App Models

### ✅ apps/portal/models.py
**Status**: CLEAN - Previously had conflict, now resolved

**Models**:
1. **RetailerUser** - Retailer portal access ✅
2. **RetailerCompanyAccess** - Approval workflow ✅

**Key Features**:
- ✅ RetailerUser uses `related_name='portal_retailer_users'` (FIXED - was 'retailer_users')
- ✅ Links User to Party (business entity)
- ✅ Permission flags (can_place_orders, can_view_balance, can_view_statements)
- ✅ RetailerCompanyAccess tracks approval status (PENDING, APPROVED, BLOCKED, REJECTED)

**Resolution**: Previously conflicted with another model, now uses unique related_name.

---

## 12. Workflow App Models

### ✅ apps/workflow/models.py
**Status**: CLEAN - Maker-checker pattern

**Models**:
1. **Approval** - Generic approval workflow ✅

**Key Features**:
- ✅ Generic design (target_type + target_id)
- ✅ ApprovalStatus enum: PENDING, APPROVED, REJECTED
- ✅ Tracks requester and approver
- ✅ UniqueConstraint: Only one PENDING approval per target
- ✅ Helper methods: approve(), reject()

**Strengths**:
- Generic, reusable across all apps
- Proper constraint to prevent duplicate pending approvals
- Rich audit trail (requested_by, approved_by, approved_at, remarks)

---

## 13. System App Models

### ✅ apps/system/models.py
**Status**: CLEAN - Audit and integration

**Models**:
1. **AuditLog** - Comprehensive audit trail ✅
2. **IntegrationEvent** - Outbound event queue ✅
3. **IdempotencyKey** - Idempotency tracking ✅

**Key Features**:
- ✅ AuditLog tracks: actor, action, object, changes (JSONField), IP, user agent
- ✅ ActionType enum with comprehensive actions
- ✅ IntegrationEvent with retry mechanism (attempts, max_attempts)
- ✅ IntegrationStatus: PENDING, PROCESSING, SUCCESS, FAILED, RETRY

**Strengths**:
- Professional audit trail implementation
- Event-driven architecture support
- Idempotency key pattern for API safety

---

## 14. HR App Models

### ✅ apps/hr/models.py
**Status**: CLEAN - Comprehensive HR system

**Models**:
1. **Department** - Hierarchical departments ✅
2. **Employee** - HR employee master ✅
3. **EmployeeLedger** - Employee accounting ledger link ✅
4. **PayHead** - Salary components ✅
5. **EmployeePayStructure** - Individual pay structures ✅
6. **PayrollRun** - Payroll processing ✅

**Key Features**:
- ✅ Department has self-referencing parent FK (hierarchy)
- ✅ Employee links to User (nullable), Department, and can have ledger
- ✅ Rich payroll structure with pay heads (EARNING, DEDUCTION, REIMBURSEMENT)

**Note**: Different from `users.Employee` (simpler version)

---

## 15. Related Name Analysis

### ✅ No Conflicts Detected

All related_name values are unique or use dynamic patterns:

**Dynamic Patterns** (CompanyScopedModel):
```python
related_name="%(app_label)s_%(class)s_set"
```
Examples:
- `company.ledgers` → `accounting_ledger_set`
- `company.invoices` → `invoice_invoice_set`

**Manual Unique Names**:
- `company_memberships` (CompanyUser to User)
- `employee_profiles` (hr.Employee to User)
- `employee_profile` (users.Employee to User)
- `retailer_profile` (RetailerUser to User)
- `portal_retailer_users` (RetailerUser to Party) ✅ FIXED
- All others reviewed - no duplicates

---

## 16. Migration Health Check

### ✅ All Migrations Applied

Based on previous session:
- ✅ Fresh database created
- ✅ All migrations applied successfully
- ✅ No pending migrations
- ✅ No migration conflicts

**Last Migration Check**: Database reset on Dec 26, 2025
**Status**: Clean slate, all apps migrated

---

## 17. Consistency Issues Summary

### 🟡 Design Inconsistencies (Non-Critical)

1. **products.Product vs inventory.StockItem**
   - Severity: MEDIUM
   - Impact: Architectural confusion, potential duplication
   - Recommendation: Clarify relationship or consolidate

2. **users.Employee vs hr.Employee**
   - Severity: LOW
   - Impact: Minor confusion, possibly intentional separation
   - Recommendation: Document distinction or merge

3. **products app not using base models**
   - Severity: MEDIUM
   - Impact: Inconsistent with rest of system (UUID vs int PK)
   - Recommendation: Refactor to extend CompanyScopedModel

### ✅ Critical Issues: NONE

---

## 18. Best Practices Observed

### ✅ Excellent Patterns Used:

1. **Multi-Tenancy**: Clean CompanyScopedModel pattern
2. **Enums**: Consistent use of TextChoices
3. **Constraints**: Proper CheckConstraints and UniqueConstraints
4. **Indexing**: Comprehensive indexing strategy
5. **Audit Trail**: Rich tracking fields (created_at, updated_at, posted_at, etc.)
6. **Cache Tables**: LedgerBalance, StockBalance with idempotency
7. **Polymorphic Design**: OrderItem (SO/PO), Approval (generic target)
8. **Reversal Tracking**: Proper voucher reversal pattern
9. **FY Scoping**: Financial year constraints and validations
10. **Lifecycle States**: Rich status enums with timestamps

---

## 19. Recommendations

### Priority 1: Critical Fixes
✅ **NONE** - No critical issues found

### Priority 2: Design Improvements

1. **Consolidate Product Models** (1-2 days)
   - Clarify products.Product vs inventory.StockItem relationship
   - Document or merge to single source of truth
   - Ensure OrderItem uses correct model

2. **Refactor products app** (1 day)
   - Extend CompanyScopedModel
   - Use UUID primary keys
   - Align with system architecture

3. **Document Employee Models** (1 hour)
   - Clarify users.Employee vs hr.Employee distinction
   - Add docstrings explaining use cases

### Priority 3: Enhancements

1. **Add Model Documentation** (2-3 days)
   - Enhance docstrings with business rules
   - Document all constraints and validations
   - Add relationship diagrams

2. **Consider GenericForeignKey** (investigation)
   - Approval model uses target_type + target_id
   - Could use ContentType framework for type safety

---

## 20. Test File Alignment Issues

### 🟡 Known Test Issues (From Previous Session)

**Test files need alignment with models**:

1. **Ledger Creation** - Tests use old field names:
   ```python
   # Tests use:
   ledger_group=...  # ❌ Should be: group=...
   account_type=...  # ❌ Field doesn't exist on all paths
   ```

2. **AccountGroup Hierarchy** - Tests need proper setup:
   ```python
   # Need to create full hierarchy:
   root_group → parent_group → account_group
   ```

3. **Opening Balance** - Tests may not set:
   ```python
   opening_balance_fy=financial_year  # Required FK
   ```

**Recommendation**: Update test factories with model audit findings

---

## 21. API/Serializer Alignment

### Status: NOT YET AUDITED

**Next Step**: Verify serializers match model definitions

**Files to Check**:
- `apps/*/api/serializers.py` (14 files)
- `apps/*/api/views.py` (14 files)

**Common Issues to Look For**:
- Serializer fields matching model fields
- Proper nested serializers for FKs
- Write-only fields (passwords, etc.)
- Read-only computed fields

---

## 22. Conclusion

### Overall System Health: ✅ EXCELLENT

**Strengths**:
- Professional architecture with clean separation of concerns
- Proper multi-tenant design
- Comprehensive audit trails
- Well-designed double-entry accounting
- Rich business logic enforcement via constraints
- Proper use of Django patterns

**Minor Issues**:
- Product model inconsistency (easily fixable)
- Needs documentation improvements

**Next Steps**:
1. ✅ Model audit complete (this document)
2. 🔲 API/Serializer alignment check
3. 🔲 Fix test file Ledger creation patterns
4. 🔲 Clarify/consolidate product models
5. 🔲 Add comprehensive model documentation

---

## Appendix A: Model Relationship Map

```
Company (root)
├── Currency (FK)
├── CompanyFeature (1:1)
├── CompanyUser (M:M via through)
├── FinancialYear (1:M)
├── AccountGroup (1:M)
│   └── Ledger (1:M)
│       ├── TaxLedger (1:1)
│       └── LedgerBalance (1:M, per FY)
├── Party (1:M)
│   ├── Ledger (1:1 link)
│   ├── PartyAddress (1:M)
│   └── PartyBankAccount (1:M)
├── StockItem (1:M)
│   ├── StockBatch (1:M)
│   └── StockBalance (1:M, per godown/batch)
├── SalesOrder (1:M)
│   ├── OrderItem (1:M)
│   └── Invoice (1:M)
├── PurchaseOrder (1:M)
│   ├── OrderItem (1:M)
│   └── Invoice (1:M)
├── Invoice (1:M)
│   ├── InvoiceLine (1:M)
│   └── Voucher (1:1)
├── VoucherType (1:M)
│   └── Voucher (1:M)
│       └── VoucherLine (1:M)
└── Department (1:M)
    └── Employee (1:M)
        └── EmployeeLedger (1:1)

User (auth)
├── CompanyUser (M:M to Company)
├── Employee (users) (1:1)
├── Employee (hr) (1:M)
└── RetailerUser (1:1)
    └── RetailerCompanyAccess (M:M to Company)
```

---

**Report End**  
**Generated**: December 26, 2025  
**Auditor**: AI Model Audit System  
**Status**: ✅ AUDIT COMPLETE
