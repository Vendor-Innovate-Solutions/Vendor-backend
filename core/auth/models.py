"""
Custom User model for authentication.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    """Enum for user's primary business role (post-signup selection)"""
    MANUFACTURER = 'MANUFACTURER', 'Manufacturer'
    RETAILER = 'RETAILER', 'Retailer'
    SUPPLIER = 'SUPPLIER', 'Supplier'
    DISTRIBUTOR = 'DISTRIBUTOR', 'Distributor'
    LOGISTICS = 'LOGISTICS', 'Logistics Provider'
    SERVICE_PROVIDER = 'SERVICE_PROVIDER', 'Service Provider'


class User(AbstractUser):
    """
    Base authentication identity.
    Do NOT store company or accounting data here.
    """
    phone = models.CharField(max_length=20, blank=True, null=True)
    phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Types of access — can be both
    is_internal_user = models.BooleanField(
        default=False,
        help_text="ERP staff member with company access"
    )
    is_portal_user = models.BooleanField(
        default=False,
        help_text="Retailer/customer portal user"
    )
    
    # Role selection (post-signup)
    selected_role = models.CharField(
        max_length=50,
        choices=UserRole.choices,
        null=True,
        blank=True,
        help_text="User's primary business role selected during onboarding"
    )
    
    # Multi-company active context
    active_company = models.ForeignKey(
        'company.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_users',
        help_text="Currently selected company for this user session"
    )

    def __str__(self):
        return self.username

