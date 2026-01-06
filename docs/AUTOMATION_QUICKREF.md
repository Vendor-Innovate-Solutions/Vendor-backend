## PHASE 5 - AUTOMATION & WORKFLOW - QUICK REFERENCE

**Status**: ✅ Complete | **Files**: 18 | **Lines**: ~2,400 | **APIs**: 11

---

## 🚀 QUICK START

### 1. Credit Control

**Check Party Credit**:
```bash
GET /api/party/{party_id}/credit_status/
```

**Validate Order**:
```bash
POST /api/party/{party_id}/can-order/
{"order_value": 50000.00}
```

### 2. Approval Workflow

**Submit for Approval**:
```bash
POST /api/workflow/request/
{"target_type": "voucher", "target_id": "<uuid>", "remarks": "Please review"}
```

**Approve** (ADMIN/ACCOUNTANT only):
```bash
POST /api/workflow/approve/voucher/{id}/
{"remarks": "Approved"}
```

**Reject**:
```bash
POST /api/workflow/reject/voucher/{id}/
{"remarks": "Missing documents"}
```

### 3. Aging Reports

**Full Report** (cached):
```bash
GET /api/reports/aging/?use_cache=true
```

**Quick Summary**:
```bash
GET /api/reports/aging/summary/
```

**Overdue Parties**:
```bash
GET /api/reports/overdue/?days_threshold=30
```

---

## 📂 KEY FILES

### Credit Control
- `apps/party/services/credit.py` - Credit calculation (220 lines)
- `apps/party/api/views.py` - Credit APIs (180 lines)
- `apps/orders/services/sales_order_service.py` - Modified with credit check

### Approval Workflow
- `apps/workflow/models.py` - Approval & ApprovalRule (200 lines)
- `apps/workflow/api/views.py` - 5 workflow APIs (290 lines)
- `core/services/posting.py` - Modified with approval check

### Event Bus
- `apps/system/tasks.py` - Celery tasks with retry (380 lines)

### Aging Reports
- `apps/reporting/services/aging.py` - Aging calculation (360 lines)
- `apps/reporting/api/views.py` - 3 report APIs (180 lines)

---

## 🔑 KEY FUNCTIONS

### Credit Service
```python
from apps.party.services.credit import (
    get_outstanding_for_party,  # Returns Decimal
    get_credit_status,          # Returns Dict
    check_credit_limit,         # Raises ValidationError if exceeded
    can_create_order            # Returns Dict with allowed flag
)
```

### Approval Workflow
```python
from apps.workflow.models import Approval, ApprovalStatus

# Check approval
approval = Approval.objects.filter(
    target_type='voucher',
    target_id=voucher_id,
    status=ApprovalStatus.APPROVED
).first()

# Approve
approval.approve(user, remarks="Approved")

# Reject
approval.reject(user, remarks="Missing docs")
```

### Aging Reports
```python
from apps.reporting.services.aging import (
    aging_for_company,           # Full report
    aging_summary,               # Quick summary
    get_cached_aging,            # From cache
    generate_and_cache_aging,    # Generate & cache
    overdue_parties              # List overdue
)
```

---

## ⚡ CELERY TASKS

### Start Workers
```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

### Tasks Available
- `process_integration_event(event_id)` - Process events with retry
- `generate_aging_reports()` - Daily at 6 AM
- `send_overdue_reminders()` - Daily at 9 AM
- `cleanup_old_audit_logs(days=365)` - Cleanup task

### Trigger Manually
```python
from apps.system.tasks import process_integration_event
process_integration_event.delay(event_id)
```

---

## 🧪 TEST COMMANDS

### Credit Control
```bash
# Get credit status
curl -X GET http://localhost:8000/api/party/{id}/credit_status/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>"

# Check order allowed
curl -X POST http://localhost:8000/api/party/{id}/can-order/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>" \
  -d '{"order_value": 50000.00}'
```

### Approval Workflow
```bash
# Submit for approval
curl -X POST http://localhost:8000/api/workflow/request/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>" \
  -d '{"target_type": "voucher", "target_id": "<uuid>"}'

