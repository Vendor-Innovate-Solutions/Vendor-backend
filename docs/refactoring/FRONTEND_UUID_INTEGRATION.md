# Frontend Integration Guide - Products API with UUID

**Date**: December 26, 2025  
**Status**: Ready for Integration

## Overview

The Products API has been refactored to use UUID primary keys instead of integer IDs. All frontend code interacting with products, categories, and related entities must be updated to handle UUID strings.

## Key Changes

### Before (Integer IDs)
```javascript
// Old format
{
  "product_id": 123,
  "category_id": 45,
  "company_id": 1
}
```

### After (UUID Strings)
```javascript
// New format
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012"
}
```

## API Endpoints

### Base URL
```
/api/catalog/
```

### Category Endpoints

#### List/Create Categories
```http
GET  /api/catalog/categories/
POST /api/catalog/categories/
```

**Response Example:**
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

#### Category Detail
```http
GET    /api/catalog/categories/{uuid}/
PUT    /api/catalog/categories/{uuid}/
PATCH  /api/catalog/categories/{uuid}/
DELETE /api/catalog/categories/{uuid}/
```

### Product Endpoints

#### List/Create Products
```http
GET  /api/catalog/products/
POST /api/catalog/products/
```

**Query Parameters:**
- `q` - Search query (name, brand, description)
- `category_id` - Filter by category UUID
- `brand` - Filter by brand name
- `status` - Filter by status (available, out_of_stock, on_demand, discontinued)
- `is_portal_visible` - true/false
- `is_featured` - true/false
- `limit` - Max results (default: 100, max: 500)

**Response Example:**
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
    }
  ],
  "count": 1
}
```

#### Product Detail
```http
GET    /api/catalog/products/{uuid}/
PUT    /api/catalog/products/{uuid}/
PATCH  /api/catalog/products/{uuid}/
DELETE /api/catalog/products/{uuid}/
```

**Detailed Response:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "company_id": "12345678-1234-1234-1234-123456789012",
  "name": "Portland Cement 53 Grade",
  "category_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "category_name": "Building Materials",
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

#### Sync Stock
```http
POST /api/catalog/products/{uuid}/sync-stock/
```

Updates `available_quantity` and `status` from linked stock items.

## Frontend Code Changes

### 1. TypeScript/JavaScript Types

```typescript
// types/product.ts

// OLD
interface Product {
  product_id: number;
  category_id: number;
  company_id: number;
  name: string;
  // ...
}

// NEW
interface Product {
  id: string;  // UUID
  category_id: string | null;  // UUID
  company_id: string;  // UUID
  name: string;
  brand: string;
  description: string;
  available_quantity: number;
  unit: string;
  price: string;  // Decimal as string
  hsn_code: string;
  cgst_rate: string;
  sgst_rate: string;
  igst_rate: string;
  cess_rate: string;
  is_portal_visible: boolean;
  is_featured: boolean;
  status: 'available' | 'out_of_stock' | 'on_demand' | 'discontinued';
  created_at: string;
  updated_at: string;
}

interface Category {
  id: string;  // UUID
  company_id: string;  // UUID
  name: string;
  description: string;
  is_active: boolean;
  display_order: number;
  product_count?: number;
  created_at: string;
  updated_at: string;
}
```

### 2. React Components

```typescript
// components/ProductList.tsx

import { useState, useEffect } from 'react';
import { Product } from '@/types/product';

