# Stock APIs - Quick Reference

Complete guide to the inventory and stock management APIs.

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Stock Items](#stock-items)
- [Godowns (Warehouses)](#godowns-warehouses)
- [Stock Balance](#stock-balance)
- [Stock Movements](#stock-movements)
- [Stock Transfers](#stock-transfers)
- [Stock Reservations](#stock-reservations)
- [Business Rules](#business-rules)
- [Error Handling](#error-handling)

---

## Overview

The Stock APIs provide complete inventory management functionality:
- ✅ Stock items CRUD with company scoping
- ✅ Real-time stock balance queries
- ✅ Stock movements (IN/OUT tracking)
- ✅ Inter-godown transfers
- ✅ Stock reservations
- ✅ **Negative stock prevention** (automatic guard)
- ✅ **Auto-updating balances** (via signals)

**Base URL:** `/api/inventory/`

---

## Authentication

All endpoints require JWT authentication:

```http
Authorization: Bearer <access_token>
```

**Required Roles:**
- Stock movements/transfers: `ADMIN` or `INVENTORY_MANAGER`
- Read operations: Any authenticated user with company access

---

## Stock Items

### List Stock Items
```http
GET /api/inventory/items/
```

**Query Parameters:**
- `is_active`: Filter by active status (true/false)
- `group`: Filter by stock group ID
- `category`: Filter by category ID
- `search`: Search by name or SKU
- `page`: Page number
- `page_size`: Items per page

**Response:**
```json
{
  "count": 100,
  "results": [
    {
      "id": "uuid",
      "name": "Product A",
      "sku": "PROD-001",
      "group_name": "Electronics",
      "uom_name": "Piece",
      "is_active": true
    }
  ]
}
```

### Get Stock Item Details
```http
GET /api/inventory/items/{id}/
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Product A",
  "sku": "PROD-001",
  "barcode": "1234567890",
  "description": "Product description",
  "group": "uuid",
  "group_name": "Electronics",
  "category": "uuid",
  "category_name": "Phones",
  "base_uom": "uuid",
  "uom_name": "Piece",
  "opening_stock": "100.000",
  "opening_rate": "1500.00",
  "reorder_level": "20.000",
  "reorder_quantity": "50.000",
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

### Create Stock Item
```http
POST /api/inventory/items/
Content-Type: application/json

{
  "name": "New Product",
  "sku": "PROD-002",
  "group": "uuid",
  "category": "uuid",
  "base_uom": "uuid",
  "opening_stock": "50.000",
  "opening_rate": "2000.00",
  "reorder_level": "10.000",
  "is_active": true
}
```

### Update Stock Item
```http
PATCH /api/inventory/items/{id}/
Content-Type: application/json

{
  "name": "Updated Product Name",
  "reorder_level": "15.000"
}
```

### Get Stock Summary
Get total stock across all godowns for an item:

```http
GET /api/inventory/items/{id}/stock_summary/
```

**Response:**
```json
{
  "item_id": "uuid",
  "item_name": "Product A",
  "total_quantity": "250.000",
  "by_godown": [
    {
      "godown_id": "uuid",
      "godown_name": "Main Warehouse",
      "quantity": "150.000"
    },
    {
      "godown_id": "uuid",
      "godown_name": "Branch Store",
      "quantity": "100.000"
    }
  ]
}
```

### Get Item Movement History
```http
GET /api/inventory/items/{id}/movements/?start_date=2024-01-01&end_date=2024-12-31
```

---

## Godowns (Warehouses)

### List Godowns
```http
GET /api/inventory/godowns/
```

**Query Parameters:**
- `is_active`: Filter by active status
- `godown_type`: Filter by type (WAREHOUSE, STORE, etc.)

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "Main Warehouse",
      "code": "WH-001",
      "godown_type": "WAREHOUSE",
      "is_active": true
    }
  ]
}
```

### Create Godown
```http
POST /api/inventory/godowns/
Content-Type: application/json

{
  "name": "Branch Store",
  "code": "ST-001",
  "godown_type": "STORE",
  "is_active": true
}
```

---

## Stock Balance

### Get Current Balance for Specific Item
```http
GET /api/inventory/balance/?item={item_id}&godown={godown_id}
```

**Query Parameters:**
- `item`: Item ID (required)
- `godown`: Godown ID (optional)
- `batch`: Batch number (optional)

**Response:**
```json
{
  "id": "uuid",
  "item": "uuid",
  "item_name": "Product A",
  "item_sku": "PROD-001",
  "godown": "uuid",
  "godown_name": "Main Warehouse",
  "batch": "BATCH-001",
  "quantity": "150.000",
  "uom": "Piece",
  "updated_at": "2024-01-15T14:30:00Z"
}
```

### List All Stock Balances
```http
GET /api/inventory/balances/
```

**Query Parameters:**
- `item`: Filter by item ID
- `godown`: Filter by godown ID
- `min_quantity`: Show only items with quantity >= value

**Response:**
```json
[
  {
    "id": "uuid",
    "item": "uuid",
    "item_name": "Product A",
    "item_sku": "PROD-001",
    "godown": "uuid",
    "godown_name": "Main Warehouse",
    "quantity": "150.000",
    "uom": "Piece",
    "updated_at": "2024-01-15T14:30:00Z"
  }
]
```

---

## Stock Movements

### Create Stock Movement (IN or OUT)
```http
POST /api/inventory/movements/
Content-Type: application/json

{
  "item_id": "uuid",
  "godown_id": "uuid",
  "quantity": "50.000",
  "movement_type": "IN",
  "rate": "1500.00",
  "reason": "Purchase receipt",
  "batch": "BATCH-001",
  "reference_type": "PURCHASE_ORDER",
  "reference_id": "uuid"
}
```

**Movement Types:**
- `IN`: Stock coming into godown
- `OUT`: Stock going out of godown

**Validation:**
- OUT movements check for available stock (negative stock prevention)
- Quantity must be positive
- Item and godown must be active

**Response:**
```json
{
  "id": "uuid",
  "item": "uuid",
  "item_name": "Product A",
  "movement_type": "IN",
  "quantity": "50.000",
  "rate": "1500.00",
  "total_value": "75000.00",
  "from_godown": null,
  "from_godown_name": null,
  "to_godown": "uuid",
  "to_godown_name": "Main Warehouse",
  "batch": "BATCH-001",
  "reason": "Purchase receipt",
  "date": "2024-01-15",
  "reference_type": "PURCHASE_ORDER",
  "reference_id": "uuid",
  "created_at": "2024-01-15T14:30:00Z"
}
```

### List Stock Movements
```http
GET /api/inventory/movements/
```

**Query Parameters:**
- `item`: Filter by item ID
- `godown`: Filter by godown ID
- `movement_type`: Filter by type (IN/OUT)
- `start_date`: Filter from date (YYYY-MM-DD)
- `end_date`: Filter to date (YYYY-MM-DD)

**Response:**
```json
[
  {
    "id": "uuid",
    "item": "uuid",
    "item_name": "Product A",
    "movement_type": "OUT",
    "quantity": "10.000",
    "rate": "1500.00",
    "total_value": "15000.00",
    "from_godown": "uuid",
    "from_godown_name": "Main Warehouse",
    "to_godown": null,
    "to_godown_name": null,
    "reason": "Sales delivery",
    "date": "2024-01-15",
    "created_at": "2024-01-15T14:30:00Z"
  }
]
```

---

## Stock Transfers

Transfer stock between godowns (warehouses).

### Create Stock Transfer
```http
POST /api/inventory/transfers/
Content-Type: application/json

{
  "item_id": "uuid",
  "from_godown_id": "uuid",
  "to_godown_id": "uuid",
  "quantity": "25.000",
  "rate": "1500.00",
  "reason": "Rebalancing stock",
  "batch": "BATCH-001"
}
```

**Validation:**
- Source and destination godowns must be different
- Sufficient stock must be available in source godown
- Both godowns must be active
- Quantity must be positive

**Response:**
```json
{
  "status": "ok",
  "message": "Stock transfer completed successfully",
  "out_movement": {
    "id": "uuid",
    "movement_type": "OUT",
    "quantity": "25.000",
    "from_godown_name": "Main Warehouse",
    "to_godown_name": "Branch Store"
  },
  "in_movement": {
    "id": "uuid",
    "movement_type": "IN",
    "quantity": "25.000",
    "from_godown_name": "Main Warehouse",
    "to_godown_name": "Branch Store"
  }
}
```

**Behind the Scenes:**
- Creates 2 StockMovement records (OUT + IN)
- Updates StockBalance for both godowns automatically
- Atomic transaction ensures data consistency

### List Transfer History
```http
GET /api/inventory/transfers/
```

**Query Parameters:**
- `item`: Filter by item ID
- `godown`: Filter by godown (source or destination)
- `start_date`: Filter from date
- `end_date`: Filter to date

---

## Stock Reservations

Reserve stock for future use (e.g., for pending orders).

### Create Reservation
```http
POST /api/inventory/reservations/
Content-Type: application/json

{
  "item": "uuid",
  "godown": "uuid",
  "quantity": "10.000",
  "status": "ACTIVE",
  "reserved_for_type": "SALES_ORDER",
  "reserved_for_id": "uuid",
  "expires_at": "2024-12-31T23:59:59Z"
}
```

**Response:**
```json
{
  "id": "uuid",
  "item": "uuid",
  "item_name": "Product A",
  "godown": "uuid",
  "godown_name": "Main Warehouse",
  "quantity": "10.000",
  "status": "ACTIVE",
  "reserved_for_type": "SALES_ORDER",
  "reserved_for_id": "uuid",
  "expires_at": "2024-12-31T23:59:59Z",
  "created_at": "2024-01-15T14:30:00Z"
}
```

### List Reservations
```http
GET /api/inventory/reservations/
```

**Query Parameters:**
- `item`: Filter by item ID
- `status`: Filter by status (ACTIVE, FULFILLED, CANCELLED, EXPIRED)

---

## Business Rules

### Negative Stock Prevention

**Automatic Guard:**
All OUT movements and transfers are validated before execution:

```python
# Automatic validation
ensure_stock_available(company, item, quantity, godown)
```

**Example Error:**
```json
{
  "error": "Insufficient stock for Product A at Main Warehouse: available 5.000, required 10.000"
}
```

**When it triggers:**
- Stock OUT movements
- Stock transfers (from source godown)
- Stock reservations (optional check)

### Stock Balance Updates

**Automatic via Signals:**
When a StockMovement is created, StockBalance is automatically updated:

```python
# Triggered automatically after movement creation
@receiver(post_save, sender=StockMovement)
def update_stock_balance(sender, instance, created, **kwargs):
    # Updates balance for affected godown
```

**Rules:**
- IN movements: Add to balance
- OUT movements: Subtract from balance
- Transfers: Update both source and destination

### Company Scoping

**All data is company-scoped:**
- Cannot access other companies' items/stock
- Automatic filtering by active_company
- Company field auto-populated on create

---

## Error Handling

### Common Errors

#### 400 Bad Request - Insufficient Stock
```json
{
  "error": "Insufficient stock for Product A at Main Warehouse: available 5.000, required 10.000"
}
```

#### 400 Bad Request - Validation Error
```json
{
  "error": "Transfer quantity must be positive"
}
```

#### 400 Bad Request - Same Godown Transfer
```json
{
  "error": "Source and destination godowns must be different"
}
```

#### 404 Not Found - Item Not Found
```json
{
  "error": "Stock item {id} not found"
}
```

#### 403 Forbidden - Insufficient Permissions
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**Required Roles:**
- `ADMIN`: All operations
- `INVENTORY_MANAGER`: Create movements, transfers
- Other roles: Read-only access

---

## Code Examples

### Python (requests)

```python
import requests

# Login
response = requests.post('http://api/auth/login/', json={
    'username': 'inventory@company.com',
    'password': 'secret'
})
token = response.json()['access']
headers = {'Authorization': f'Bearer {token}'}

# Get stock balance
response = requests.get(
    'http://api/inventory/balance/',
    params={'item': 'item-uuid', 'godown': 'godown-uuid'},
    headers=headers
)
balance = response.json()
print(f"Current stock: {balance['quantity']}")

# Create stock transfer
response = requests.post(
    'http://api/inventory/transfers/',
    json={
        'item_id': 'item-uuid',
        'from_godown_id': 'warehouse-uuid',
        'to_godown_id': 'store-uuid',
        'quantity': '25.000',
        'reason': 'Rebalancing'
    },
    headers=headers
)
transfer = response.json()
print(f"Transfer status: {transfer['status']}")
```

### JavaScript (fetch)

```javascript
// Get auth token
const loginResponse = await fetch('http://api/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'inventory@company.com',
    password: 'secret'
  })
});
const { access } = await loginResponse.json();

// List stock items
const itemsResponse = await fetch('http://api/inventory/items/', {
  headers: { 'Authorization': `Bearer ${access}` }
});
const items = await itemsResponse.json();
console.log('Stock items:', items.results);

// Create stock movement (IN)
const movementResponse = await fetch('http://api/inventory/movements/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${access}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    item_id: 'item-uuid',
    godown_id: 'warehouse-uuid',
    quantity: '50.000',
    movement_type: 'IN',
    reason: 'Purchase receipt'
  })
});
const movement = await movementResponse.json();
console.log('Movement created:', movement);
```

---

## API Endpoint Summary

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| **Stock Items** |
| GET | `/api/inventory/items/` | List all items | ✅ |
| POST | `/api/inventory/items/` | Create item | ✅ |
| GET | `/api/inventory/items/{id}/` | Get item details | ✅ |
| PATCH | `/api/inventory/items/{id}/` | Update item | ✅ |
| DELETE | `/api/inventory/items/{id}/` | Delete item | ✅ |
| GET | `/api/inventory/items/{id}/stock_summary/` | Get stock summary | ✅ |
| GET | `/api/inventory/items/{id}/movements/` | Get movement history | ✅ |
| **Godowns** |
| GET | `/api/inventory/godowns/` | List godowns | ✅ |
| POST | `/api/inventory/godowns/` | Create godown | ✅ |
| GET | `/api/inventory/godowns/{id}/` | Get godown details | ✅ |
| PATCH | `/api/inventory/godowns/{id}/` | Update godown | ✅ |
| DELETE | `/api/inventory/godowns/{id}/` | Delete godown | ✅ |
| **Stock Balance** |
| GET | `/api/inventory/balance/` | Get item balance | ✅ |
| GET | `/api/inventory/balances/` | List all balances | ✅ |
| **Stock Movements** |
| GET | `/api/inventory/movements/` | List movements | ✅ |
| POST | `/api/inventory/movements/` | Create movement | ✅ ADMIN/INV_MGR |
| **Stock Transfers** |
| GET | `/api/inventory/transfers/` | List transfers | ✅ |
| POST | `/api/inventory/transfers/` | Create transfer | ✅ ADMIN/INV_MGR |
| **Reservations** |
| GET | `/api/inventory/reservations/` | List reservations | ✅ |
| POST | `/api/inventory/reservations/` | Create reservation | ✅ |

---

## Implementation Checklist

- ✅ Selectors (read-only data access)
- ✅ Negative stock guard (automatic validation)
- ✅ Stock transfer service (atomic transactions)
- ✅ API serializers (DRF)
- ✅ API views with permissions
- ✅ URL routing configured
- ✅ Signals (auto-update balances)
- ✅ Signal registration in apps.py
- ✅ Wired into main API routing
- ✅ Complete documentation

---

## Architecture Notes

**Service Layer:**
- `selectors.py`: Read-only queries (safe, company-scoped)
- `services/guards.py`: Business rule validation
- `services/transfers.py`: Stock transfer logic

**API Layer:**
- `api/serializers.py`: DRF serializers
- `api/views.py`: RESTful endpoints
- `api/urls.py`: URL routing

**Data Layer:**
- `signals.py`: Auto-update balances
- `models.py`: Database schema

**Flow:**
1. API request → View validates → Service executes
2. Service checks guards → Creates movement
3. Signal triggers → Updates balance
4. Response returned

---

## Related Documentation

- **Authentication:** [AUTH_LAYER_QUICKREF.md](AUTH_LAYER_QUICKREF.md)
- **Accounting:** [LEDGER_API_QUICKREF.md](LEDGER_API_QUICKREF.md)
- **Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

---

**Last Updated:** December 26, 2025  
**Version:** 1.0.0  
**Status:** ✅ Production Ready
