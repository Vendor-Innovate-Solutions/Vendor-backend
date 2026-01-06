# Quick Reference: Posting Service

## Import & Setup

```python
from core.services.posting import PostingService, post_voucher, post_invoice

service = PostingService()
```

## Common Operations

### 1. Post a Voucher
```python
voucher = service.post_voucher(
    voucher_id='uuid',
    user=request.user,
    idempotency_key='optional-key',
    metadata={'ip_address': '...'}
)
```

### 2. Post an Invoice
```python
voucher = service.post_invoice(
    invoice_id='uuid',
    user=request.user,
    idempotency_key='invoice-123'
)
```

### 3. Convenience Functions
```python
# Quick voucher posting
voucher = post_voucher(voucher_id, user)

# Quick invoice posting
voucher = post_invoice(invoice_id, user, idempotency_key='key')
```

## Exception Handling

```python
from core.services.posting import (
    PostingError,
    AlreadyPosted,
    UnbalancedVoucher,
    InsufficientStock,
    FinancialYearClosed,
    CompanyLocked,
    InvalidVoucherType
)

try:
    voucher = service.post_voucher(voucher_id, user)
except AlreadyPosted:
    # Voucher already posted
except UnbalancedVoucher:
    # DR != CR
except InsufficientStock:
    # Not enough stock
except FinancialYearClosed:
    # FY closed
except CompanyLocked:
    # Accounting freeze
except InvalidVoucherType:
    # Voucher type inactive
except PostingError as e:
    # Generic posting error
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Double-Entry** | Validates DR == CR with Decimal rounding |
| **Idempotency** | Prevents duplicate posting via keys |
| **Locking** | SELECT FOR UPDATE on critical resources |
| **FIFO** | Automatic batch allocation |
| **Audit Trail** | Complete audit logs |
| **Events** | Integration events for async processing |
| **Atomic** | Full transaction safety |

## Validation Checks

Automatically validates:
- ✓ Financial year not closed
- ✓ Company not locked
- ✓ Voucher type active
- ✓ Double-entry balanced
- ✓ Stock availability (if inventory voucher)
- ✓ Not already posted

## Sequence Numbering

Automatic sequence allocation:
- Format: `{company_id}:{voucher_type}:{fy_id}`
- Thread-safe with SELECT FOR UPDATE
- No duplicate numbers
- Per-company, per-type, per-FY sequences

## Stock Allocation

FIFO batch allocation:
- Locks batches during allocation
- Prevents over-allocation
- Race-condition safe
- Raises InsufficientStock if not enough

## Idempotency

```python
# First call
voucher = post_voucher(
    voucher_id,
    user,
    idempotency_key='external-ref-123'
)

# Retry (returns existing voucher)
same_voucher = post_voucher(
    voucher_id,
    user,
    idempotency_key='external-ref-123'
)

assert voucher.id == same_voucher.id  # True
```

## Context Metadata

```python
voucher = service.post_voucher(
    voucher_id,
    user,
    metadata={
        'ip_address': request.META['REMOTE_ADDR'],
        'user_agent': request.META['HTTP_USER_AGENT'],
        'source': 'web',
        'approval_id': 'uuid'
    }
)
```

## Performance Tips

1. **Use bulk operations where possible**
2. **Pre-load related objects with select_related()**
3. **Keep atomic blocks small**
4. **Monitor lock wait times**
5. **Use idempotency keys for API calls**

## Testing

```python
# Unit test example
from core.services.posting import PostingService

def test_posting():
    service = PostingService()
    voucher = service.post_voucher(voucher_id, user)
    assert voucher.status == 'POSTED'
```

## Common Patterns

### Web View
```python
from django.views import View
from core.services.posting import post_voucher

class PostVoucherView(View):
    def post(self, request, voucher_id):
        try:
            voucher = post_voucher(
                voucher_id,
                request.user,
                idempotency_key=request.headers.get('Idempotency-Key'),
                metadata={
                    'ip_address': request.META['REMOTE_ADDR'],
                    'user_agent': request.META['HTTP_USER_AGENT']
                }
            )
            return JsonResponse({'voucher_number': voucher.voucher_number})
        except PostingError as e:
            return JsonResponse({'error': str(e)}, status=400)
```

### API Endpoint
```python
from rest_framework.decorators import api_view
from core.services.posting import post_invoice

@api_view(['POST'])
def post_invoice_api(request, invoice_id):
    try:
        voucher = post_invoice(
            invoice_id,
            request.user,
            idempotency_key=request.headers.get('Idempotency-Key')
        )
        return Response({
            'voucher_id': str(voucher.id),
            'voucher_number': voucher.voucher_number
        })
    except PostingError as e:
        return Response({'error': str(e)}, status=400)
```

### Celery Task
```python
from celery import shared_task
from core.services.posting import post_voucher

@shared_task
def post_voucher_async(voucher_id, user_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=user_id)
    
    try:
        voucher = post_voucher(voucher_id, user)
        return {'success': True, 'voucher_number': voucher.voucher_number}
    except PostingError as e:
        return {'success': False, 'error': str(e)}
```

## Monitoring

Key metrics to track:
- Posting success rate
- Average posting time
- Lock wait times
- Idempotency hit rate
- Stock allocation failures

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| UnbalancedVoucher | DR != CR | Check line amounts, verify rounding |
| InsufficientStock | Not enough stock | Check stock balances, verify godowns |
| AlreadyPosted | Duplicate post | Check voucher status, use idempotency |
| FinancialYearClosed | FY closed | Open FY or post to correct period |
| CompanyLocked | Accounting freeze | Unlock company features |

## Best Practices

1. ✓ Always use idempotency keys for API calls
2. ✓ Include metadata for audit trails
3. ✓ Handle all specific exceptions
4. ✓ Log failures for monitoring
5. ✓ Test concurrent posting scenarios
6. ✓ Monitor performance metrics
7. ✓ Validate data before posting
8. ✓ Use atomic transactions consistently

## More Information

See [PHASE2_POSTING_SERVICE.md](PHASE2_POSTING_SERVICE.md) for complete documentation.
