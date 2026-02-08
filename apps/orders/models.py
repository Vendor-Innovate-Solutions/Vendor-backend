"""
Order management models for ERP system.
Models: SalesOrder, PurchaseOrder, OrderItem
"""
from django.db import models
from django.conf import settings
from core.models import CompanyScopedModel, BaseModel


class OrderStatus(models.TextChoices):
    """Enum for order status"""
    DRAFT = 'DRAFT', 'Draft'
    PENDING = 'PENDING', 'Pending'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    PARTIAL_INVOICED = 'PARTIAL_INVOICED', 'Partially Invoiced'
    INVOICE_CREATED_PENDING_POSTING = 'INVOICE_CREATED_PENDING_POSTING', 'Invoice Created Pending Posting'
    INVOICED = 'INVOICED', 'Invoiced'
    PARTIAL_RECEIVED = 'PARTIAL_RECEIVED', 'Partially Received'
    COMPLETED = 'COMPLETED', 'Completed'
    POSTED = 'POSTED', 'Posted'
    CANCELLED = 'CANCELLED', 'Cancelled'
    ON_HOLD = 'ON_HOLD', 'On Hold'


class SalesOrder(CompanyScopedModel):
    """
    Sales order from customers.
    Tracks order lifecycle from quotation to delivery.
    """
    order_number = models.CharField(max_length=50, db_index=True)
    customer = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name='sales_orders',
        limit_choices_to={'party_type__in': ['CUSTOMER', 'BOTH']}
    )
    status = models.CharField(
        max_length=40,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT
    )
    order_date = models.DateField()
    delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected delivery date"
    )
    currency = models.ForeignKey(
        "company.Currency",
        on_delete=models.PROTECT,
        related_name='sales_orders'
    )
    price_list = models.ForeignKey(
        "inventory.PriceList",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_orders',
        help_text="Price list for this order"
    )
    
    # Reference fields
    customer_po_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Customer's Purchase Order reference"
    )
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Lifecycle tracking
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was confirmed"
    )
    invoiced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was invoiced"
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was posted to accounting"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was cancelled"
    )
    cancellation_reason = models.TextField(
        blank=True,
        help_text="Reason for cancellation"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_sales_orders'
    )
    
    # Employee assignment for delivery/processing
    assigned_employee = models.ForeignKey(
        "hr.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_orders',
        help_text="Employee assigned for delivery/processing"
    )

    class Meta:
        unique_together = ("company", "order_number")
        verbose_name_plural = "Sales Orders"
        indexes = [
            models.Index(fields=['company', 'order_number']),
            models.Index(fields=['company', 'customer', 'status']),
            models.Index(fields=['company', 'order_date']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"SO-{self.order_number} - {self.customer.name}"
    
    def get_content_type(self):
        """Get ContentType for this model (for generic relations)."""
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(self.__class__)


class PurchaseOrder(CompanyScopedModel):
    """
    Purchase order to suppliers.
    Tracks procurement from order to receipt.
    """
    order_number = models.CharField(max_length=50, db_index=True)
    supplier = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name='purchase_orders',
        limit_choices_to={'party_type__in': ['SUPPLIER', 'BOTH']}
    )
    status = models.CharField(
        max_length=40,
        choices=OrderStatus.choices,
        default=OrderStatus.DRAFT
    )
    order_date = models.DateField()
    expected_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected delivery date from supplier"
    )
    currency = models.ForeignKey(
        "company.Currency",
        on_delete=models.PROTECT,
        related_name='purchase_orders'
    )
    price_list = models.ForeignKey(
        "inventory.PriceList",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='purchase_orders',
        help_text="Price list for this purchase order"
    )
    
    # Reference fields
    supplier_quote_ref = models.CharField(
        max_length=50,
        blank=True,
        help_text="Supplier's quotation reference"
    )
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Lifecycle tracking
    confirmed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was confirmed"
    )
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was posted to accounting"
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the order was cancelled"
    )
    cancellation_reason = models.TextField(
        blank=True,
        help_text="Reason for cancellation"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_purchase_orders'
    )

    class Meta:
        unique_together = ("company", "order_number")
        verbose_name_plural = "Purchase Orders"
        indexes = [
            models.Index(fields=['company', 'order_number']),
            models.Index(fields=['company', 'supplier', 'status']),
            models.Index(fields=['company', 'order_date']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"PO-{self.order_number} - {self.supplier.name}"
    
    def get_content_type(self):
        """Get ContentType for this model (for generic relations)."""
        from django.contrib.contenttypes.models import ContentType
        return ContentType.objects.get_for_model(self.__class__)


class OrderItem(CompanyScopedModel):
    """
    Line items for orders.
    Polymorphic - can belong to either SalesOrder or PurchaseOrder.
    """
    sales_order = models.ForeignKey(
        SalesOrder,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='items'
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    line_no = models.PositiveIntegerField(
        help_text="Line number in order"
    )
    
    item = models.ForeignKey(
        "inventory.StockItem",
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Additional item description"
    )
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    uom = models.ForeignKey(
        "inventory.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    
    unit_rate = models.DecimalField(max_digits=14, decimal_places=4)
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Discount percentage"
    )
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Tax rate percentage"
    )
    
    # Delivery tracking
    delivered_qty = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        help_text="Quantity delivered/received so far"
    )

    class Meta:
        verbose_name_plural = "Order Items"
        indexes = [
            models.Index(fields=['sales_order', 'line_no']),
            models.Index(fields=['purchase_order', 'line_no']),
            models.Index(fields=['company', 'item']),
            models.Index(fields=['company', 'created_at']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(sales_order__isnull=False, purchase_order__isnull=True) |
                    models.Q(sales_order__isnull=True, purchase_order__isnull=False)
                ),
                name="order_item_single_parent",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(delivered_qty__gte=0),
                name="order_item_delivered_qty_non_negative",
            ),
        ]

    def __str__(self):
        order = self.sales_order or self.purchase_order
        order_type = "SO" if self.sales_order else "PO"
        return f"{order_type}-{order.order_number} Line {self.line_no}: {self.item.sku}"


