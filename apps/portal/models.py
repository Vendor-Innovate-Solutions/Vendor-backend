"""
Retailer portal models - customer/retailer login and access management.
"""
from django.db import models
from django.conf import settings
from core.models import BaseModel
from apps.party.models import RetailerUser as PartyRetailerUser


class RetailerUser(BaseModel):
    """
    Login-enabled user for retailer/customer ordering.
    Links a User account to a Party (business entity).
    
    NOTE: This model is DEPRECATED. Use apps.party.models.RetailerUser instead.
    Kept for migration compatibility only.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='retailer_profile'
    )
    party = models.ForeignKey(
        'party.Party',
        on_delete=models.CASCADE,
        related_name='portal_retailer_users',
        help_text="Business party this user represents"
    )

    is_primary_contact = models.BooleanField(
        default=False,
        help_text="Primary contact for this retailer"
    )
    can_place_orders = models.BooleanField(
        default=True,
        help_text="Permission to create orders"
    )
    can_view_balance = models.BooleanField(
        default=True,
        help_text="Permission to view account balance"
    )
    can_view_statements = models.BooleanField(
        default=True,
        help_text="Permission to view ledger statements"
    )

    class Meta:
        verbose_name = 'Retailer User'
        verbose_name_plural = 'Retailer Users'
        indexes = [
            models.Index(fields=['party']),
            models.Index(fields=['is_primary_contact']),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.party.name}"


class RetailerCompanyAccess(BaseModel):
    """
    Retailer is approved to place orders with a Company.
    Enables discovery, approvals, blocking, marketplace logic.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('BLOCKED', 'Blocked'),
        ('REJECTED', 'Rejected'),
    ]

    retailer = models.ForeignKey(
        PartyRetailerUser,  # Use the RetailerUser from party app
        on_delete=models.CASCADE,
        related_name='company_accesses'
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.CASCADE,
        related_name='retailer_accesses'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    # Approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_retailer_accesses'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this access request"
    )

    class Meta:
        unique_together = ('retailer', 'company')
        verbose_name = 'Retailer Company Access'
        verbose_name_plural = 'Retailer Company Accesses'
        indexes = [
            models.Index(fields=['retailer', 'status']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.retailer.party.name} → {self.company.name} ({self.status})"
