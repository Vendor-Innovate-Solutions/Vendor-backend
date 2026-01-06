# API Testing Guide - Products Catalog

Quick reference for testing Products API endpoints with Postman, curl, or HTTPie.

## Setup

**Base URL**: `http://localhost:8000`  
**Authentication**: Include auth token in headers  
**Content-Type**: `application/json`

```bash
# Headers for authenticated requests
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json
```

## Example Requests

### 1. List Categories

```bash
# curl
curl -X GET "http://localhost:8000/api/catalog/categories/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# HTTPie
http GET localhost:8000/api/catalog/categories/ \
  Authorization:"Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "categories": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "Building Materials",
      "description": "Construction materials",
      "is_active": true,
      "display_order": 1,
      "product_count": 15,
      "created_at": "2025-12-26T10:00:00Z",
      "updated_at": "2025-12-26T10:00:00Z"
    }
  ],
  "count": 1
}
```

### 2. Create Category

```bash
# curl
curl -X POST "http://localhost:8000/api/catalog/categories/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cement & Concrete",
    "description": "All types of cement and concrete products",
    "is_active": true,
    "display_order": 1
  }'

# HTTPie
http POST localhost:8000/api/catalog/categories/ \
  Authorization:"Bearer YOUR_TOKEN" \
  name="Cement & Concrete" \
  description="All types of cement" \
  is_active:=true \
  display_order:=1
```

### 3. Get Category Detail

```bash
# Replace {uuid} with actual category ID
curl -X GET "http://localhost:8000/api/catalog/categories/f47ac10b-58cc-4372-a567-0e02b2c3d479/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Update Category

```bash
# PUT - Full update
curl -X PUT "http://localhost:8000/api/catalog/categories/f47ac10b-58cc-4372-a567-0e02b2c3d479/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cement & Concrete Products",
    "description": "Updated description",
    "is_active": true,
    "display_order": 1
  }'

# PATCH - Partial update
curl -X PATCH "http://localhost:8000/api/catalog/categories/f47ac10b-58cc-4372-a567-0e02b2c3d479/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_active": false
  }'
```

### 5. Delete Category

```bash
curl -X DELETE "http://localhost:8000/api/catalog/categories/f47ac10b-58cc-4372-a567-0e02b2c3d479/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 6. List Products (with filters)

```bash
# All products
curl -X GET "http://localhost:8000/api/catalog/products/" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Search by name
curl -X GET "http://localhost:8000/api/catalog/products/?q=cement" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by category
curl -X GET "http://localhost:8000/api/catalog/products/?category_id=f47ac10b-58cc-4372-a567-0e02b2c3d479" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by brand
curl -X GET "http://localhost:8000/api/catalog/products/?brand=UltraTech" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by status
curl -X GET "http://localhost:8000/api/catalog/products/?status=available" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Portal visible only
curl -X GET "http://localhost:8000/api/catalog/products/?is_portal_visible=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Featured products
curl -X GET "http://localhost:8000/api/catalog/products/?is_featured=true" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Multiple filters
curl -X GET "http://localhost:8000/api/catalog/products/?category_id=f47ac10b-58cc-4372-a567-0e02b2c3d479&status=available&limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "products": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "company_id": "12345678-1234-1234-1234-123456789012",
      "name": "Portland Cement 53 Grade",
      "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "category_name": "Cement & Concrete",
      "brand": "UltraTech",
      "available_quantity": 1000,
      "unit": "BAG",
      "price": "450.00",
      "status": "available",
      "is_portal_visible": true,
      "is_featured": true,
      "created_at": "2025-12-26T10:00:00Z"
    }
  ],
  "count": 1
}
```

### 7. Create Product

```bash
curl -X POST "http://localhost:8000/api/catalog/products/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### 8. Get Product Detail

```bash
curl -X GET "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Cement & Concrete",
  "description": "High-strength Portland cement",
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

### 9. Update Product

