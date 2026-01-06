# ORDER APIs — QUICK REFERENCE

## Overview

Complete RESTful APIs for managing Sales Orders and Purchase Orders in the ERP system.

**Features:**
- Create, read, update, delete orders
- Add/update/remove line items
- Confirm orders (reserve stock for sales)
- Cancel orders (release reservations)
- Multi-company scoping
- Role-based permissions
- Atomic transactions

**Base URL:** `/api/orders/`

---

## 🔑 Authentication

All endpoints require JWT authentication:

```
Authorization: Bearer <jwt_token>
```

Company context is derived from the user's active company.

---

## 📋 Sales Order Endpoints

### 1. List / Create Sales Orders

**GET** `/api/orders/sales/`

List all sales orders with optional filters.

**Query Parameters:**
- `status` - Filter by order status (DRAFT, CONFIRMED, etc.)
- `customer` - Filter by customer ID (UUID)
- `start_date` - Filter from date (YYYY-MM-DD)
- `end_date` - Filter to date (YYYY-MM-DD)

**Response:**
```json
[
  {
    "id": "uuid",
    "order_number": "SO-00001",
    "customer_name": "Customer Name",
    "currency_code": "USD",
    "status": "DRAFT",
    "order_date": "2025-12-26",
    "due_date": "2026-01-26",
    "item_count": 3,
    "created_at": "2025-12-26T10:00:00Z"
  }
]
```

**POST** `/api/orders/sales/`

Create a new sales order.

**Request:**
```json
{
  "customer_id": "uuid",
  "currency_id": "uuid",
  "price_list_id": "uuid",  // optional
  "order_date": "2025-12-26",  // optional, defaults to today
  "due_date": "2026-01-26",  // optional
  "shipping_address": "123 Main St",  // optional
  "billing_address": "123 Main St",  // optional
  "payment_terms": "Net 30",  // optional
  "notes": "Special instructions"  // optional
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "order_number": "SO-00001",
  "customer": "customer-uuid",
  "customer_name": "Customer Name",
  "currency": "currency-uuid",
  "currency_code": "USD",
  "status": "DRAFT",
  "order_date": "2025-12-26",
  "due_date": "2026-01-26",
  "items": [],
  "total_amount": "0.00",
  "created_at": "2025-12-26T10:00:00Z"
}
```

---

### 2. Get / Update / Delete Sales Order

**GET** `/api/orders/sales/{order_id}/`

Get sales order details with line items.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "order_number": "SO-00001",
  "customer": "customer-uuid",
  "customer_name": "Customer Name",
  "currency_code": "USD",
  "status": "DRAFT",
  "items": [
    {
      "id": "item-uuid",
      "item": "stock-item-uuid",
      "item_name": "Product A",
      "item_sku": "SKU001",
      "quantity": "10.000",
      "unit_rate": "100.00",
      "uom_name": "Piece",
      "discount_percent": "5.00",
      "line_total": "950.00"
    }
  ],
  "total_amount": "950.00"
}
```

**PATCH** `/api/orders/sales/{order_id}/`

Update order fields (only for DRAFT/PENDING orders).

**Request:**
```json
{
  "due_date": "2026-02-01",
  "notes": "Updated notes",
  "shipping_address": "New address"
}
```

**DELETE** `/api/orders/sales/{order_id}/`

Delete a draft sales order.

**Response:** `204 No Content`

---

### 3. Add Item to Sales Order

**POST** `/api/orders/sales/{order_id}/add_item/`

Add a line item to the order.

**Request:**
```json
{
  "item_id": "uuid",
  "quantity": "10.000",
  "override_rate": "95.00",  // optional
  "uom_id": "uuid",  // optional
  "discount_percent": "5.00",  // optional
  "notes": "Special item notes"  // optional
}
```

**Response:** `201 Created`
```json
{
  "id": "item-uuid",
  "item": "stock-item-uuid",
  "item_name": "Product A",
  "quantity": "10.000",
  "unit_rate": "95.00",
  "uom_name": "Piece",
  "discount_percent": "5.00",
  "line_total": "902.50"
}
```

---

### 4. Update Order Item

**PATCH** `/api/orders/sales/{order_id}/items/{item_id}/`

Update an existing line item.

**Request:**
```json
{
  "quantity": "15.000",
  "unit_rate": "98.00",
  "discount_percent": "10.00",
  "notes": "Updated notes"
}
```

**Response:** `200 OK` (updated item details)

---

### 5. Remove Order Item

**DELETE** `/api/orders/sales/{order_id}/items/{item_id}/remove/`

Remove a line item from the order.

**Response:** `204 No Content`

---

### 6. Confirm Sales Order

**POST** `/api/orders/sales/{order_id}/confirm/`

Confirm the order and reserve stock.

**Permissions:** Requires `ADMIN` or `SALES_MANAGER` role.

**Response:** `200 OK`
```json
{
  "order": {
    "id": "uuid",
    "order_number": "SO-00001",
    "status": "CONFIRMED",
    "confirmed_at": "2025-12-26T10:30:00Z"
  },
  "message": "Order confirmed and stock reserved",
  "reservations_count": 3
}
```

**Business Logic:**
- Validates order has items
- Creates stock reservations for all items
- Updates order status to `CONFIRMED`
- Records confirmation timestamp

---

### 7. Cancel Sales Order

**POST** `/api/orders/sales/{order_id}/cancel/`

Cancel the order and release stock reservations.

**Permissions:** Requires `ADMIN` or `SALES_MANAGER` role.

**Request:**
```json
{
  "reason": "Customer requested cancellation"
}
```

**Response:** `200 OK`
```json
{
  "order": {
    "id": "uuid",
    "order_number": "SO-00001",
    "status": "CANCELLED",
    "cancellation_reason": "Customer requested cancellation",
    "cancelled_at": "2025-12-26T11:00:00Z"
  },
  "message": "Order cancelled and reservations released"
}
```

---

## 📦 Purchase Order Endpoints

Purchase order endpoints follow the same pattern as sales orders with `/purchase/` path prefix.

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/orders/purchase/` | List purchase orders |
| POST | `/api/orders/purchase/` | Create purchase order |
| GET | `/api/orders/purchase/{order_id}/` | Get order details |
| PATCH | `/api/orders/purchase/{order_id}/` | Update order |
| DELETE | `/api/orders/purchase/{order_id}/` | Delete draft order |
| POST | `/api/orders/purchase/{order_id}/add_item/` | Add item |
| PATCH | `/api/orders/purchase/{order_id}/items/{item_id}/` | Update item |
| DELETE | `/api/orders/purchase/{order_id}/items/{item_id}/remove/` | Remove item |
| POST | `/api/orders/purchase/{order_id}/confirm/` | Confirm order |
| POST | `/api/orders/purchase/{order_id}/cancel/` | Cancel order |

