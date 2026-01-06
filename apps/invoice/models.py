"""
Invoice models for ERP system.
Models: Invoice, InvoiceLine
"""
from django.db import models
from django.conf import settings
from core.models import CompanyScopedModel, BaseModel


class InvoiceType(models.TextChoices):
    """Enum for invoice types"""
    SALES = 'SALES', 'Sales Invoice'
    PURCHASE = 'PURCHASE', 'Purchase Invoice'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Debit Note'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note'
    PROFORMA = 'PROFORMA', 'Proforma Invoice'


class InvoiceStatus(models.TextChoices):
    """Enum for invoice status"""
    DRAFT = 'DRAFT', 'Draft'
    POSTING = 'POSTING', 'Posting'
    POSTED = 'POSTED', 'Posted'
    SUBMITTED = 'SUBMITTED', 'Submitted'
    PAID = 'PAID', 'Paid'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Invoice(CompanyScopedModel):
    """
    Invoice master.
    Every invoice creates a voucher for accounting integration.
    """
    invoice_number = models.CharField(max_length=50, db_index=True)
    invoice_date = models.DateField()
    
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceType.choices
    )
    
    due_date = models.DateField(
        help_text="Payment due date"
    )
    
    currency = models.ForeignKey(
        "company.Currency",
        on_delete=models.PROTECT,
        related_name='invoices'
    )
    
    financial_year = models.ForeignKey(
        "company.FinancialYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Financial year is resolved by posting engine"
    )
    
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT
    )
    
    # Link to accounting voucher
    voucher = models.OneToOneField(
        "voucher.Voucher",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='invoice',
        help_text="Accounting voucher generated from this invoice"
    )
    
    # References
    sales_order = models.ForeignKey(
        "orders.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices'
    )
    purchase_order = models.ForeignKey(
        "orders.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invoices'
    )
    
    # Amounts (denormalized for performance)
    subtotal = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    tax_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    discount_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    grand_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )
    
    # Payment tracking
    amount_received = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        help_text="Total amount received against this invoice"
    )
    
    @property
    def total_value(self):
        """Total value of invoice (alias for grand_total)"""
        return self.grand_total
    
    # Additional fields
    terms_and_conditions = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices'
    )

    class Meta:
        unique_together = ("company", "invoice_number")
        verbose_name_plural = "Invoices"
        indexes = [
            models.Index(fields=['company', 'invoice_number']),
            models.Index(fields=['company', 'party', 'status']),
            models.Index(fields=['company', 'invoice_date']),
            models.Index(fields=['company', 'due_date']),
            models.Index(fields=['company', 'invoice_type', 'status']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.party.name}"
    
    def refresh_outstanding(self):
        """
        Recalculate and update outstanding amount based on payments received.
        
        This method aggregates all payment applications (PaymentLine) for this invoice
        and updates the amount_received and status fields accordingly.
        """
        from decimal import Decimal
        
        # Check if PaymentLine model exists
        try:
            from apps.payment.models import PaymentLine
            
            # Aggregate payments applied to this invoice
            paid = PaymentLine.objects.filter(
                invoice_id=self.id
            ).aggregate(total=models.Sum("amount_applied"))["total"] or Decimal("0")
            
            self.amount_received = paid
            
            # Update status based on payment
            if paid >= self.total_value:
                self.status = "PAID"
            elif paid > 0:
                self.status = "PARTIALLY_PAID"
            else:
                # Keep existing status if no payment
                pass
            
            self.save(update_fields=["amount_received", "status"])
            
        except ImportError:
            # PaymentLine model not yet implemented
            pass


class InvoiceLine(BaseModel):
    """
    Invoice line items.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    line_no = models.PositiveIntegerField(
        help_text="Line number in invoice"
    )
    
    item = models.ForeignKey(
        "inventory.StockItem",
        on_delete=models.PROTECT,
        related_name='invoice_lines'
    )
    
    description = models.CharField(max_length=255, blank=True, null=True)
    
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    
    uom = models.ForeignKey(
        "inventory.UnitOfMeasure",
        on_delete=models.PROTECT,
        related_name='invoice_lines'
    )
    
    unit_rate = models.DecimalField(max_digits=14, decimal_places=4)
    
    discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )
    
    # Calculated amounts (can be computed but stored for audit)
    line_total = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text="Line total after discount before tax"
    )
    
    tax_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0
    )

    class Meta:
        verbose_name_plural = "Invoice Lines"
        ordering = ['invoice', 'line_no']
        indexes = [
            models.Index(fields=['invoice', 'line_no']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name="invoice_line_quantity_positive",
            ),
        ]

    def __str__(self):
        return f"Invoice {self.invoice.invoice_number} Line {self.line_no}: {self.item.sku}"
