# Products App Refactoring Guide

**Last Updated**: December 26, 2025  
**Status**: 🔶 PLANNED REFACTORING  
**Estimated Effort**: 2-3 days  
**Risk Level**: MEDIUM (requires data migration)

---

## Overview

Refactor `apps/products/models.py` to align with system architecture:
1. Extend `CompanyScopedModel` instead of `models.Model`
2. Use UUID primary keys instead of auto-increment integers
3. Add proper constraints and indexing
4. Link to `inventory.StockItem` for ERP integration

---

## Current Issues

### ❌ Problem 1: Not Using Base Models

**Current**:
```python
class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=255, unique=True)
```

**Issue**: 
- Doesn't extend `CompanyScopedModel`
- Manual company FK instead of inheritance
- Uses auto-increment ID instead of UUID
- Missing `created_at`, `updated_at` timestamps
- `name` is globally unique (should be per-company)

---

### ❌ Problem 2: Product Model Inconsistency

**Current**:
```python
class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    company = models.ForeignKey('company.Company', on_delete=models.CASCADE, related_name="products")
    # ... many fields
```

**Issues**:
- Same as Category (not using CompanyScopedModel)
- Inconsistent with `inventory.StockItem` (which uses UUID)
- Breaks REST API consistency (mixing int and UUID IDs)
- Not future-proof for distributed systems

---

### ❌ Problem 3: No Link to StockItem

**Current**: Products and StockItems are completely separate

**Issue**: No way to:
- Map portal product to inventory SKU
- Show stock availability on product page
- Create orders from products
- Track variants (50kg bag vs 25kg bag)

---

## Refactoring Plan

### Phase B.1: Backup Current Data

**Before making any changes**, export existing data:

```bash
# Export products
python manage.py dumpdata products --indent 2 > backups/products_backup_$(date +%Y%m%d).json

# Export only specific company (if multi-tenant)
python manage.py dumpdata products --indent 2 --pks=1,2,3 > backups/products_company1.json
```

---

### Phase B.2: Create New Models (Side-by-Side)