### Key Differences from Sales Orders

1. **No Stock Reservations:** Purchase orders don't reserve stock on confirmation
2. **Supplier Field:** Uses `supplier_id` instead of `customer_id`
3. **Stock IN:** Stock is added when goods are received (separate receipt process)
4. **Permissions:** Requires `ADMIN` or `PURCHASE_MANAGER` role

---

## 🔒 Permissions & Roles

| Endpoint | Roles Required |
|----------|----------------|
| List/Create orders | Any authenticated user |
| Get order details | Any authenticated user |
| Update/Delete draft | Any authenticated user |
| Add/Update/Remove items | Any authenticated user |
| **Confirm order** | `ADMIN`, `SALES_MANAGER`, or `PURCHASE_MANAGER` |
| **Cancel order** | `ADMIN`, `SALES_MANAGER`, or `PURCHASE_MANAGER` |

---

## 📊 Order Status Flow

### Sales Order Lifecycle

```
DRAFT → CONFIRMED → IN_PROGRESS → INVOICED → COMPLETED
  ↓
CANCELLED (can cancel from DRAFT, PENDING, CONFIRMED)
```

### Purchase Order Lifecycle

```
DRAFT → CONFIRMED → IN_PROGRESS → RECEIVED → COMPLETED
  ↓
CANCELLED (can cancel from DRAFT, PENDING, CONFIRMED)
```

---

## 🔧 Business Rules

### Sales Orders

1. **Stock Reservation:**
   - Confirmed orders automatically reserve stock
   - Reservations prevent negative stock issues
   - Cancelled orders release all reservations

2. **Order Modification:**
   - Items can only be added/updated/removed in DRAFT or PENDING status
   - Confirmed orders cannot be modified (must cancel first)

3. **Order Deletion:**
   - Only DRAFT orders can be deleted
   - Confirmed/Invoiced orders must be cancelled instead

4. **Pricing:**
   - Uses price list rates if available
   - Falls back to item's opening rate
   - Can be overridden with `override_rate`

### Purchase Orders

1. **No Reservations:**
   - Purchase orders don't reserve stock
   - Stock is added when goods are physically received

2. **Receipt Process:**
   - Separate goods receipt creates stock IN movements
   - References original purchase order

---

## 🎯 Example Workflows

### Create Sales Order with Items

