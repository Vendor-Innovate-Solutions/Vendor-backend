"""
Party management models for ERP system.
Models: Party, PartyAddress, PartyBankAccount, RetailerUser
"""
from django.db import models
from django.contrib.auth import get_user_model
from core.models import BaseModel, CompanyScopedModel

User = get_user_model()


class PartyType(models.TextChoices):
    """Enum for party types"""
    CUSTOMER = 'CUSTOMER', 'Customer'
    SUPPLIER = 'SUPPLIER', 'Supplier'
    BOTH = 'BOTH', 'Both Customer & Supplier'
    EMPLOYEE = 'EMPLOYEE', 'Employee'
    OTHER = 'OTHER', 'Other'


class Party(CompanyScopedModel):
    """
    Party master (customers, suppliers, etc.).
    Every party is linked to a ledger for accounting integration.
    """
    name = models.CharField(max_length=255)
    party_type = models.CharField(
        max_length=20,
        choices=PartyType.choices
    )
    
    # Direct ledger link (every party has ONE control ledger)
    # Made nullable to allow retailer connections when accounting groups don't exist yet
    ledger = models.OneToOneField(
        "accounting.Ledger",
        on_delete=models.PROTECT,
        related_name='party',
        null=True,
        blank=True,
        help_text="Associated accounting ledger"
    )
    
    # Contact details
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    
    # Business identifiers
    gstin = models.CharField(
        max_length=15,
        blank=True,
        help_text="GST Identification Number"
    )
    pan = models.CharField(
        max_length=10,
        blank=True,
        help_text="PAN Number"
    )
    
    # Portal access
    is_retailer = models.BooleanField(
        default=False,
        help_text="Enable portal login for this party"
    )
    
    # Credit terms
    credit_limit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Maximum credit allowed"
    )
    credit_days = models.PositiveIntegerField(
        default=0,
        help_text="Payment terms in days"
    )
    
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Parties"
        indexes = [
            models.Index(fields=['company', 'party_type']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'gstin']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.party_type})"


class AddressType(models.TextChoices):
    """Enum for address types"""
    BILLING = 'BILLING', 'Billing'
    SHIPPING = 'SHIPPING', 'Shipping'
    REGISTERED = 'REGISTERED', 'Registered Office'
    CONTACT = 'CONTACT', 'Contact'


class PartyAddress(BaseModel):
    """
    Multiple addresses per party.
    Supports billing, shipping, and other address types.
    """
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    address_type = models.CharField(
        max_length=20,
        choices=AddressType.choices
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    is_default = models.BooleanField(
        default=False,
        help_text="Default address for this type"
    )

    class Meta:
        verbose_name_plural = "Party Addresses"
        indexes = [
            models.Index(fields=['party', 'address_type']),
        ]

    def __str__(self):
        return f"{self.party.name} - {self.address_type} ({self.city})"


class PartyBankAccount(BaseModel):
    """
    Bank account details for parties.
    Used for payment processing and reconciliation.
    """
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name='bank_accounts'
    )
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    ifsc = models.CharField(
        max_length=20,
        help_text="IFSC Code (for Indian banks)"
    )
    swift_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="SWIFT/BIC code (for international)"
    )
    branch = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(
        default=False,
        help_text="Primary account for payments"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Party Bank Accounts"
        indexes = [
            models.Index(fields=['party', 'is_primary']),
        ]

    def __str__(self):
        return f"{self.party.name} - {self.bank_name} ({self.account_number})"


class RetailerUserStatus(models.TextChoices):
    """Status for retailer user access"""
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'
    SUSPENDED = 'SUSPENDED', 'Suspended'


class RetailerUser(BaseModel):
    """
    Links external retailer users to supplier/manufacturer companies.
    
    Retailers register and request access to view catalog, pricing,
    and place orders. Admin must approve before granting access.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='retailer_mappings',
        help_text="The retailer user account"
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='retailer_users',
        help_text="Supplier/manufacturer company being accessed"
    )
    party = models.ForeignKey(
        Party,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='retailer_users',
        help_text="Associated party record (customer)"
    )
    status = models.CharField(
        max_length=20,
        choices=RetailerUserStatus.choices,
        default=RetailerUserStatus.PENDING
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='retailer_approvals',
        help_text="Admin who approved access"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        unique_together = [('user', 'company')]
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['company', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.email} → {self.company.name} ({self.status})"