class CreditNoteStatus(models.TextChoices):
    """Enum for credit note status"""
    DRAFT = 'DRAFT', 'Draft'
    APPROVED = 'APPROVED', 'Approved'
    APPLIED = 'APPLIED', 'Applied'
    CANCELLED = 'CANCELLED', 'Cancelled'


class CreditNote(CompanyScopedModel):
    """
    Credit note for sales returns or adjustments.
    Can be created against an invoice or as a general credit.
    """
    credit_note_number = models.CharField(max_length=50, unique=True, db_index=True)
    credit_note_date = models.DateField()
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name='credit_notes'
    )
    reference_invoice = models.ForeignKey(
        "invoice.Invoice",
        on_delete=models.PROTECT,
        related_name='credit_notes',
        null=True,
        blank=True,
        help_text="Invoice against which this credit note is issued"
    )
    reference_type = models.CharField(
        max_length=20,
        choices=[('INVOICE', 'Against Invoice'), ('GENERAL', 'General Credit')],
        default='INVOICE'
    )
    reason = models.TextField(help_text='Reason for credit note')
    status = models.CharField(
        max_length=20,
        choices=CreditNoteStatus.choices,
        default=CreditNoteStatus.DRAFT
    )
    
    # Totals
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_credit_notes'
    )

    class Meta:
        verbose_name = "Credit Note"
        verbose_name_plural = "Credit Notes"
        ordering = ['-credit_note_date', '-created_at']
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'credit_note_date']),
            models.Index(fields=['party', 'status']),
        ]

    def __str__(self):
        return f"{self.credit_note_number} - {self.party.name}"


class CreditNoteLine(BaseModel):
    """
    Line items for credit notes.
    """
    credit_note = models.ForeignKey(
        CreditNote,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    line_no = models.PositiveSmallIntegerField()
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_rate = models.DecimalField(max_digits=15, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # GST breakdown
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    cgst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    sgst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    igst_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    line_total = models.DecimalField(max_digits=15, decimal_places=2)

    class Meta:
        verbose_name = "Credit Note Line"
        verbose_name_plural = "Credit Note Lines"
        ordering = ['line_no']
        unique_together = [('credit_note', 'line_no')]

    def __str__(self):
        return f"{self.credit_note.credit_note_number} Line {self.line_no}"


class PriceListType(models.TextChoices):
    """Enum for price list types"""
    STANDARD = 'STANDARD', 'Standard Price'
    WHOLESALE = 'WHOLESALE', 'Wholesale'
    RETAIL = 'RETAIL', 'Retail'
    SPECIAL = 'SPECIAL', 'Special Offer'


class PriceList(CompanyScopedModel):
    """
    Price list for products.
    Can have different price lists for wholesale, retail, special offers, etc.
    """
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price_list_type = models.CharField(
        max_length=20,
        choices=PriceListType.choices,
        default=PriceListType.STANDARD
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Price List"
        verbose_name_plural = "Price Lists"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'price_list_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.price_list_type})"


class PriceListItem(BaseModel):
    """
    Individual product prices in a price list.
    Supports tiered pricing based on minimum quantity.
    """
    price_list = models.ForeignKey(
        PriceList,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name='price_list_items'
    )
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    min_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=1,
        help_text='Minimum quantity for this price'
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Price List Item"
        verbose_name_plural = "Price List Items"
        ordering = ['product', 'min_quantity']
        unique_together = [('price_list', 'product', 'min_quantity')]
        indexes = [
            models.Index(fields=['price_list', 'is_active']),
            models.Index(fields=['product', 'is_active']),
        ]

    def __str__(self):
        return f"{self.price_list.name} - {self.product.name} @ {self.unit_price}"
