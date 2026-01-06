"""
Service-layer decorators for access control.
"""
from functools import wraps
from django.core.exceptions import PermissionDenied


def role_required(roles):
    """
    Decorator to enforce role-based access control in service functions.
    
    Args:
        roles: List of allowed role strings (e.g., ['ADMIN', 'ACCOUNTANT'])
    
    Usage:
        @role_required(['ADMIN'])
        def post_sales_order(user, order_id):
            # Only users with ADMIN role can execute this
            ...
        
        @role_required(['ADMIN', 'ACCOUNTANT'])
        def reverse_voucher(user, voucher_id, reason):
            # Users with ADMIN or ACCOUNTANT role can execute
            ...
    
    Raises:
        PermissionDenied: If user doesn't have required role
    """
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            # Import here to avoid circular dependency
            from apps.company.models import CompanyUser
            
            if not user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get user's active roles
            user_roles = set(
                CompanyUser.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('role', flat=True)
            )
            
            # Check if user has any required role
            if not any(role in user_roles for role in roles):
                raise PermissionDenied(
                    f"Role required: {', '.join(roles)}. "
                    f"You have: {', '.join(user_roles) or 'none'}"
                )
            
            return func(user, *args, **kwargs)
        return wrapper
    return decorator


def company_required(func):
    """
    Decorator to ensure user has active company context.
    
    Usage:
        @company_required
        def create_invoice(user, invoice_data):
            # Ensures user.active_company is set
            company = user.active_company
            ...
    
    Raises:
        PermissionDenied: If user has no active company
    """
    @wraps(func)
    def wrapper(user, *args, **kwargs):
        if not hasattr(user, 'active_company') or not user.active_company:
            raise PermissionDenied(
                "No active company. Please select a company first."
            )
        return func(user, *args, **kwargs)
    return wrapper


def internal_user_only(func):
    """
    Decorator to restrict function to internal ERP users only.
    
    Usage:
        @internal_user_only
        def manage_company_settings(user, company_id):
            # Only internal users can access this
            ...
    
    Raises:
        PermissionDenied: If user is not internal user
    """
    @wraps(func)
    def wrapper(user, *args, **kwargs):
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required")
        
        if not getattr(user, 'is_internal_user', False):
            raise PermissionDenied(
                "This operation is restricted to internal users only"
            )
        
        return func(user, *args, **kwargs)
    return wrapper


def retailer_user_only(func):
    """
    Decorator to restrict function to retailer/portal users only.
    
    Usage:
        @retailer_user_only
        def place_order(user, order_data):
            # Only retailer users can access this
            ...
    
    Raises:
        PermissionDenied: If user is not retailer user
    """
    @wraps(func)
    def wrapper(user, *args, **kwargs):
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required")
        
        if not getattr(user, 'is_portal_user', False):
            raise PermissionDenied(
                "This operation is restricted to retailer users only"
            )
        
        return func(user, *args, **kwargs)
    return wrapper


def combined_role_and_company(roles):
    """
    Decorator that combines role checking and company requirement.
    
    Args:
        roles: List of allowed role strings
    
    Usage:
        @combined_role_and_company(['ADMIN', 'ACCOUNTANT'])
        def post_voucher(user, voucher_id):
            # Ensures both role and company
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(user, *args, **kwargs):
            # Import here to avoid circular dependency
            from apps.company.models import CompanyUser
            
            if not user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Check company
            if not hasattr(user, 'active_company') or not user.active_company:
                raise PermissionDenied("No active company selected")
            
            # Check roles
            user_roles = set(
                CompanyUser.objects.filter(
                    user=user,
                    is_active=True
                ).values_list('role', flat=True)
            )
            
            if not any(role in user_roles for role in roles):
                raise PermissionDenied(
                    f"Role required: {', '.join(roles)}"
                )
            
            return func(user, *args, **kwargs)
        return wrapper
    return decorator
