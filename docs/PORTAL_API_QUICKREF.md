# Portal Retailer APIs - Quick Reference

## Retailer Registration Flow

### 1. Discover Companies (Public)
```bash
GET /api/portal/companies/discover/?q=steel&city=Mumbai
```

### 2. Register (Public)
```bash
POST /api/portal/register/
{
  "email": "retailer@example.com",
  "password": "password",
  "company_id": "uuid",
  "full_name": "John Doe"
}
```

### 3. Admin Approval
```bash
POST /api/portal/retailers/{id}/approve/
Authorization: Bearer ADMIN_TOKEN
{
  "create_party": true,
  "phone": "+91..."
}
```

## Catalog APIs

### List Items
```bash
GET /api/portal/items/?q=widget&category=electronics&limit=50
Authorization: Bearer RETAILER_TOKEN
```

### Item Details
```bash
GET /api/portal/items/{item_id}/
Authorization: Bearer RETAILER_TOKEN
```

## Pricing APIs

### Single Item Price
```bash
GET /api/pricing/items/{item_id}/
Authorization: Bearer RETAILER_TOKEN
```

### Bulk Pricing
```bash
POST /api/pricing/items/bulk/
Authorization: Bearer RETAILER_TOKEN
{
  "item_ids": ["uuid1", "uuid2", "uuid3"]
}
```

## Order APIs

### Create Order
```bash
POST /api/portal/orders/create/
Authorization: Bearer RETAILER_TOKEN
{
  "items": [
    {"item_id": "uuid", "quantity": 10},
    {"item_id": "uuid2", "quantity": 5, "unit_rate": 100}
  ],
  "delivery_date": "2025-01-15",
  "notes": "Urgent"
}
```

### List Orders
```bash
GET /api/portal/orders/?status=CONFIRMED
Authorization: Bearer RETAILER_TOKEN
```

### Order Status
```bash
GET /api/portal/orders/{order_id}/
Authorization: Bearer RETAILER_TOKEN
```

### Reorder
```bash
POST /api/portal/orders/{order_id}/reorder/
Authorization: Bearer RETAILER_TOKEN
{
  "delivery_date": "2025-02-01"
}
```

## Admin APIs

### List Retailer Requests
```bash
GET /api/portal/retailers/?status=PENDING
Authorization: Bearer ADMIN_TOKEN
```

### Reject Retailer
```bash
POST /api/portal/retailers/{id}/reject/
Authorization: Bearer ADMIN_TOKEN
{
  "reason": "Invalid documents"
}
```

## Pricing Hierarchy

1. **Party Price List** (if retailer has custom pricing)
2. **Company Default Price List** (company-wide pricing)
3. **Item Default Price** (item's latest price)
4. **Item Standard Rate** (fallback)

## Status Codes

- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Validation error
- `403 Forbidden` - Not approved or wrong role
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

## Common Errors

**Retailer not approved:**
```json
{"error": "No approved retailer access for this company"}
```

**Credit limit exceeded:**
```json
{"error": "Credit limit exceeded"}
```

**No price available:**
```json
{"error": "No price available for item Widget A"}
```

## Integration Events

Portal orders trigger:
```json
{
  "event_type": "portal.order.created",
  "payload": {
    "order_id": "uuid",
    "order_number": "SO-2025-0001",
    "customer_name": "Retailer Co",
    "total_amount": 1500.00
  }
}
```