export function ProductList() {
  const [products, setProducts] = useState<Product[]>([]);

  useEffect(() => {
    fetch('/api/catalog/products/')
      .then(res => res.json())
      .then(data => setProducts(data.products));
  }, []);

  return (
    <div>
      {products.map(product => (
        // OLD: key={product.product_id}
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
```

### 3. API Calls

```typescript
// services/productService.ts

class ProductService {
  // Get product by UUID
  async getProduct(productId: string): Promise<Product> {
    const response = await fetch(`/api/catalog/products/${productId}/`);
    return response.json();
  }

  // Create product
  async createProduct(data: Partial<Product>): Promise<Product> {
    const response = await fetch('/api/catalog/products/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  }

  // Update product
  async updateProduct(productId: string, data: Partial<Product>): Promise<Product> {
    const response = await fetch(`/api/catalog/products/${productId}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return response.json();
  }

  // Delete product
  async deleteProduct(productId: string): Promise<void> {
    await fetch(`/api/catalog/products/${productId}/`, {
      method: 'DELETE'
    });
  }
}
```

### 4. URL Routing

```typescript
// React Router

// OLD
<Route path="/products/:productId" element={<ProductDetail />} />

// NEW (same syntax, but productId is now UUID string)
<Route path="/products/:productId" element={<ProductDetail />} />

// In component:
const { productId } = useParams<{ productId: string }>();
// productId will be: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
```

### 5. Comparisons and Filtering

```typescript
// Comparing UUIDs

// OLD
if (product.product_id === selectedId) { /* ... */ }

// NEW - String comparison (works the same)
if (product.id === selectedId) { /* ... */ }

// Filtering
const filteredProducts = products.filter(p => 
  p.category_id === selectedCategoryId  // String comparison
);

// ⚠️ IMPORTANT: Don't try to parse UUIDs as numbers!
// WRONG: parseInt(product.id)
// RIGHT: Just use as string
```

### 6. Local Storage / State Management

```typescript
// Redux/Zustand/etc.

// Store UUIDs as strings
interface AppState {
  selectedProductId: string | null;
  selectedCategoryId: string | null;
}

// localStorage
localStorage.setItem('selectedProduct', product.id);  // Stores UUID string
const productId = localStorage.getItem('selectedProduct');  // Returns UUID string
```

## Validation

### UUID Format
UUIDs are strings in format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

```typescript
// UUID validation regex
const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function isValidUUID(id: string): boolean {
  return UUID_REGEX.test(id);
}
```

## Common Pitfalls

### ❌ Don't Do This

```typescript
// 1. Don't parse UUIDs as numbers
const numericId = parseInt(product.id);  // ❌ Will fail

// 2. Don't use === with mixed types
if (product.id === 123) { /* ... */ }  // ❌ UUID is string

// 3. Don't try to increment UUIDs
const nextId = product.id + 1;  // ❌ Not how UUIDs work

// 4. Don't assume ordering
products.sort((a, b) => a.id - b.id);  // ❌ UUIDs aren't orderable
```

### ✅ Do This Instead

```typescript
// 1. Use UUIDs as strings
const productId = product.id;  // ✅ Just a string

// 2. String comparison
if (product.id === selectedId) { /* ... */ }  // ✅ Both strings

// 3. Use created_at for ordering
products.sort((a, b) => 
  new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
);  // ✅ Sort by timestamp

// 4. Use display_order for categories
categories.sort((a, b) => a.display_order - b.display_order);  // ✅
```

## Testing Checklist

- [ ] Update all product ID references from `product_id` to `id`
- [ ] Update all category ID references from `category_id` to `category_id` (field name same, but UUID)
- [ ] Change URL patterns from `/products/:id(\\d+)` to `/products/:id`
- [ ] Update TypeScript interfaces with UUID string types
- [ ] Test product list loading
- [ ] Test product detail page
- [ ] Test product create/update forms
- [ ] Test category filtering
- [ ] Test search functionality
- [ ] Test product deletion (check cascade rules)
- [ ] Update any bookmarks/favorites that store product IDs
- [ ] Update any analytics that track product IDs

## Migration Strategy

1. **Backend First** (✅ Complete)
   - Models migrated to UUID
   - Serializers updated
   - API endpoints ready

2. **Frontend Updates** (Your Task)
   - Update type definitions
   - Update API calls
   - Update components
   - Update routing

3. **Testing**
   - Test CRUD operations
   - Test filtering/search
   - Test edge cases

4. **Deployment**
   - Backend deploys first
   - Frontend deploys second
   - Monitor for errors

## Support

For issues or questions:
- Check model definitions: [apps/products/models.py](../apps/products/models.py)
- Check serializers: [apps/products/api/serializers.py](../apps/products/api/serializers.py)
- Check API views: [apps/products/api/views.py](../apps/products/api/views.py)
- See refactoring guide: [PRODUCTS_REFACTOR_GUIDE.md](PRODUCTS_REFACTOR_GUIDE.md)

---

**Ready for Frontend Integration** ✅  
All backend changes complete. Frontend can now consume UUID-based Product API.
