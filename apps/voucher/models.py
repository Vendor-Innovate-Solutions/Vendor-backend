"""
Voucher models for ERP system.
Models: VoucherType, Voucher, VoucherLine
"""
from django.db import models
from django.conf import settings
from core.models import CompanyScopedModel, BaseModel


class VoucherCategory(models.TextChoices):
    """Enum for voucher categories"""
    JOURNAL = 'JOURNAL', 'Journal'
    PAYMENT = 'PAYMENT', 'Payment'
    RECEIPT = 'RECEIPT', 'Receipt'
    CONTRA = 'CONTRA', 'Contra'
    SALES = 'SALES', 'Sales'
    PURCHASE = 'PURCHASE', 'Purchase'
    DEBIT_NOTE = 'DEBIT_NOTE', 'Debit Note'
    CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note'


class VoucherType(CompanyScopedModel):
    """
    Voucher type configuration.
    Defines different types of accounting entries.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    
    category = models.CharField(
        max_length=30,
        choices=VoucherCategory.choices
    )
    
    is_accounting = models.BooleanField(
        default=True,
        help_text="Posts to accounting ledgers"
    )
    is_inventory = models.BooleanField(
        default=False,
        help_text="Affects inventory (stock movements)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Voucher Types"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'category']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class VoucherStatus(models.TextChoices):
    """Enum for voucher status"""
    DRAFT = 'DRAFT', 'Draft'
    POSTED = 'POSTED', 'Posted'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REVERSED = 'REVERSED', 'Reversed'


class Voucher(CompanyScopedModel):
    """
    Accounting voucher.
    Core double-entry accounting entity.
    All financial transactions post through vouchers.
    """
    voucher_type = models.ForeignKey(
        VoucherType,
        on_delete=models.PROTECT,
        related_name='vouchers'
    )
    
    financial_year = models.ForeignKey(
        "company.FinancialYear",
        on_delete=models.PROTECT,
        related_name='vouchers'
    )
    
    voucher_number = models.CharField(max_length=50, db_index=True)
    
    date = models.DateField(db_index=True)
    
    narration = models.TextField(
        blank=True,
        help_text="Description/remarks for the voucher"
    )
    
    status = models.CharField(
        max_length=20,
        choices=VoucherStatus.choices,
        default=VoucherStatus.DRAFT
    )
    
    # Reversal tracking
    reversed_voucher = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='reversals',
        help_text="If this is a reversal, link to original voucher"
    )
    
    # Reference fields
    reference_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="External reference (invoice #, cheque #, etc.)"
    )
    reference_date = models.DateField(
        null=True,
        blank=True
    )
    
    # Posting timestamp
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when voucher was posted"
    )
    
    # Reversal tracking
    reversed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when voucher was reversed"
    )
    reversal_reason = models.TextField(
        blank=True,
        help_text="Reason for reversal"
    )
    reversal_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reversed_vouchers',
        help_text="User who reversed this voucher"
    )

    class Meta:
        verbose_name_plural = "Vouchers"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "voucher_type", "financial_year", "voucher_number"],
                name="unique_voucher_per_company_type_fy",
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'voucher_number']),
            models.Index(fields=['company', 'date', 'status']),
            models.Index(fields=['company', 'voucher_type', 'status']),
            models.Index(fields=['company', 'financial_year']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'status']),
        ]

    def __str__(self):
        return f"{self.voucher_number} - {self.voucher_type.name} ({self.date})"


class EntryType(models.TextChoices):
    """Enum for debit/credit"""
    DR = 'DR', 'Debit'
    CR = 'CR', 'Credit'


class VoucherLine(BaseModel):
    """
    Voucher line entries.
    Implements double-entry bookkeeping: Σ(DR) = Σ(CR)
    """
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    line_no = models.PositiveIntegerField(
        help_text="Line number for ordering"
    )
    
    ledger = models.ForeignKey(
        "accounting.Ledger",
        on_delete=models.PROTECT,
        related_name='voucher_lines'
    )
    
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    
    entry_type = models.CharField(
        max_length=2,
        choices=EntryType.choices
    )
    
    # Optional cost center for dimensional analysis
    cost_center = models.ForeignKey(
        "accounting.CostCenter",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='voucher_lines'
    )
    
    # Optional bill-wise tracking
    against_voucher = models.ForeignKey(
        Voucher,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='settled_lines',
        help_text="For bill-wise accounting (receivables/payables)"
    )
    
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Voucher Lines"
        ordering = ['voucher', 'line_no']
        indexes = [
            models.Index(fields=['voucher', 'line_no']),
            models.Index(fields=['ledger', 'entry_type']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(entry_type__in=['DR', 'CR']),
                name="valid_dr_cr",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="voucher_line_amount_positive",
            ),
        ]

    def __str__(self):
        return f"{self.voucher.voucher_number} Line {self.line_no}: {self.ledger.name} {self.entry_type} {self.amount}"


class Payment(CompanyScopedModel):
    """
    Payment/Receipt tracking model.
    Links to voucher for posting and tracks payment application to invoices.
    """
    voucher = models.OneToOneField(
        Voucher,
        on_delete=models.PROTECT,
        related_name='payment',
        help_text="Associated voucher for posting"
    )
    
    party = models.ForeignKey(
        "party.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='payments',
        help_text="Party for advance payments without invoice"
    )
    
    bank_account = models.ForeignKey(
        "accounting.Ledger",
        on_delete=models.PROTECT,
        related_name='payments',
        help_text="Bank/cash ledger for payment"
    )
    
    payment_date = models.DateField(db_index=True)
    
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cheque/transfer reference"
    )
    
    payment_mode = models.CharField(
        max_length=50,
        choices=[
            ('CASH', 'Cash'),
            ('CHEQUE', 'Cheque'),
            ('BANK_TRANSFER', 'Bank Transfer'),
            ('UPI', 'UPI'),
            ('CARD', 'Card'),
            ('OTHER', 'Other'),
        ],
        default='CASH'
    )
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('DRAFT', 'Draft'),
            ('POSTED', 'Posted'),
            ('CANCELLED', 'Cancelled'),
        ],
        default='DRAFT'
    )
    
    posted_voucher = models.ForeignKey(
        Voucher,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='posted_payments',
        help_text="Posted voucher reference"
    )
    
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Payments"
        indexes = [
            models.Index(fields=['company', 'payment_date']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['company', 'party']),
        ]

    def __str__(self):
        return f"Payment {self.voucher.voucher_number} - {self.payment_date}"


class PaymentLine(BaseModel):
    """
    Individual payment application lines.
    Tracks how payment is applied to specific invoices or as advance.
    """
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='lines'
    )
    
    invoice = models.ForeignKey(
        "invoice.Invoice",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='payment_lines',
        help_text="Invoice being paid (null for advance)"
    )
    
    amount_applied = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text="Amount applied to this invoice or advance"
    )
    
    line_no = models.PositiveIntegerField(
        help_text="Line number in payment"
    )
    
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "Payment Lines"
        ordering = ['payment', 'line_no']
        indexes = [
            models.Index(fields=['payment', 'line_no']),
            models.Index(fields=['invoice']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_applied__gt=0),
                name="payment_line_amount_positive",
            ),
        ]

    def __str__(self):
        return f"Payment {self.payment.id} Line {self.line_no}: {self.amount_applied}"
