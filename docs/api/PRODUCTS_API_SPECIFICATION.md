# Products Catalog API - Frontend Integration Specification

**API Version**: 1.0  
**Base URL**: `http://your-domain.com`  
**Date**: December 26, 2025  
**Status**: Production Ready

## Table of Contents
1. [Authentication](#authentication)
2. [Category Endpoints](#category-endpoints)
3. [Product Endpoints](#product-endpoints)
4. [Error Responses](#error-responses)
5. [Field Specifications](#field-specifications)

---

## Authentication

All endpoints require authentication via Bearer token.

**Headers Required**:
```http
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
```

---

## Category Endpoints

### 1. List All Categories

**Endpoint**: `GET /api/catalog/categories/`

**Request**: No body required

**Response** (200 OK):
```json
{
  "categories": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "Building Materials",
      "description": "Construction and building materials",
      "is_active": true,
      "display_order": 1,
      "product_count": 15,
      "created_at": "2025-12-26T10:00:00Z",
      "updated_at": "2025-12-26T10:30:00Z"
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "Electrical",
      "description": "Electrical supplies and equipment",
      "is_active": true,
      "display_order": 2,
      "product_count": 8,
      "created_at": "2025-12-26T11:00:00Z",
      "updated_at": "2025-12-26T11:00:00Z"
    }
  ],
  "count": 2
}
```

---

### 2. Create Category

**Endpoint**: `POST /api/catalog/categories/`

**Request Body**:
```json
{
  "name": "Building Materials",
  "description": "Construction and building materials",
  "is_active": true,
  "display_order": 1
}
```

**Field Requirements**:
| Field | Type | Required | Max Length | Notes |
|-------|------|----------|------------|-------|
| name | string | Yes | 255 | Unique per company |
| description | string | No | unlimited | Can be empty |
| is_active | boolean | No | - | Default: true |
| display_order | integer | No | - | Default: 0, for sorting |

**Response** (201 Created):
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Building Materials",
  "description": "Construction and building materials",
  "is_active": true,
  "display_order": 1,
  "product_count": 0,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:00:00Z"
}
```

**Error Response** (400 Bad Request):
```json
{
  "name": ["This field is required."]
}
```

---

### 3. Get Category Detail

**Endpoint**: `GET /api/catalog/categories/{category_id}/`

**URL Parameters**:
- `category_id` (UUID) - The category UUID

**Request**: No body required

**Response** (200 OK):
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Building Materials",
  "description": "Construction and building materials",
  "is_active": true,
  "display_order": 1,
  "product_count": 15,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:30:00Z"
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "Category not found"
}
```

---

### 4. Update Category (Full)

**Endpoint**: `PUT /api/catalog/categories/{category_id}/`

**URL Parameters**:
- `category_id` (UUID) - The category UUID

**Request Body** (all fields required):
```json
{
  "name": "Building Materials Updated",
  "description": "Updated description for construction materials",
  "is_active": true,
  "display_order": 1
}
```

**Response** (200 OK):
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Building Materials Updated",
  "description": "Updated description for construction materials",
  "is_active": true,
  "display_order": 1,
  "product_count": 15,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T11:00:00Z"
}
```

---

### 5. Update Category (Partial)

**Endpoint**: `PATCH /api/catalog/categories/{category_id}/`

**URL Parameters**:
- `category_id` (UUID) - The category UUID

**Request Body** (only fields to update):
```json
{
  "is_active": false
}
```

**Response** (200 OK):
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Building Materials",
  "description": "Construction and building materials",
  "is_active": false,
  "display_order": 1,
  "product_count": 15,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T11:30:00Z"
}
```

---

### 6. Delete Category

**Endpoint**: `DELETE /api/catalog/categories/{category_id}/`

**URL Parameters**:
- `category_id` (UUID) - The category UUID

**Request**: No body required

**Response** (204 No Content): Empty body

**Error Response** (400 Bad Request) - If category has products:
```json
{
  "error": "Cannot delete category with products. Move or delete products first."
}
```

---

## Product Endpoints

### 7. List Products (with Filters)

**Endpoint**: `GET /api/catalog/products/`

**Query Parameters** (all optional):
| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| q | string | Search in name, brand, description | `?q=cement` |
| category_id | UUID | Filter by category | `?category_id=f47ac10b...` |
| brand | string | Filter by brand | `?brand=UltraTech` |
| status | string | available, out_of_stock, on_demand, discontinued | `?status=available` |
| is_portal_visible | boolean | true/false | `?is_portal_visible=true` |
| is_featured | boolean | true/false | `?is_featured=true` |
| limit | integer | Max results (default: 100, max: 500) | `?limit=50` |

**Request**: No body required

**Example URL**:
```
GET /api/catalog/products/?q=cement&category_id=f47ac10b-58cc-4372-a567-0e02b2c3d479&status=available&limit=20
```

**Response** (200 OK):
```json
{
  "products": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "Portland Cement 53 Grade",
      "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "category_name": "Building Materials",
      "brand": "UltraTech",
      "available_quantity": 1000,
      "unit": "BAG",
      "price": "450.00",
      "status": "available",
      "is_portal_visible": true,
      "is_featured": true,
      "created_at": "2025-12-26T10:00:00Z"
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "PPC Cement",
      "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "category_name": "Building Materials",
      "brand": "ACC",
      "available_quantity": 500,
      "unit": "BAG",
      "price": "420.00",
      "status": "available",
      "is_portal_visible": true,
      "is_featured": false,
      "created_at": "2025-12-26T10:15:00Z"
    }
  ],
  "count": 2
}
```

---

### 8. Create Product

**Endpoint**: `POST /api/catalog/products/`

**Request Body**:
```json
{
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "description": "High-strength Portland cement for construction",
  "brand": "UltraTech",
  "unit": "BAG",
  "price": "450.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": true,
  "status": "available"
}
```

**Field Requirements**:
| Field | Type | Required | Max Length | Notes |
|-------|------|----------|------------|-------|
| name | string | Yes | 255 | Unique per company |
| category_id | UUID | No | - | Must belong to same company, can be null |
| description | string | No | unlimited | Can be empty |
| brand | string | No | 100 | Manufacturer/brand name |
| unit | string | No | 10 | Default: "PCS", See UQC choices below |
| price | decimal | No | - | Default: 0.00, max digits: 10, decimals: 2 |
| hsn_code | string | No | 10 | Default: "0000", HSN/SAC code for GST |
| cgst_rate | decimal | No | - | Default: 0.00, max digits: 5, decimals: 2 |
| sgst_rate | decimal | No | - | Default: 0.00, max digits: 5, decimals: 2 |
| igst_rate | decimal | No | - | Default: 0.00, max digits: 5, decimals: 2 |
| cess_rate | decimal | No | - | Default: 0.00, max digits: 5, decimals: 2 |
| is_portal_visible | boolean | No | - | Default: true |
| is_featured | boolean | No | - | Default: false |
| status | string | No | 20 | Default: "available", choices below |

**Status Choices**:
- `"available"` - Product is available
- `"out_of_stock"` - Out of stock
- `"on_demand"` - Available on demand
- `"discontinued"` - No longer available

**Unit Choices (UQC)**: BAG, BAL, BDL, BKL, BOU, BOX, BTL, BUN, CAN, CBM, CCM, CMS, CTN, DOZ, DRM, GGK, GMS, GRS, GYD, KGS, KLR, KME, LTR, MTR, MLT, MTS, NOS, PAC, PCS, PRS, QTL, ROL, SET, SQF, SQM, SQY, TBS, TGM, THD, TON, TUB, UGS, UNT, YDS

**Response** (201 Created):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Building Materials",
  "description": "High-strength Portland cement for construction",
  "brand": "UltraTech",
  "available_quantity": 0,
  "unit": "BAG",
  "total_shipped": 0,
  "total_required_quantity": 0,
  "price": "450.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": true,
  "status": "available",
  "created_by_id": "98765432-abcd-ef12-3456-7890abcdef12",
  "created_by_name": "John Doe",
  "stock_item_count": 0,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:00:00Z"
}
```

**Error Response** (400 Bad Request):
```json
{
  "name": ["This field is required."],
  "price": ["A valid number is required."]
}
```

**Error Response** (400 Bad Request) - Invalid category:
```json
{
  "category_id": ["Category not found or doesn't belong to your company."]
}
```

---

### 9. Get Product Detail

**Endpoint**: `GET /api/catalog/products/{product_id}/`

**URL Parameters**:
- `product_id` (UUID) - The product UUID

**Request**: No body required

**Response** (200 OK):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Building Materials",
  "description": "High-strength Portland cement for construction",
  "brand": "UltraTech",
  "available_quantity": 1000,
  "unit": "BAG",
  "total_shipped": 5000,
  "total_required_quantity": 500,
  "price": "450.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": true,
  "status": "available",
  "created_by_id": "98765432-abcd-ef12-3456-7890abcdef12",
  "created_by_name": "John Doe",
  "stock_item_count": 3,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T10:30:00Z"
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "Product not found"
}
```

---

### 10. Update Product (Full)

**Endpoint**: `PUT /api/catalog/products/{product_id}/`

**URL Parameters**:
- `product_id` (UUID) - The product UUID

**Request Body** (all fields required except category_id):
```json
{
  "name": "Portland Cement 53 Grade - Premium",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "description": "Premium high-strength Portland cement",
  "brand": "UltraTech",
  "unit": "BAG",
  "price": "475.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": true,
  "status": "available"
}
```

**Response** (200 OK):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade - Premium",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Building Materials",
  "description": "Premium high-strength Portland cement",
  "brand": "UltraTech",
  "available_quantity": 1000,
  "unit": "BAG",
  "total_shipped": 5000,
  "total_required_quantity": 500,
  "price": "475.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": true,
  "status": "available",
  "created_by_id": "98765432-abcd-ef12-3456-7890abcdef12",
  "created_by_name": "John Doe",
  "stock_item_count": 3,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T11:00:00Z"
}
```

---

### 11. Update Product (Partial)

**Endpoint**: `PATCH /api/catalog/products/{product_id}/`

**URL Parameters**:
- `product_id` (UUID) - The product UUID

**Request Body** (only fields to update):
```json
{
  "price": "475.00",
  "is_featured": false
}
```

**Example - Update only price**:
```json
{
  "price": "475.00"
}
```

**Example - Hide from portal**:
```json
{
  "is_portal_visible": false
}
```

**Example - Remove category**:
```json
{
  "category_id": null
}
```

**Response** (200 OK):
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Building Materials",
  "description": "High-strength Portland cement for construction",
  "brand": "UltraTech",
  "available_quantity": 1000,
  "unit": "BAG",
  "total_shipped": 5000,
  "total_required_quantity": 500,
  "price": "475.00",
  "hsn_code": "2523",
  "cgst_rate": "9.00",
  "sgst_rate": "9.00",
  "igst_rate": "18.00",
  "cess_rate": "0.00",
  "is_portal_visible": true,
  "is_featured": false,
  "status": "available",
  "created_by_id": "98765432-abcd-ef12-3456-7890abcdef12",
  "created_by_name": "John Doe",
  "stock_item_count": 3,
  "created_at": "2025-12-26T10:00:00Z",
  "updated_at": "2025-12-26T11:30:00Z"
}
```

---

### 12. Delete Product

**Endpoint**: `DELETE /api/catalog/products/{product_id}/`

**URL Parameters**:
- `product_id` (UUID) - The product UUID

**Request**: No body required

**Response** (204 No Content): Empty body

**Error Response** (400 Bad Request) - If product has linked stock items:
```json
{
  "error": "Cannot delete product with linked stock items.",
  "suggestion": "Set is_portal_visible=False to hide instead."
}
```

---

### 13. Sync Product Stock

**Endpoint**: `POST /api/catalog/products/{product_id}/sync-stock/`

**URL Parameters**:
- `product_id` (UUID) - The product UUID

**Request**: No body required

**Description**: Updates `available_quantity` and `status` from linked stock items

**Response** (200 OK):
```json
{
  "message": "Stock synced successfully",
  "product": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "company_id": "12345678-1234-1234-1234-123456789012",
    "name": "Portland Cement 53 Grade",
    "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "category_name": "Building Materials",
    "description": "High-strength Portland cement for construction",
    "brand": "UltraTech",
    "available_quantity": 1500,
    "unit": "BAG",
    "total_shipped": 5000,
    "total_required_quantity": 500,
    "price": "450.00",
    "hsn_code": "2523",
    "cgst_rate": "9.00",
    "sgst_rate": "9.00",
    "igst_rate": "18.00",
    "cess_rate": "0.00",
    "is_portal_visible": true,
    "is_featured": true,
    "status": "available",
    "created_by_id": "98765432-abcd-ef12-3456-7890abcdef12",
    "created_by_name": "John Doe",
    "stock_item_count": 3,
    "created_at": "2025-12-26T10:00:00Z",
    "updated_at": "2025-12-26T12:00:00Z"
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "Product not found"
}
```

---

## Error Responses

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 204 | No Content | Resource deleted successfully |
| 400 | Bad Request | Validation error or invalid data |
| 401 | Unauthorized | Missing or invalid authentication token |
| 403 | Forbidden | User doesn't have permission |
| 404 | Not Found | Resource not found or doesn't belong to company |
| 500 | Server Error | Internal server error |

### Error Response Format

**Validation Errors** (400):
```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Error message"]
}
```

**Example**:
```json
{
  "name": ["This field is required."],
  "price": ["Ensure that there are no more than 10 digits in total."],
  "cgst_rate": ["Ensure that there are no more than 2 decimal places."]
}
```

**General Errors** (400, 404, 500):
```json
{
  "error": "Descriptive error message"
}
```

**Authentication Error** (401):
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**Forbidden Error** (403):
```json
{
  "detail": "You do not have permission to perform this action."
}
```

---

## Field Specifications

### Data Types

| Type | Description | Example |
|------|-------------|---------|
| UUID | Universally Unique Identifier | `"f47ac10b-58cc-4372-a567-0e02b2c3d479"` |
| string | Text field | `"Building Materials"` |
| integer | Whole number | `100` |
| decimal | Number with decimals | `"450.00"` (sent as string) |
| boolean | true or false | `true` or `false` |
| datetime | ISO 8601 format | `"2025-12-26T10:00:00Z"` |

### Important Notes

1. **UUID Fields**: All IDs (id, company_id, category_id, product_id, created_by_id) are UUID strings in format `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

2. **Decimal Fields**: Price and tax rate fields should be sent as strings with up to 2 decimal places:
   - Correct: `"450.00"`, `"9.50"`
   - Incorrect: `450` (number), `"450"` (no decimals)

3. **DateTime Fields**: All datetime fields are in ISO 8601 format with UTC timezone

4. **Read-Only Fields**: These fields are automatically set by the system and cannot be modified:
   - `id`, `company_id`, `created_at`, `updated_at`
   - `category_name`, `created_by_name`, `stock_item_count`
   - `available_quantity`, `total_shipped`, `total_required_quantity` (managed by system)

5. **Unique Constraints**:
   - Category `name` must be unique per company
   - Product `name` must be unique per company

6. **Company Scoping**: All requests automatically filter by the authenticated user's company. You cannot access or modify resources from other companies.

7. **Null Values**: 
   - `category_id` can be `null` for uncategorized products
   - `description` can be empty string `""`
   - `brand` can be empty string `""`

---

## Complete Unit Choices (UQC)

Available values for the `unit` field:

| Code | Description | Code | Description |
|------|-------------|------|-------------|
| BAG | Bags | BAL | Bale |
| BDL | Bundles | BKL | Buckles |
| BOU | Billions of Units | BOX | Box |
| BTL | Bottles | BUN | Bunches |
| CAN | Cans | CBM | Cubic Meter |
| CCM | Cubic Centimeter | CMS | Centimeters |
| CTN | Cartons | DOZ | Dozens |
| DRM | Drums | GGK | Great Gross |
| GMS | Grams | GRS | Gross |
| GYD | Gross Yards | KGS | Kilograms |
| KLR | Kilolitre | KME | Kilometre |
| LTR | Litre | MTR | Meters |
| MLT | Millilitre | MTS | Metric Ton |
| NOS | Numbers | PAC | Packs |
| PCS | Pieces | PRS | Pairs |
| QTL | Quintal | ROL | Rolls |
| SET | Sets | SQF | Square Feet |
| SQM | Square Meter | SQY | Square Yards |
| TBS | Tablets | TGM | Ten Grams |
| THD | Thousands | TON | Tonne |
| TUB | Tubes | UGS | US Gallons |
| UNT | Units | YDS | Yards |

---

## Quick Reference - Request/Response Summary

| Endpoint | Method | Request Body | Response |
|----------|--------|--------------|----------|
| `/api/catalog/categories/` | GET | None | List of categories |
| `/api/catalog/categories/` | POST | Category fields | Created category |
| `/api/catalog/categories/{id}/` | GET | None | Category detail |
| `/api/catalog/categories/{id}/` | PUT | All category fields | Updated category |
| `/api/catalog/categories/{id}/` | PATCH | Partial category fields | Updated category |
| `/api/catalog/categories/{id}/` | DELETE | None | Empty (204) |
| `/api/catalog/products/` | GET | None (query params) | List of products |
| `/api/catalog/products/` | POST | Product fields | Created product |
| `/api/catalog/products/{id}/` | GET | None | Product detail |
| `/api/catalog/products/{id}/` | PUT | All product fields | Updated product |
| `/api/catalog/products/{id}/` | PATCH | Partial product fields | Updated product |
| `/api/catalog/products/{id}/` | DELETE | None | Empty (204) |
| `/api/catalog/products/{id}/sync-stock/` | POST | None | Synced product |

---

## TypeScript Interfaces

For frontend TypeScript projects:

```typescript
// Category Interface
interface Category {
  id: string;
  company_id: string;
  name: string;
  description: string;
  is_active: boolean;
  display_order: number;
  product_count?: number;
  created_at: string;
  updated_at: string;
}

// Category Create/Update
interface CategoryInput {
  name: string;
  description?: string;
  is_active?: boolean;
  display_order?: number;
}

// Product List Item
interface ProductListItem {
  id: string;
  company_id: string;
  name: string;
  category_id: string | null;
  category_name: string | null;
  brand: string;
  available_quantity: number;
  unit: string;
  price: string;
  status: 'available' | 'out_of_stock' | 'on_demand' | 'discontinued';
  is_portal_visible: boolean;
  is_featured: boolean;
  created_at: string;
}

// Product Detail
interface Product {
  id: string;
  company_id: string;
  name: string;
  category_id: string | null;
  category_name: string | null;
  description: string;
  brand: string;
  available_quantity: number;
  unit: string;
  total_shipped: number;
  total_required_quantity: number;
  price: string;
  hsn_code: string;
  cgst_rate: string;
  sgst_rate: string;
  igst_rate: string;
  cess_rate: string;
  is_portal_visible: boolean;
  is_featured: boolean;
  status: 'available' | 'out_of_stock' | 'on_demand' | 'discontinued';
  created_by_id: string | null;
  created_by_name: string | null;
  stock_item_count: number;
  created_at: string;
  updated_at: string;
}

// Product Create/Update
interface ProductInput {
  name: string;
  category_id?: string | null;
  description?: string;
  brand?: string;
  unit?: string;
  price?: string;
  hsn_code?: string;
  cgst_rate?: string;
  sgst_rate?: string;
  igst_rate?: string;
  cess_rate?: string;
  is_portal_visible?: boolean;
  is_featured?: boolean;
  status?: 'available' | 'out_of_stock' | 'on_demand' | 'discontinued';
}

// API Responses
interface CategoryListResponse {
  categories: Category[];
  count: number;
}

interface ProductListResponse {
  products: ProductListItem[];
  count: number;
}

interface SyncStockResponse {
  message: string;
  product: Product;
}

interface ErrorResponse {
  error?: string;
  detail?: string;
  [key: string]: any;
}
```

---

## Testing Checklist

Before integrating:

- [ ] Test authentication with bearer token
- [ ] Test category list endpoint
- [ ] Test category create with all fields
- [ ] Test category update (PUT and PATCH)
- [ ] Test category delete (with and without products)
- [ ] Test product list without filters
- [ ] Test product list with each filter type
- [ ] Test product create with all fields
- [ ] Test product create without optional fields
- [ ] Test product detail endpoint
- [ ] Test product update (PUT and PATCH)
- [ ] Test product delete
- [ ] Test sync stock endpoint
- [ ] Test error responses (400, 401, 404)
- [ ] Verify UUID handling in URLs
- [ ] Verify decimal number formatting
- [ ] Test null category_id handling
- [ ] Test company scoping (cannot access other companies' data)

---

**Document Version**: 1.0  
**Last Updated**: December 26, 2025  
**Status**: Production Ready ✅

For questions or issues, refer to:
- Backend API implementation: `apps/products/api/`
- Model definitions: `apps/products/models.py`
- Serializer definitions: `apps/products/api/serializers.py`
