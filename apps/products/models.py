"""
Product and category models.
Models: Product, Category

NOTE: Refactored Dec 2025 to use CompanyScopedModel and UUID primary keys.
See docs/domain/product_inventory.md for architecture details.
"""
from django.db import models
from django.conf import settings
from decimal import Decimal
from core.models import CompanyScopedModel


# Unit of Quantity Choices (UQC) for GST compliance
UQC_CHOICES = [
    ('BAG', 'Bags'),
    ('BAL', 'Bale'),
    ('BDL', 'Bundles'),
    ('BKL', 'Buckles'),
    ('BOU', 'Billions of Units'),
    ('BOX', 'Box'),
    ('BTL', 'Bottles'),
    ('BUN', 'Bunches'),
    ('CAN', 'Cans'),
    ('CBM', 'Cubic Meter'),
    ('CCM', 'Cubic Centimeter'),
    ('CMS', 'Centimeters'),
    ('CTN', 'Cartons'),
    ('DOZ', 'Dozens'),
    ('DRM', 'Drums'),
    ('GGK', 'Great Gross'),
    ('GMS', 'Grams'),
    ('GRS', 'Gross'),
    ('GYD', 'Gross Yards'),
    ('KGS', 'Kilograms'),
    ('KLR', 'Kilolitre'),
    ('KME', 'Kilometre'),
    ('LTR', 'Litre'),
    ('MTR', 'Meters'),
    ('MLT', 'Millilitre'),
    ('MTS', 'Metric Ton'),
    ('NOS', 'Numbers'),
    ('PAC', 'Packs'),
    ('PCS', 'Pieces'),
    ('PRS', 'Pairs'),
    ('QTL', 'Quintal'),
    ('ROL', 'Rolls'),
    ('SET', 'Sets'),
    ('SQF', 'Square Feet'),
    ('SQM', 'Square Meter'),
    ('SQY', 'Square Yards'),
    ('TBS', 'Tablets'),
    ('TGM', 'Ten Grams'),
    ('THD', 'Thousands'),
    ('TON', 'Tonne'),
    ('TUB', 'Tubes'),
    ('UGS', 'US Gallons'),
    ('UNT', 'Units'),
    ('YDS', 'Yards'),
]


class Category(CompanyScopedModel):
    """
    Product category for portal catalog organization.
    
    Extends CompanyScopedModel for multi-tenant safety and UUID primary keys.
    Examples: Cement, Steel, Paint, Electrical, Plumbing
    """
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Category name (e.g., 'Cement', 'Steel TMT Bars')"
    )
    description = models.TextField(
        blank=True,
        help_text="Category description for portal display"
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
            models.Index(fields=['company', 'name']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def get_category_counts(cls, company):
        """
        Returns categories with their product counts for a specific company.
        """
        from django.db.models import Count
        return cls.objects.filter(
            company=company,
            is_active=True
        ).annotate(product_count=Count('products'))


class Product(CompanyScopedModel):
    """
    Portal product catalog entry.
    
    Represents customer-facing product information for B2B portal.
    Links to inventory.StockItem for actual stock tracking.
    
    See docs/domain/product_inventory.md for architecture details.
    """
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Product display name for portal"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        help_text="Product category for browsing"
    )
    description = models.TextField(
        blank=True,
        help_text="Product description for portal"
    )
    brand = models.CharField(
        max_length=100,
        blank=True,
        help_text="Brand name (e.g., 'Asian Paints', 'Tata Steel')"
    )
    available_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Display quantity (aggregated from stock items)"
    )
    
    # Unit display (for portal)
    unit = models.CharField(
        max_length=10,
        choices=UQC_CHOICES,
        default='PCS',
        help_text="Display unit for portal (actual UOM in StockItem)"
    )
    
    # Legacy fields (consider deprecating)
    total_shipped = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity shipped (legacy field)"
    )
    total_required_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Total required quantity (legacy field)"
    )
    
    # Pricing (display only - actual pricing from StockItem)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Display price (MRP or list price)"
    )
    
    # Tax information
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
    
    # Status choices
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
        settings.AUTH_USER_MODEL,
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
            models.Index(fields=['company', 'name']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return self.name
    
    def update_stock_from_items(self):
        """
        Update available_quantity and status from linked StockItems.
        Called after stock movements to keep portal display in sync.
        """
        from django.db.models import Sum
        
        # Aggregate from linked stock items
        total_stock = self.stockitems.aggregate(
            total=Sum('stock_balances__quantity_on_hand')
        )['total'] or 0
        
        self.available_quantity = int(total_stock)
        
        # Update status based on stock
        if total_stock > 0:
            self.status = 'available'
        elif self.status != 'discontinued':
            self.status = 'out_of_stock'
        
        self.save(update_fields=['available_quantity', 'status', 'updated_at'])
