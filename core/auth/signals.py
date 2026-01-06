"""
Signals for auth app - auto-assign default company on user creation.
"""
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.conf import settings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def assign_default_company_on_creation(sender, instance, created, **kwargs):
    """
    Auto-assign first available company as active_company when user is created.
    
    This prevents new users from having no company context.
    
    Args:
        sender: User model class
        instance: User instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if not created:
        return  # Only run on creation
    
    # Skip if user already has active_company set
    if instance.active_company:
        return
    
    # Try to find first company user has access to
    from apps.company.models import CompanyUser
    
    first_membership = CompanyUser.objects.filter(
        user=instance,
        is_active=True
    ).select_related('company').first()
    
    if first_membership:
        instance.active_company = first_membership.company
        instance.save(update_fields=['active_company'])


@receiver(post_save, sender='company.CompanyUser')
def set_active_company_on_first_membership(sender, instance, created, **kwargs):
    """
    When a CompanyUser membership is created, set it as active_company
    if user doesn't have one yet.
    
    This handles the case where User is created first, then CompanyUser is created.
    
    Args:
        sender: CompanyUser model class
        instance: CompanyUser instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if not created:
        return  # Only run on creation
    
    user = instance.user
    
    # If user has no active_company and this membership is active, set it
    if not user.active_company and instance.is_active:
        user.active_company = instance.company
        user.save(update_fields=['active_company'])


@receiver(post_save, sender='portal.RetailerUser')
def set_active_company_for_retailer(sender, instance, created, **kwargs):
    """
    When a RetailerUser is created, check for approved company access
    and set as active_company if user doesn't have one.
    
    Args:
        sender: RetailerUser model class
        instance: RetailerUser instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional signal arguments
    """
    if not created:
        return  # Only run on creation
    
    user = instance.user
    
    # If user already has active_company, don't override
    if user.active_company:
        return
    
    # Find first approved company access
    from apps.portal.models import RetailerCompanyAccess
    
    first_access = RetailerCompanyAccess.objects.filter(
        retailer=instance,
        status='APPROVED'
    ).select_related('company').first()
    
    if first_access:
        user.active_company = first_access.company
        user.save(update_fields=['active_company'])
