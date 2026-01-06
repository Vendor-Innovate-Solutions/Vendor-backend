"""
Custom User model for authentication.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Base authentication identity.
    Do NOT store company or accounting data here.
    """
    phone = models.CharField(max_length=20, blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)

    # Types of access — can be both
    is_internal_user = models.BooleanField(
        default=False,
        help_text="ERP staff member with company access"
    )
    is_portal_user = models.BooleanField(
        default=False,
        help_text="Retailer/customer portal user"
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