```python
import requests

base_url = "http://localhost:8000/api/orders"
headers = {"Authorization": f"Bearer {token}"}

# 1. Create order
order_data = {
    "customer_id": "customer-uuid",
    "currency_id": "currency-uuid",
    "price_list_id": "pricelist-uuid",
    "due_date": "2026-01-26"
}
response = requests.post(f"{base_url}/sales/", json=order_data, headers=headers)
order = response.json()
order_id = order["id"]

# 2. Add items
items = [
    {"item_id": "item1-uuid", "quantity": "10.000", "discount_percent": "5.00"},
    {"item_id": "item2-uuid", "quantity": "20.000"},
    {"item_id": "item3-uuid", "quantity": "5.000", "override_rate": "150.00"}
]

for item in items:
    requests.post(
        f"{base_url}/sales/{order_id}/add_item/",
        json=item,
        headers=headers
    )

# 3. Confirm order (reserve stock)
response = requests.post(
    f"{base_url}/sales/{order_id}/confirm/",
    headers=headers
)
print(response.json())  # Order confirmed, stock reserved
```

### Update Order Item Quantity

```python
# Update existing item
item_id = "order-item-uuid"
update_data = {
    "quantity": "25.000",
    "discount_percent": "10.00"
}

response = requests.patch(
    f"{base_url}/sales/{order_id}/items/{item_id}/",
    json=update_data,
    headers=headers
)
```

### Cancel Order

```python
# Cancel and release reservations
cancel_data = {"reason": "Customer changed their mind"}

response = requests.post(
    f"{base_url}/sales/{order_id}/cancel/",
    json=cancel_data,
    headers=headers
)
```

---

## ⚠️ Error Handling

### Common Error Responses

**400 Bad Request** - Validation error
```json
{
  "error": "Cannot add items to CONFIRMED order"
}
```

**404 Not Found** - Order or item not found
```json
{
  "error": "Sales order not found"
}
```

**403 Forbidden** - Insufficient permissions
```json
{
  "error": "Permission denied"
}
```

### Validation Errors

- Order must have items before confirmation
- Cannot modify confirmed orders
- Cannot add items after order is confirmed
- Stock must be available for confirmation
- Quantities must be positive

---

## 🧪 Testing Checklist

### Sales Order Tests

- [ ] Create draft order
- [ ] Add multiple items to order
- [ ] Update item quantity and rate
- [ ] Remove item from order
- [ ] Confirm order (verify stock reserved)
- [ ] Check stock reservations created
- [ ] Cancel order (verify reservations released)
- [ ] Try to modify confirmed order (should fail)
- [ ] Try to delete confirmed order (should fail)
- [ ] Filter orders by status
- [ ] Filter orders by customer
- [ ] Filter orders by date range

### Purchase Order Tests

- [ ] Create draft purchase order
- [ ] Add items with supplier rates
- [ ] Confirm purchase order
- [ ] Verify no stock reservations created
- [ ] Cancel purchase order
- [ ] Update order fields
- [ ] Delete draft order

---

## 🔗 Integration Points

### With Inventory System

- **Stock Reservations:** Sales orders create reservations on confirmation
- **Stock Movements:** Invoice posting creates actual OUT movements
- **Stock Balance:** Reservations reduce available stock

### With Accounting System (Phase 7)

- **Invoice Generation:** Confirmed orders can be invoiced
- **Voucher Posting:** Invoice creates voucher entries
- **Ledger Updates:** Updates customer/supplier ledgers

### With Party Management

- **Customer/Supplier Links:** Orders linked to parties
- **Credit Limits:** Can check customer credit before confirmation
- **Payment Terms:** Inherited from party or price list

---

## 📚 Service Layer Architecture

The Order APIs use a clean service layer pattern:

### Files Structure

```
apps/orders/
├── api/
│   ├── serializers.py      # DRF serializers for input/output
│   ├── views_sales.py       # Sales order API views
│   ├── views_purchase.py    # Purchase order API views
│   └── urls.py              # URL routing
├── services/
│   ├── sales_order_service.py    # Sales order business logic
│   ├── purchase_order_service.py # Purchase order business logic
│   └── reservations.py           # Stock reservation logic
├── models.py               # Order models
└── signals.py              # Order status change handlers
```

### Service Methods

**SalesOrderService:**
- `create_order()` - Create new order with sequence number
- `add_item()` - Add item with pricing logic
- `update_item()` - Update item quantities/rates
- `remove_item()` - Remove item and update totals
- `confirm_order()` - Confirm and reserve stock
- `cancel_order()` - Cancel and release reservations

**PurchaseOrderService:**
- Same methods as SalesOrderService
- No reservation logic (stock added on receipt)

---

## 🎉 Implementation Complete!

All order management endpoints are now live and ready for frontend integration. The system provides complete order lifecycle management from creation to fulfillment, with automatic stock reservations and multi-company isolation.

### Next Steps

1. **Test manually** with Postman/curl
2. **Integrate with frontend** cart/checkout flow
3. **Connect to invoicing** (Phase 7)
4. **Add receipt processing** for purchase orders
5. **Implement credit limit checks**
6. **Add email notifications** on status changes

---

**Documentation Version:** 1.0  
**Last Updated:** December 26, 2025  
**API Version:** Phase 6