Create `apps/products/models_v2.py` (don't modify existing yet):

```python
"""
Products models V2 - Refactored to use CompanyScopedModel
"""
import uuid
from django.db import models
from decimal import Decimal
from core.models import CompanyScopedModel


class Category(CompanyScopedModel):
    """
    Product category for portal catalog organization.
    
    Examples: Cement, Steel, Paint, Electrical, Plumbing
    """
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Category name (e.g., 'Cement', 'Steel TMT Bars')"
    )
    slug = models.SlugField(
        max_length=255,
        blank=True,
        help_text="URL-friendly category name"
    )
    description = models.TextField(
        blank=True,
        help_text="Category description for portal"
    )
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories',
        help_text="Parent category for hierarchy (optional)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Show in portal catalog"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Sort order in catalog"
    )

    class Meta:
        verbose_name = "Product Category"
        verbose_name_plural = "Product Categories"
        unique_together = [("company", "name")]
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['company', 'is_active', 'display_order']),
            models.Index(fields=['company', 'parent']),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_category_counts(cls, company):
        """
        Returns categories with their product counts.
        Scoped to company.
        """
        from django.db.models import Count
        return cls.objects.filter(
            company=company,
            is_active=True
        ).annotate(
            product_count=Count('products')
        )


class Product(CompanyScopedModel):
    """
    Portal product catalog entry.
    
    Represents customer-facing product information.
    Links to inventory.StockItem for actual stock tracking.
    
    See docs/domain/product_inventory.md for architecture details.
    """
    # Basic info
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Product display name"
    )
    slug = models.SlugField(
        max_length=255,
        blank=True,
        help_text="URL-friendly product name"
    )
    description = models.TextField(
        blank=True,
        help_text="Product description for portal"
    )
    
    # Categorization
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="products",
        help_text="Product category"
    )
    brand = models.CharField(
        max_length=100,
        blank=True,
        help_text="Brand name (e.g., 'Asian Paints', 'Tata Steel')"
    )
    
    # Pricing (display only)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Display price (MRP or list price)"
    )
    
    # Stock display (aggregated from StockItems)
    available_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Display quantity (updated from stock items)"
    )
    
    # Unit display
    unit = models.CharField(
        max_length=10,
        default='PCS',
        help_text="Display unit (KGS, BAG, PCS, etc.)"
    )
    
    # Tax info
    hsn_code = models.CharField(
        max_length=10,
        default='0000',
        help_text="HSN/SAC code for GST"
    )
    cgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="CGST rate percentage"
    )
    sgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="SGST rate percentage"
    )
    igst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="IGST rate percentage"
    )
    cess_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Cess rate percentage"
    )
    
    # Portal visibility
    is_portal_visible = models.BooleanField(
        default=True,
        help_text="Show in retailer portal catalog"
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Feature on homepage/promotions"
    )
    
    # Status
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('out_of_stock', 'Out of Stock'),
        ('on_demand', 'On Demand'),
        ('discontinued', 'Discontinued'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        help_text="Product availability status"
    )
    
    # Audit
    created_by = models.ForeignKey(
        'core_auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_products",
        help_text="User who created this product"
    )

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"
        unique_together = [("company", "name")]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'category', 'is_portal_visible']),
            models.Index(fields=['company', 'is_portal_visible', 'status']),
            models.Index(fields=['company', 'brand']),
            models.Index(fields=['company', 'hsn_code']),
        ]

    def __str__(self):
        return self.name

    def update_status(self):
        """
        Update product status based on linked stock items.
        Called after stock movements.
        """
        total_stock = self.stockitems.aggregate(
            total=models.Sum('stock_balances__quantity_on_hand')
        )['total'] or 0
        
        if total_stock > 0:
            self.status = 'available'
        elif self.status != 'discontinued':
            self.status = 'out_of_stock'
        
        self.available_quantity = total_stock
        self.save(update_fields=['status', 'available_quantity'])
```

---

### Phase B.3: Add StockItem Link

Update `apps/inventory/models.py`:

```python
class StockItem(CompanyScopedModel):
    """
    Stockable item in ERP.
    Links to products.Product for portal integration.
    """
    # NEW FIELD: Link to Product
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        null=True,  # Nullable during migration
        blank=True,
        related_name='stockitems',
        help_text="Portal product this stock item represents"
    )
    
    sku = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # ... rest of existing fields
```

---

### Phase B.4: Create Migrations

```bash
# Step 1: Create migration for new models
python manage.py makemigrations products --name "refactor_to_uuid"

# Step 2: Create migration for StockItem.product FK
python manage.py makemigrations inventory --name "add_product_link"
```

The migration will look like:

```python
# products/migrations/0002_refactor_to_uuid.py
from django.db import migrations, models
import uuid

def migrate_data_forward(apps, schema_editor):
    """
    Copy data from old models to new UUID-based models.
    """
    OldCategory = apps.get_model('products', 'Category')
    OldProduct = apps.get_model('products', 'Product')
    
    # Create mapping: old ID → new UUID
    category_mapping = {}
    product_mapping = {}
    
    # Migrate categories
    for old_cat in OldCategory.objects.all():
        new_id = uuid.uuid4()
        category_mapping[old_cat.category_id] = new_id
        # Create new category with UUID...
    
    # Migrate products
    for old_prod in OldProduct.objects.all():
        new_id = uuid.uuid4()
        product_mapping[old_prod.product_id] = new_id
        # Create new product with UUID...
    
    # Store mapping for reverse migration
    # ...

def migrate_data_backward(apps, schema_editor):
    """
    Reverse migration if needed.
    """
    # Restore old auto-increment IDs
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('products', '0001_initial'),
    ]
    
    operations = [
        # Step 1: Rename old models
        migrations.RenameModel('Category', 'CategoryOld'),
        migrations.RenameModel('Product', 'ProductOld'),
        
        # Step 2: Create new models with UUID
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(...)),
                ('name', models.CharField(max_length=255)),
                # ... all other fields
            ],
            bases=('core.CompanyScopedModel',),
        ),
        
        # Step 3: Migrate data
        migrations.RunPython(migrate_data_forward, migrate_data_backward),
        
        # Step 4: Update foreign keys
        # (Any models that reference Product/Category)
        
        # Step 5: Drop old models
        migrations.DeleteModel('CategoryOld'),
        migrations.DeleteModel('ProductOld'),
    ]
```

---

### Phase B.5: Data Migration Strategy

**Option A: Downtime Migration** (Recommended for small datasets)

1. Put system in maintenance mode
2. Run migration
3. Verify data
4. Resume operations

**Option B: Zero-Downtime Migration** (For production)

1. Create new models alongside old
2. Dual-write to both models
3. Backfill data
4. Switch reads to new models
5. Remove old models

**Script**:

```python
# scripts/migrate_products_to_uuid.py
import uuid
from django.db import transaction
from apps.products.models import Category as OldCategory, Product as OldProduct
from apps.products.models_v2 import Category as NewCategory, Product as NewProduct

@transaction.atomic
def migrate_products():
    """
    Migrate products from auto-increment to UUID.
    """
    category_map = {}
    product_map = {}
    
    print("Migrating categories...")
    for old_cat in OldCategory.objects.all():
        new_cat = NewCategory.objects.create(
            id=uuid.uuid4(),
            company=old_cat.company,
            name=old_cat.name,
            created_at=old_cat.created_at if hasattr(old_cat, 'created_at') else timezone.now(),
        )
        category_map[old_cat.category_id] = new_cat.id
        print(f"  Migrated: {old_cat.name} -> {new_cat.id}")
    
    print("\nMigrating products...")
    for old_prod in OldProduct.objects.all():
        new_prod = NewProduct.objects.create(
            id=uuid.uuid4(),
            company=old_prod.company,
            name=old_prod.name,
            category_id=category_map.get(old_prod.category_id),
            price=old_prod.price,
            available_quantity=old_prod.available_quantity,
            unit=old_prod.unit,
            hsn_code=old_prod.hsn_code,
            cgst_rate=old_prod.cgst_rate,
            sgst_rate=old_prod.sgst_rate,
            igst_rate=old_prod.igst_rate,
            cess_rate=old_prod.cess_rate,
            status='available' if old_prod.status == 'sufficient' else 'on_demand',
            created_by=old_prod.created_by,
        )
        product_map[old_prod.product_id] = new_prod.id
        print(f"  Migrated: {old_prod.name} -> {new_prod.id}")
    
    print(f"\n✅ Migration complete!")
    print(f"   Categories: {len(category_map)}")
    print(f"   Products: {len(product_map)}")
    
    return category_map, product_map

if __name__ == '__main__':
    migrate_products()
```

---

### Phase B.6: Update APIs

Update serializers to handle UUID:

```python
# apps/products/api/serializers.py
from rest_framework import serializers
from apps.products.models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'is_active', 'product_count']
        # id is now UUID (automatically handled by DRF)

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True)  # Changed from IntegerField
    
    class Meta:
        model = Product
        fields = [
            'id',  # Now UUID
            'name',
            'description',
            'category',
            'category_id',
            'brand',
            'price',
            'available_quantity',
            'unit',
            'hsn_code',
            'status',
            'is_portal_visible',
        ]
```

---

### Phase B.7: Update Frontend/Portal

**API Endpoint Changes**: None (URLs remain same, just ID format changes)

**JavaScript/TypeScript Changes**:

```typescript
// BEFORE
interface Product {
  id: number;  // ❌ Integer
  category_id: number;
  // ...
}

// AFTER
interface Product {
  id: string;  // ✅ UUID string
  category_id: string;
  // ...
}

// URL construction (no change needed)
const url = `/api/products/${product.id}/`;  // Works with both int and UUID
```

**React/Vue Components**: Minimal changes (IDs treated as strings)

---

## Testing Strategy

### Test Cases

```python
# tests/test_products_refactor.py
import uuid
from django.test import TestCase
from apps.products.models import Product, Category
from apps.company.models import Company, Currency

class ProductRefactorTest(TestCase):
    
    def setUp(self):
        currency = Currency.objects.create(code='INR', name='Indian Rupee')
        self.company = Company.objects.create(
            code='TEST',
            name='Test Company',
            legal_name='Test Pvt Ltd',
            base_currency=currency
        )
    
    def test_category_uses_uuid(self):
        """Category should use UUID primary key"""
        category = Category.objects.create(
            company=self.company,
            name="Test Category"
        )
        self.assertIsInstance(category.id, uuid.UUID)
    
    def test_product_uses_uuid(self):
        """Product should use UUID primary key"""
        product = Product.objects.create(
            company=self.company,
            name="Test Product",
            price=100
        )
        self.assertIsInstance(product.id, uuid.UUID)
    
    def test_category_unique_per_company(self):
        """Category name should be unique per company only"""
        Category.objects.create(company=self.company, name="Cement")
        
        # Should raise error for same company
        with self.assertRaises(Exception):
            Category.objects.create(company=self.company, name="Cement")
        
        # Should work for different company
        other_company = Company.objects.create(...)
        category2 = Category.objects.create(
            company=other_company,
            name="Cement"  # Same name, different company
        )
        self.assertIsNotNone(category2)
    
    def test_product_stockitem_link(self):
        """Product should link to StockItem"""
        from apps.inventory.models import StockItem, UnitOfMeasure
        
        product = Product.objects.create(...)
        uom = UnitOfMeasure.objects.create(name='Bag', symbol='BAG')
        
        stock_item = StockItem.objects.create(
            company=self.company,
            product=product,  # Link to product
            sku='TEST-SKU',
            name='Test Stock Item',
            uom=uom
        )
        
        self.assertEqual(stock_item.product, product)
        self.assertIn(stock_item, product.stockitems.all())
```

---

## Rollback Plan

If migration fails:

```bash
# Step 1: Restore database backup
pg_restore -d vendor_db backups/before_products_migration.dump

# Step 2: Revert migrations
python manage.py migrate products 0001_initial

# Step 3: Verify data
python manage.py shell
>>> from apps.products.models import Product
>>> Product.objects.count()  # Should match backup

# Step 4: Investigate failure
# Check migration logs, fix issues, retry
```

---

## Deployment Checklist

- [ ] **Backup database**
- [ ] **Export existing products** (`dumpdata`)
- [ ] **Test migration in staging**
- [ ] **Verify all products migrated**
- [ ] **Test API endpoints** (Postman/Swagger)
- [ ] **Test portal product listing**
- [ ] **Test order creation**
- [ ] **Monitor for errors** (first 24 hours)
- [ ] **Document new ID format** (API docs)
- [ ] **Update frontend types** (if TypeScript)
- [ ] **Update mobile app** (if applicable)

---

## Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| B.1 Backup | 1 hour | Export and verify backups |
| B.2 New Models | 4 hours | Write models_v2.py, tests |
| B.3 StockItem Link | 2 hours | Add FK, create migration |
| B.4 Migrations | 4 hours | Write data migration script |
| B.5 Testing | 4 hours | Run tests, verify data |
| B.6 API Updates | 3 hours | Update serializers, views |
| B.7 Deployment | 2 hours | Deploy, monitor |
| **Total** | **2-3 days** | Including testing and fixes |

---

## Success Criteria

✅ **Migration Success**:
1. All categories migrated with new UUIDs
2. All products migrated with new UUIDs
3. No data loss (count matches)
4. All relationships preserved
5. API returns UUID strings
6. Portal functions normally
7. Orders can be created
8. No regression in tests

---

## Post-Migration Tasks

1. **Update documentation**
   - API docs (Swagger/OpenAPI)
   - Frontend integration guide
   - Mobile app integration

2. **Monitor production**
   - Check logs for UUID-related errors
   - Monitor API response times
   - Track order creation success rate

3. **Clean up**
   - Remove old migration backups (after 30 days)
   - Archive old model code
   - Update team on changes

---

**Status**: 📋 READY FOR IMPLEMENTATION  
**Approval Required**: Yes (involves schema change)  
**Contact**: Backend Team Lead