```bash
# PUT - Full update
curl -X PUT "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Portland Cement 53 Grade - Premium",
    "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "description": "Premium high-strength cement",
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
  }'

# PATCH - Partial update (just price)
curl -X PATCH "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "price": "475.00"
  }'

# PATCH - Hide from portal
curl -X PATCH "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "is_portal_visible": false
  }'
```

### 10. Sync Stock from Items

```bash
curl -X POST "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/sync-stock/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "message": "Stock synced successfully",
  "product": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "available_quantity": 1500,
    "status": "available",
    ...
  }
}
```

### 11. Delete Product

```bash
curl -X DELETE "http://localhost:8000/api/catalog/products/a1b2c3d4-e5f6-7890-abcd-ef1234567890/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Error Responses

### 400 Bad Request
```json
{
  "name": ["This field is required."],
  "price": ["A valid number is required."]
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 404 Not Found
```json
{
  "error": "Product not found"
}
```

### 403 Forbidden (wrong company)
```json
{
  "error": "Category not found or doesn't belong to your company."
}
```

## Postman Collection

Import this JSON into Postman:

```json
{
  "info": {
    "name": "Products API",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {
      "key": "base_url",
      "value": "http://localhost:8000"
    },
    {
      "key": "category_id",
      "value": ""
    },
    {
      "key": "product_id",
      "value": ""
    }
  ],
  "item": [
    {
      "name": "Categories",
      "item": [
        {
          "name": "List Categories",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/api/catalog/categories/"
          }
        },
        {
          "name": "Create Category",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/catalog/categories/",
            "body": {
              "mode": "raw",
              "raw": "{\n  \"name\": \"Building Materials\",\n  \"description\": \"Construction materials\",\n  \"is_active\": true,\n  \"display_order\": 1\n}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            }
          }
        },
        {
          "name": "Get Category",
          "request": {
            "method": "GET",
            "url": "{{base_url}}/api/catalog/categories/{{category_id}}/"
          }
        }
      ]
    },
    {
      "name": "Products",
      "item": [
        {
          "name": "List Products",
          "request": {
            "method": "GET",
            "url": {
              "raw": "{{base_url}}/api/catalog/products/?q=&category_id=&status=available",
              "query": [
                {"key": "q", "value": ""},
                {"key": "category_id", "value": ""},
                {"key": "status", "value": "available"}
              ]
            }
          }
        },
        {
          "name": "Create Product",
          "request": {
            "method": "POST",
            "url": "{{base_url}}/api/catalog/products/",
            "body": {
              "mode": "raw",
              "raw": "{\n  \"name\": \"Portland Cement 53 Grade\",\n  \"brand\": \"UltraTech\",\n  \"unit\": \"BAG\",\n  \"price\": \"450.00\",\n  \"hsn_code\": \"2523\",\n  \"cgst_rate\": \"9.00\",\n  \"sgst_rate\": \"9.00\",\n  \"igst_rate\": \"18.00\",\n  \"is_portal_visible\": true,\n  \"status\": \"available\"\n}",
              "options": {
                "raw": {
                  "language": "json"
                }
              }
            }
          }
        }
      ]
    }
  ]
}
```

## Testing Tips

1. **Get Auth Token First**: Login and save token to environment variable
2. **Save UUIDs**: After creating, save category/product UUIDs for subsequent requests
3. **Test Filtering**: Try various query parameter combinations
4. **Test Validation**: Send invalid data to check error responses
5. **Test Permissions**: Try accessing other company's products (should fail)
6. **Test Cascade**: Try deleting category with products (should fail)

## Common Test Scenarios

1. **Create Category** → Save UUID → **Create Product** with that category
2. **List Products** → Filter by category → Verify count
3. **Update Product Price** → **Get Product** → Verify new price
4. **Hide Product** (is_portal_visible=false) → **List visible** → Verify not in list
5. **Sync Stock** → Check available_quantity updated

---

Happy Testing! 🚀
