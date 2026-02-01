"""
Company-related models for ERP system.
Models: Currency, Company, Address, CompanyFeature, CompanyUser, FinancialYear, Sequence
"""
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from core.models import BaseModel, CompanyScopedModel


class Currency(BaseModel):
    """
    Global currency master.
    """
    code = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=50)
    symbol = models.CharField(max_length=10)
    decimal_places = models.PositiveSmallIntegerField(default=2)

    class Meta:
        verbose_name_plural = "Currencies"
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class CompanyType(models.TextChoices):
    """Enum for company types"""
    PRIVATE_LIMITED = 'PRIVATE_LIMITED', 'Private Limited'
    PUBLIC_LIMITED = 'PUBLIC_LIMITED', 'Public Limited'
    PARTNERSHIP = 'PARTNERSHIP', 'Partnership'
    PROPRIETORSHIP = 'PROPRIETORSHIP', 'Proprietorship'
    LLP = 'LLP', 'Limited Liability Partnership'


class Company(BaseModel):
    """
    Multi-tenant company master.
    Each company represents an independent ERP instance.
    """
    code = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255)
    company_type = models.CharField(
        max_length=50,
        choices=CompanyType.choices,
        default=CompanyType.PRIVATE_LIMITED
    )
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=20, default='en')
    base_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        related_name='companies'
    )
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Companies"
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active', 'is_deleted']),
        ]

    def __str__(self):
        return self.name


class AddressType(models.TextChoices):
    """Enum for address types"""
    REGISTERED = 'REGISTERED', 'Registered Office'
    CORPORATE = 'CORPORATE', 'Corporate Office'
    BRANCH = 'BRANCH', 'Branch'
    WAREHOUSE = 'WAREHOUSE', 'Warehouse'
    BILLING = 'BILLING', 'Billing'
    SHIPPING = 'SHIPPING', 'Shipping'


class Address(CompanyScopedModel):
    """
    Company address master.
    """
    address_type = models.CharField(
        max_length=30,
        choices=AddressType.choices
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)

    class Meta:
        verbose_name_plural = "Addresses"
        indexes = [
            models.Index(fields=['company', 'address_type']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.address_type} - {self.city}"


class CompanyFeature(CompanyScopedModel):
    """
    Feature flags per company.
    'locked' prevents any financial modifications (accounting freeze).
    """
    inventory_enabled = models.BooleanField(default=True)
    accounting_enabled = models.BooleanField(default=True)
    payroll_enabled = models.BooleanField(default=False)
    gst_enabled = models.BooleanField(default=False)
    locked = models.BooleanField(
        default=False,
        help_text="When locked, no financial transactions can be modified"
    )

    class Meta:
        verbose_name_plural = "Company Features"

    def __str__(self):
        return f"Features for {self.company.name}"


class UserRole(models.TextChoices):
    """Enum for user roles"""
    ADMIN = 'ADMIN', 'Administrator'
    MANAGER = 'MANAGER', 'Manager'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    STOCK_KEEPER = 'STOCK_KEEPER', 'Stock Keeper'
    SALES = 'SALES', 'Sales Person'
    VIEWER = 'VIEWER', 'View Only'


class CompanyUser(CompanyScopedModel):
    """
    Internal ERP operator: accountants, warehouse staff, admin, etc.
    Maps users to companies with roles.
    A user can belong to multiple companies with different roles.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company_memberships'
    )
    role = models.CharField(
        max_length=50,
        choices=UserRole.choices,
        default=UserRole.VIEWER
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default company when user logs in"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "company")
        verbose_name_plural = "Company Users"
        indexes = [
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.company.name} ({self.role})"


class FinancialYear(CompanyScopedModel):
    """
    Financial year master per company.
    Enforces:
    - Only one is_current=True per company
    - No overlapping dates per company
    - start_date < end_date
    """
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_closed = models.BooleanField(
        default=False,
        help_text="Once closed, no transactions can be posted to this FY"
    )

    class Meta:
        verbose_name_plural = "Financial Years"
        constraints = [
            models.UniqueConstraint(
                fields=["company"],
                condition=models.Q(is_current=True),
                name="one_current_fy_per_company",
            ),
            models.CheckConstraint(
                condition=models.Q(start_date__lt=models.F('end_date')),
                name="fy_start_before_end",
            ),
        ]
        indexes = [
            models.Index(fields=['company', 'is_current']),
            models.Index(fields=['company', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.name} ({self.company.name})"

    def clean(self):
        """Validate no overlapping financial years within the same company"""
        if not self.company_id:
            return

        overlapping = FinancialYear.objects.filter(
            company=self.company
        ).exclude(pk=self.pk).filter(
            models.Q(start_date__lte=self.end_date) &
            models.Q(end_date__gte=self.start_date)
        )

        if overlapping.exists():
            raise ValidationError(
                "Financial year dates overlap with existing financial year"
            )


class ResetPeriod(models.TextChoices):
    """Enum for sequence reset periods"""
    NEVER = 'NEVER', 'Never Reset'
    YEARLY = 'YEARLY', 'Reset Yearly'
    MONTHLY = 'MONTHLY', 'Reset Monthly'
    DAILY = 'DAILY', 'Reset Daily'


class Sequence(CompanyScopedModel):
    """
    Auto-numbering sequences for vouchers, invoices, etc.
    Ensures unique numbering per company per key.
    Thread-safe incrementing must be handled at service layer with select_for_update().
    """
    key = models.CharField(
        max_length=100,
        help_text="Unique identifier or compound key (company_id:code:fy_id)"
    )
    prefix = models.CharField(max_length=20, blank=True)
    last_value = models.PositiveIntegerField(default=0)
    reset_period = models.CharField(
        max_length=20,
        choices=ResetPeriod.choices,
        default=ResetPeriod.YEARLY
    )

    class Meta:
        unique_together = ("company", "key")
        verbose_name_plural = "Sequences"
        indexes = [
            models.Index(fields=['company', 'key']),
        ]

    def __str__(self):
        return f"{self.key} - {self.company.name}"
