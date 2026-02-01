"""
Inventory management models for ERP system.
Models: UnitOfMeasure, StockItem, PriceList, ItemPrice, StockBatch, Godown, StockMovement, StockBalance
"""
from django.db import models
from django.utils import timezone
from core.models import BaseModel, CompanyScopedModel


class UOMCategory(models.TextChoices):
    """Enum for UOM categories"""
    WEIGHT = 'WEIGHT', 'Weight'
    LENGTH = 'LENGTH', 'Length'
    VOLUME = 'VOLUME', 'Volume'
    QUANTITY = 'QUANTITY', 'Quantity'
    TIME = 'TIME', 'Time'
    AREA = 'AREA', 'Area'


class UnitOfMeasure(BaseModel):
    """
    Unit of measure master (global).
    Examples: kg, meter, piece, liter, etc.
    """
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10, unique=True, db_index=True)
    category = models.CharField(
        max_length=30,
        choices=UOMCategory.choices
    )

    class Meta:
        verbose_name_plural = "Units of Measure"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class StockGroup(CompanyScopedModel):
    """
    Hierarchical grouping of stock items (e.g., Electronics > Mobile Phones).
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('company', 'code')
        verbose_name_plural = "Stock Groups"
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class StockCategory(CompanyScopedModel):
    """
    Categorization of stock items for filtering and reporting.
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ('company', 'code')
        verbose_name_plural = "Stock Categories"
        indexes = [
            models.Index(fields=['company', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class StockItem(CompanyScopedModel):
    """
    Stock item master per company.
    Represents products/items that can be tracked in inventory.
    
    Links to products.Product for portal catalog integration.
    See docs/domain/product_inventory.md for architecture.
    """
    # Link to portal product (added Dec 2025)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stockitems',
        help_text="Portal product this stock item represents (for B2B catalog)"
    )
    
    sku = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    uom = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.PROTECT,
        related_name='stock_items'
    )
    is_stock_item = models.BooleanField(
        default=True,
        help_text="Whether this item tracks stock or is a service"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "sku")
        verbose_name_plural = "Stock Items"
        indexes = [
            models.Index(fields=['company', 'sku']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'product']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name}"


class PriceList(CompanyScopedModel):
    """
    Price list master for different customer segments or time periods.
    """
    name = models.CharField(max_length=100)
    currency = models.ForeignKey(
        "company.Currency",
        on_delete=models.PROTECT,
        related_name='price_lists'
    )
    is_default = models.BooleanField(default=False)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Price Lists"
        indexes = [
            models.Index(fields=['company', 'is_default']),
            models.Index(fields=['company', 'valid_from', 'valid_to']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class ItemPrice(BaseModel):
    """
    Time-bound pricing for items in a price list.
    """
    item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='prices'
    )
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name='item_prices'
    )
    rate = models.DecimalField(max_digits=14, decimal_places=4)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Item Prices"
        indexes = [
            models.Index(fields=['item', 'price_list', 'valid_from']),
        ]

    def __str__(self):
        return f"{self.item.sku} - {self.rate} in {self.price_list.name}"


class StockBatch(CompanyScopedModel):
    """
    Batch/Lot tracking for stock items.
    Used for expiry tracking, FIFO/LIFO, traceability.
    """
    item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name='batches'
    )
    batch_number = models.CharField(max_length=100, db_index=True)
    mfg_date = models.DateField(null=True, blank=True)
    exp_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Stock Batches"
        unique_together = ("company", "item", "batch_number")
        indexes = [
            models.Index(fields=['company', 'item', 'batch_number']),
            models.Index(fields=['company', 'exp_date']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.item.sku} - Batch {self.batch_number}"


class Godown(CompanyScopedModel):
    """
    Warehouse/Godown master.
    Supports hierarchy for multi-location inventory tracking.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children'
    )
    address = models.ForeignKey(
        "company.Address",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='godowns'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Godowns"
        unique_together = ("company", "code")
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class StockMovement(CompanyScopedModel):
    """
    Core stock movement ledger.
    Every inventory transaction creates movement entries.
    Stock balance = Σ(IN movements) - Σ(OUT movements)
    
    NEVER store quantity directly on StockItem.
    Always compute from movements.
    """
    item = models.ForeignKey(
        StockItem,
        on_delete=models.PROTECT,
        related_name='movements'
    )
    from_godown = models.ForeignKey(
        Godown,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='outward_movements'
    )
    to_godown = models.ForeignKey(
        Godown,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='inward_movements'
    )
    batch = models.ForeignKey(
        StockBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='movements'
    )
    
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        help_text="Positive for inward, negative for outward (or use godowns)"
    )
    rate = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        help_text="Rate per unit for valuation"
    )
    
    voucher = models.ForeignKey(
        "voucher.Voucher",
        on_delete=models.CASCADE,
        related_name='stock_movements',
        help_text="Every movement is tied to a voucher"
    )
    
    movement_date = models.DateField()

    class Meta:
        verbose_name_plural = "Stock Movements"
        indexes = [
            models.Index(fields=['company', 'item', 'movement_date']),
            models.Index(fields=['company', 'to_godown', 'item']),
            models.Index(fields=['company', 'from_godown', 'item']),
            models.Index(fields=['voucher']),
            models.Index(fields=['company', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="stock_movement_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.item.sku} - {self.quantity} on {self.movement_date}"


class StockBalance(CompanyScopedModel):
    """
    Cached balance per (company, item, godown, batch).
    Source of truth remains StockMovement. This table is a transactional cache
    updated by posting service inside the same DB transaction (select_for_update).
    
    Provides fast real-time stock availability queries without aggregating movements.
    """
    item = models.ForeignKey(
        "inventory.StockItem",
        on_delete=models.PROTECT,
        related_name='stock_balances'
    )
    godown = models.ForeignKey(
        "inventory.Godown",
        on_delete=models.PROTECT,
        related_name='stock_balances'
    )
    batch = models.ForeignKey(
        "inventory.StockBatch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_balances'
    )

    quantity_on_hand = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        default=0,
        help_text="Physical quantity available in godown"
    )
    quantity_reserved = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        default=0,
        help_text="Reserved for orders (not yet shipped)"
    )
    quantity_allocated = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        default=0,
        help_text="Allocated for current picking/processing"
    )

    last_movement = models.ForeignKey(
        "inventory.StockMovement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='balance_updates',
        help_text="Last movement that updated this balance (for idempotency)"
    )
    last_updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("company", "item", "godown", "batch")
        verbose_name_plural = "Stock Balances"
        indexes = [
            models.Index(fields=['company', 'item']),
            models.Index(fields=['company', 'godown', 'item']),
            models.Index(fields=['company', 'item', 'godown', 'batch']),
            models.Index(fields=['company', 'created_at']),
        ]

    @property
    def quantity_available(self):
        """Available quantity = on_hand - reserved - allocated"""
        return self.quantity_on_hand - self.quantity_reserved - self.quantity_allocated

    def __str__(self):
        batch_info = f" Batch:{self.batch.batch_number}" if self.batch else ""
        return f"{self.item.sku} @{self.godown.code}{batch_info} = {self.quantity_on_hand}"


class StockReservation(CompanyScopedModel):
    """
    Stock reservations - allocate stock for sales orders or other purposes.
    """
    
    class ReservationStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        CANCELLED = 'CANCELLED', 'Cancelled'
        EXPIRED = 'EXPIRED', 'Expired'
    
    item = models.ForeignKey(
        "inventory.StockItem",
        on_delete=models.PROTECT,
        related_name='reservations'
    )
    godown = models.ForeignKey(
        "inventory.Godown",
        on_delete=models.PROTECT,
        related_name='reservations'
    )
    quantity = models.DecimalField(
        max_digits=18,
        decimal_places=3,
        help_text="Quantity reserved"
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.ACTIVE
    )
    reserved_for_type = models.CharField(
        max_length=100,
        help_text="Type of entity this reservation is for (e.g., 'SalesOrder')",
        blank=True
    )
    reserved_for_id = models.IntegerField(
        help_text="ID of the entity this reservation is for",
        null=True,
        blank=True
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this reservation expires"
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Stock Reservations"
        indexes = [
            models.Index(fields=['company', 'item', 'status']),
            models.Index(fields=['company', 'godown', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.item.sku} @ {self.godown.code}: {self.quantity} ({self.status})"
