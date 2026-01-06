# Product vs StockItem Architecture

**Last Updated**: December 26, 2025  
**Status**: 🟢 ACTIVE DESIGN PATTERN

---

## Overview

The Vendor ERP maintains two distinct but related concepts for items:

1. **`products.Product`** - Marketing/Catalog Layer (B2B Portal facing)
2. **`inventory.StockItem`** - ERP Stock Unit (Operations/Accounting)

This separation enables powerful B2B marketplace features while maintaining strict inventory control.

---

## Model Responsibilities

### 📦 products.Product - Catalog/Marketing Entity

**Purpose**: Customer-facing product information for portal ordering

**Location**: `apps/products/models.py`

**Responsibilities**:
- ✅ Product catalog for retailer portal
- ✅ Marketing metadata (name, description, images, brand)
- ✅ Product categorization for browsing
- ✅ GST/HSN codes for invoicing
- ✅ Base pricing visible to retailers
- ✅ Product visibility and availability status

**Key Fields**:
```python
class Product:
    name                     # Display name for customers
    category                 # Category (Cement, Steel, Paint)
    available_quantity       # Display stock (may be aggregate)
    unit                     # User-friendly UOM (KGS, PCS, BAG)
    price                    # Retail/list price
    hsn_code                 # GST HSN/SAC code
    cgst_rate, sgst_rate     # Tax rates
    status                   # on_demand, sufficient
    created_by               # User who created
```

**Used By**:
- 🌐 Retailer Portal (product browsing, search, cart)
- 📱 Mobile ordering app
- 🛒 Product catalog APIs
- 📊 Marketing reports
- 💰 Portal pricing display

**NOT Used For**:
- ❌ Stock movements/transactions
- ❌ FIFO/batch tracking
- ❌ Accounting vouchers
- ❌ Manufacturing BOM
- ❌ Warehouse operations

---

### 📊 inventory.StockItem - ERP Stock Unit

**Purpose**: Operational inventory tracking and accounting

**Location**: `apps/inventory/models.py`

**Responsibilities**:
- ✅ Stock movements and transactions
- ✅ FIFO/LIFO/batch tracking
- ✅ Warehouse (Godown) management
- ✅ Costing and valuation
- ✅ Manufacturing BOM components
- ✅ Purchase/Sales order line items
- ✅ Invoice line items
- ✅ Stock ledger posting

**Key Fields**:
```python
class StockItem(CompanyScopedModel):
    sku                      # Unique stock keeping unit code
    name                     # Internal item name
    description              # Technical description
    uom                      # FK to UnitOfMeasure (strict)
    is_stock_item            # True for goods, False for services
    is_active                # Active status
    
    # Related models:
    - StockBatch             # Batch/lot tracking
    - StockBalance           # Godown-wise balances
    - StockMovement          # Transactions (GRN, issue, transfer)
    - ItemPrice              # Price list rates
```

**Used By**:
- 📦 Warehouse operations (GRN, dispatch, transfer)
- 💰 Accounting vouchers (stock posting)
- 🏭 Manufacturing (BOM, production)
- 📋 Purchase/Sales orders (OrderItem FK)
- 📄 Invoices (InvoiceLine FK)
- 💵 FIFO costing and valuation
- 📊 Stock reports and analysis

**NOT Used For**:
- ❌ Portal product display (use Product)
- ❌ Marketing categorization
- ❌ Customer-facing descriptions

---

## Relationship Between Models

### Current Architecture (As-Is)

```
┌─────────────────────────────────────────────────┐
│  PORTAL LAYER (Customer Facing)                 │
├─────────────────────────────────────────────────┤
│                                                  │
│  products.Product                                │
│  ├── name: "Acme Cement 50kg Bag"               │
│  ├── category: Cement                            │
│  ├── available_quantity: 500                     │
│  ├── price: 320.00                               │
│  └── status: sufficient                          │
│                                                  │
└──────────────────┬──────────────────────────────┘
                   │ (Currently NO direct link)
                   ↓
┌─────────────────────────────────────────────────┐
│  ERP LAYER (Operations & Accounting)             │
├─────────────────────────────────────────────────┤
│                                                  │
│  inventory.StockItem                             │
│  ├── sku: "CEM-ACM-50"                          │
│  ├── name: "Acme Cement 50kg"                   │
│  ├── uom: FK → Bag                              │
│  ├── is_stock_item: True                        │
│  │                                               │
│  ├── StockBatch → Batch tracking                │
│  ├── StockBalance → Godown balances             │
│  └── StockMovement → Transactions               │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Proposed Architecture (To-Be)

```
┌─────────────────────────────────────────────────┐
│  PORTAL LAYER                                    │
├─────────────────────────────────────────────────┤
│                                                  │
│  products.Product (CompanyScopedModel, UUID)     │
│  ├── name: "Acme Cement 50kg Bag"               │
│  ├── category: FK → Category                    │
│  ├── brand: "Acme Industries"                   │
│  ├── description: "Premium Portland Cement"     │
│  ├── hsn_code: "2523"                           │
│  └── is_portal_visible: True                    │
│                                                  │
└──────────────────┬──────────────────────────────┘
                   │ FK: product → Product
                   ↓
