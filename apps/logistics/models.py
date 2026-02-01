"""
Logistics and shipping models for ERP system.
Models: Carrier, Shipment, ShipmentItem
"""
from django.db import models
from core.models import CompanyScopedModel, BaseModel


class Carrier(CompanyScopedModel):
    """
    Shipping carrier/transporter master.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    
    # Contact details
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    
    # Business details
    gstin = models.CharField(
        max_length=15,
        blank=True,
        help_text="GST Number for transporter"
    )
    
    transport_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Transporter ID for e-way bill"
    )
    
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Carriers"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class ShipmentStatus(models.TextChoices):
    """Enum for shipment status"""
    DRAFT = 'DRAFT', 'Draft'
    READY = 'READY', 'Ready to Ship'
    PICKED = 'PICKED', 'Picked Up'
    IN_TRANSIT = 'IN_TRANSIT', 'In Transit'
    OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', 'Out for Delivery'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'
    RETURNED = 'RETURNED', 'Returned'


class Shipment(CompanyScopedModel):
    """
    Shipment/delivery tracking.
    Links to sales orders and invoices.
    """
    shipment_number = models.CharField(max_length=50, db_index=True)
    
    carrier = models.ForeignKey(
        Carrier,
        on_delete=models.PROTECT,
        related_name='shipments'
    )
    
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Carrier's tracking number"
    )
    
    # Shipment dates
    shipped_date = models.DateField()
    expected_delivery = models.DateField(
        null=True,
        blank=True
    )
    actual_delivery = models.DateField(
        null=True,
        blank=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.DRAFT
    )
    
    # Links to orders/invoices
    sales_order = models.ForeignKey(
        "orders.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='shipments'
    )
    
    invoice = models.ForeignKey(
        "invoice.Invoice",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='shipments'
    )
    
    # Shipping details
    from_address = models.ForeignKey(
        "company.Address",
        on_delete=models.PROTECT,
        related_name='shipments_from'
    )
    
    to_address = models.ForeignKey(
        "party.PartyAddress",
        on_delete=models.PROTECT,
        related_name='shipments_to'
    )
    
    # Transport details
    vehicle_number = models.CharField(
        max_length=50,
        blank=True
    )
    driver_name = models.CharField(
        max_length=100,
        blank=True
    )
    driver_phone = models.CharField(
        max_length=20,
        blank=True
    )
    
    # E-way bill (for India)
    eway_bill_number = models.CharField(
        max_length=50,
        blank=True
    )
    
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("company", "shipment_number")
        verbose_name_plural = "Shipments"
        indexes = [
            models.Index(fields=['company', 'shipment_number']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'shipped_date']),
            models.Index(fields=['sales_order']),
            models.Index(fields=['invoice']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.shipment_number} - {self.carrier.name} ({self.status})"


class ShipmentItem(BaseModel):
    """
    Line items in a shipment.
    Tracks what items are being shipped.
    """
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    line_no = models.PositiveIntegerField()
    
    item = models.ForeignKey(
        "inventory.StockItem",
        on_delete=models.PROTECT,
        related_name='shipment_items'
    )
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    
    uom = models.ForeignKey(
        "inventory.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name='shipment_items'
    )
    
    # Optional links to order/invoice items
    order_item = models.ForeignKey(
        "orders.OrderItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='shipment_items'
    )
    
    invoice_line = models.ForeignKey(
        "invoice.InvoiceLine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='shipment_items'
    )
    
    # Package details
    package_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Package/box number if multiple packages"
    )
    
    batch = models.ForeignKey(
        "inventory.StockBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='shipment_items'
    )

    class Meta:
        verbose_name_plural = "Shipment Items"
        ordering = ['shipment', 'line_no']
        indexes = [
            models.Index(fields=['shipment', 'line_no']),
            models.Index(fields=['item']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="shipment_item_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.shipment.shipment_number} Line {self.line_no}: {self.item.sku} x {self.quantity}"