# Approve
curl -X POST http://localhost:8000/api/workflow/approve/voucher/{id}/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>" \
  -d '{"remarks": "Approved"}'
```

### Aging Reports
```bash
# Full report
curl -X GET http://localhost:8000/api/reports/aging/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>"

# Summary only
curl -X GET http://localhost:8000/api/reports/aging/summary/ \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>"

# Overdue parties
curl -X GET http://localhost:8000/api/reports/overdue/?days_threshold=30 \
  -H "Authorization: Bearer <token>" -H "Company-ID: <uuid>"
```

---

## 🔧 COMMON CONFIGURATIONS

### Create ApprovalRule
```python
from apps.workflow.models import ApprovalRule
from decimal import Decimal

ApprovalRule.objects.create(
    company=company,
    target_type='voucher',
    approval_required=True,
    threshold_amount=Decimal('10000.00'),
    auto_approve_below_threshold=True
)
```

### Configure Webhook
```python
from apps.company.models import CompanyFeature

features, _ = CompanyFeature.objects.get_or_create(company=company)
features.webhook_url = 'https://your-endpoint.com/events'
features.save()
```

### Set Credit Limit
```python
from apps.party.models import Party

party = Party.objects.get(id=party_id)
party.credit_limit = Decimal('500000.00')
party.save()
```

---

## 📊 AGING BUCKETS

| Bucket | Days | Status | Action |
|--------|------|--------|--------|
| 0-30 | 0-30 | Current | No action |
| 31-60 | 31-60 | Slightly overdue | Gentle reminder |
| 61-90 | 61-90 | Overdue | Firm reminder |
| 90+ | 90+ | Seriously overdue | Escalate to collections |

---

## 🔐 ROLE PERMISSIONS

### Credit Control
- **All Authenticated**: Can view credit status
- **ADMIN/ACCOUNTANT**: Can modify credit limits

### Approval Workflow
- **MAKER** (All users): Can submit for approval
- **CHECKER** (ADMIN/ACCOUNTANT): Can approve/reject
- **POSTER** (System): Posts after approval

### Reports
- **All Authenticated**: Can view aging reports
- **ADMIN/ACCOUNTANT**: Can trigger manual generation

---

## 🐛 QUICK TROUBLESHOOTING

### Credit check fails unexpectedly
```python
from apps.party.services.credit import get_outstanding_for_party
outstanding = get_outstanding_for_party(party, company)
print(f"Outstanding: {outstanding}, Limit: {party.credit_limit}")
```

### Approval fails (403)
```python
# Check user role
print(request.user.role)  # Must be ADMIN or ACCOUNTANT

# Check not self-approval
approval = Approval.objects.get(target_id=voucher_id)
print(f"Requested: {approval.requested_by}, Current: {request.user}")
```

### Aging report empty
```python
# Check invoices
invoices = Invoice.objects.filter(
    company=company,
    status__in=['POSTED', 'PARTIALLY_PAID']
)
print(f"Count: {invoices.count()}")
```

### Celery task not processing
```bash
# Check worker running
ps aux | grep celery

# Check Redis
redis-cli ping

# Restart worker
pkill celery
celery -A config worker --loglevel=info
```

---

## 📈 PERFORMANCE TIPS

1. **Use Cached Aging Reports**: Add `?use_cache=true` to aging API
2. **Limit Date Range**: Don't query >1 year of invoices
3. **Index**: Ensure DB indexes on (company, status, invoice_date)
4. **Celery**: Use Redis (not RabbitMQ) for better performance

---

## 📚 RELATED DOCS

- [AUTOMATION_WORKFLOW_REPORTING_COMPLETE.md](AUTOMATION_WORKFLOW_REPORTING_COMPLETE.md) - Full documentation
- [PHASE2_POSTING_SERVICE.md](PHASE2_POSTING_SERVICE.md) - Posting logic
- [GST_COMPLIANCE_COMPLETE.md](GST_COMPLIANCE_COMPLETE.md) - GST features
- [FINANCIAL_YEAR_COMPLETE.md](FINANCIAL_YEAR_COMPLETE.md) - FY locking

---

**Version**: 1.0 | **Status**: ✅ Production Ready