┌─────────────────────────────────────────────────┐
│  ERP LAYER                                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  inventory.StockItem (CompanyScopedModel, UUID)  │
│  ├── product: FK → products.Product             │
│  ├── sku: "CEM-ACM-50"                          │
│  ├── name: "Acme Cement 50kg"                   │
│  ├── uom: FK → Bag                              │
│  └── related models...                          │
│                                                  │
└─────────────────────────────────────────────────┘
```

**Link Pattern**: `1 Product → Many StockItems` (variants, packs)

**Examples**:
- Product: "Acme Cement 50kg"
  - StockItem 1: SKU "CEM-ACM-50-BAG" (50kg bag)
  - StockItem 2: SKU "CEM-ACM-25-BAG" (25kg bag)
  
- Product: "Premium Steel TMT Bar"
  - StockItem 1: SKU "STEEL-TMT-8MM" (8mm diameter)
  - StockItem 2: SKU "STEEL-TMT-10MM" (10mm diameter)
  - StockItem 3: SKU "STEEL-TMT-12MM" (12mm diameter)

---

## Use Cases

### Use Case 1: Retailer Browses Portal

**Flow**:
1. Retailer logs into portal
2. Frontend queries: `GET /api/portal/products/?category=cement`
3. Returns `products.Product` list with:
   - Product name, image, description
   - Category for filtering
   - Available quantity (aggregated from StockItems)
   - Price (from default price list)
4. Retailer adds to cart

**Why Product?**: Clean, customer-friendly catalog without ERP complexity

---

### Use Case 2: Create Sales Order from Portal

**Flow**:
1. Retailer submits cart
2. Backend converts Product selection to StockItem:
   ```python
   # Portal sends:
   { "product_id": "uuid...", "quantity": 100 }
   
   # Backend creates OrderItem:
   OrderItem.objects.create(
       sales_order=order,
       item=StockItem.objects.get(product_id=product_id),  # Link via FK
       quantity=100
   )
   ```
3. OrderItem uses `inventory.StockItem` (FK)
4. Stock reservation happens on StockItem

**Why StockItem?**: Orders must track actual inventory units

---

### Use Case 3: Warehouse Receives Stock (GRN)

**Flow**:
1. Purchase Order issued for "Acme Cement 50kg"
2. GRN created with:
   ```python
   StockMovement.objects.create(
       item=stock_item,        # inventory.StockItem
       movement_type='RECEIPT',
       quantity=500,
       godown=warehouse_a,
       batch=batch_20250115
   )
   ```
3. StockBalance updated
4. Voucher posted to accounting

**Why StockItem?**: Warehouse tracks SKUs, batches, godowns - not marketing products

---

### Use Case 4: Multi-Variant Product

**Scenario**: "Asian Paints Apex" comes in 1L, 5L, 20L

**Setup**:
```python
# Single Product
product = Product.objects.create(
    name="Asian Paints Apex Interior Emulsion",
    category=paints_category,
    brand="Asian Paints"
)

# Multiple StockItems (variants)
StockItem.objects.create(
    product=product,
    sku="PAINT-APEX-1L",
    name="Apex 1 Litre",
    uom=litre
)

StockItem.objects.create(
    product=product,
    sku="PAINT-APEX-5L",
    name="Apex 5 Litre",
    uom=litre
)

StockItem.objects.create(
    product=product,
    sku="PAINT-APEX-20L",
    name="Apex 20 Litre",
    uom=litre
)
```

**Portal Display**: Shows single product "Asian Paints Apex" with variant selector (1L/5L/20L)

**Order Processing**: Creates OrderItem with specific StockItem SKU

---

## API Design

### Portal Product List API

**Endpoint**: `GET /api/portal/products/`

**Response**:
```json
{
  "results": [
    {
      "id": "uuid-123",
      "name": "Acme Cement 50kg Bag",
      "category": {
        "id": 1,
        "name": "Cement"
      },
      "price": 320.00,
      "available_quantity": 500,
      "unit": "BAG",
      "hsn_code": "2523",
      "status": "sufficient",
      "variants": [
        {
          "sku": "CEM-ACM-50",
          "size": "50kg",
          "stock_available": 500
        },
        {
          "sku": "CEM-ACM-25",
          "size": "25kg",
          "stock_available": 800
        }
      ]
    }
  ]
}
```

**Serializer**:
```python
class PortalProductSerializer(serializers.ModelSerializer):
    variants = StockItemVariantSerializer(many=True, source='stockitems')
    available_quantity = serializers.SerializerMethodField()
    
    def get_available_quantity(self, obj):
        # Aggregate from linked StockItems
        return obj.stockitems.aggregate(
            total=Sum('stock_balances__quantity_available')
        )['total'] or 0
```

---

### Order Creation API

**Endpoint**: `POST /api/orders/sales/`

**Request**:
```json
{
  "customer_id": "uuid...",
  "items": [
    {
      "product_id": "uuid-123",      // Portal sends Product ID
      "sku": "CEM-ACM-50",            // Selected variant SKU
      "quantity": 100
    }
  ]
}
```

**Backend Processing**:
```python
stock_item = StockItem.objects.get(
    product_id=item_data['product_id'],
    sku=item_data['sku']
)

OrderItem.objects.create(
    sales_order=order,
    item=stock_item,           # Uses StockItem, not Product
    quantity=item_data['quantity']
)
```

---

## Migration Strategy

### Phase 1: Add Product FK to StockItem

```python
# inventory/models.py
class StockItem(CompanyScopedModel):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        null=True,  # Nullable during migration
        blank=True,
        related_name='stockitems',
        help_text="Portal product this stock item belongs to"
    )
    # ... existing fields
```

### Phase 2: Data Migration

```python
# Create mapping: Product name → StockItem SKU
# Option A: Manual mapping via admin interface
# Option B: Auto-create Products from existing StockItems

def create_products_from_stockitems(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    StockItem = apps.get_model('inventory', 'StockItem')
    
    for stock_item in StockItem.objects.all():
        product, _ = Product.objects.get_or_create(
            company=stock_item.company,
            name=stock_item.name,
            defaults={
                'price': 0,  # Set manually later
                'available_quantity': 0
            }
        )
        stock_item.product = product
        stock_item.save()
```

### Phase 3: Make FK Required (After Backfill)

```python
# inventory/models.py
class StockItem(CompanyScopedModel):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        null=False,  # Now required
        related_name='stockitems'
    )
```

---

## Decision Matrix: When to Use Which Model

| Scenario | Use Product | Use StockItem | Reason |
|----------|-------------|---------------|--------|
| Portal product catalog | ✅ | ❌ | Customer-facing |
| Portal search/filter | ✅ | ❌ | Marketing categories |
| Add to cart | ✅ | ❌ | Customer selection |
| Create order line | ❌ | ✅ | Inventory tracking |
| Stock movement | ❌ | ✅ | Warehouse ops |
| FIFO/batch tracking | ❌ | ✅ | ERP functionality |
| Accounting voucher | ❌ | ✅ | Financial posting |
| Price list rates | ❌ | ✅ | Operational pricing |
| Invoice line items | ❌ | ✅ | Accounting integration |
| Manufacturing BOM | ❌ | ✅ | Production planning |
| Stock valuation | ❌ | ✅ | Accounting reports |
| Portal pricing display | ✅ | ❌ | Marketing price |

---

## Alternative Strategies (Not Recommended)

### Strategy A: Merge into Single Model
**Approach**: Use only StockItem, add portal fields

**Pros**: Simpler schema, no dual management

**Cons**: 
- ❌ Weak portal UX (technical SKUs visible)
- ❌ Complex variant handling
- ❌ Marketing vs ops concerns mixed
- ❌ Portal queries hit operational tables

**Verdict**: ❌ Not recommended for B2B marketplace

---

### Strategy B: Product as Alias/View
**Approach**: Product is a database view over StockItem

**Pros**: No data duplication

**Cons**:
- ❌ Can't have multiple StockItems per Product
- ❌ No variant support
- ❌ Complex aggregations

**Verdict**: ❌ Too limiting

---

### Strategy C: ProductVariant Model
**Approach**: Product → ProductVariant → StockItem (3 levels)

**Pros**: Ultimate flexibility (color, size, pack variants)

**Cons**:
- ❌ Over-engineered for construction materials
- ❌ Adds complexity
- ❌ May be needed for fashion/FMCG later

**Verdict**: 🟡 Consider for future expansion

---

## Conclusion

**Recommended Architecture**: **Keep Separate + Add FK Link**

```
Product (portal catalog) → StockItem (ERP stock) → Transactions
```

**Benefits**:
1. ✅ Clean separation of concerns
2. ✅ Portal UX optimized separately
3. ✅ ERP operations unaffected
4. ✅ Multi-variant support
5. ✅ Scalable for marketplace features
6. ✅ Marketing independence from SKU changes

**Next Steps**:
1. ✅ Refactor Product/Category to CompanyScopedModel (Phase B)
2. ✅ Add product FK to StockItem
3. ✅ Migrate existing data
4. ✅ Update portal APIs to use Product
5. ✅ Update order creation to map Product → StockItem

---

**Document Owner**: Backend Team  
**Review Date**: March 2026  
**Status**: 🟢 Active Design Pattern
