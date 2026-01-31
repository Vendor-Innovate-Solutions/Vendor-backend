"""
Authorization enforcement for company-scoped resources.
Every protected API must verify user has CompanyUser access with appropriate role.
"""
from rest_framework.permissions import BasePermission
from rest_framework import status
from apps.company.models import CompanyUser


class HasCompanyAccess(BasePermission):
    """
    Permission to check if user has access to a company.
    User must have an active CompanyUser record with that company.
    
    Usage in views:
    permission_classes = [IsAuthenticated, HasCompanyAccess]
    
    The view must pass company_id in URL parameter: <uuid:company_id>
    """
    
    message = "You do not have access to this company"
    
    def has_permission(self, request, view):
        # All authenticated users can access
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user has access to company"""
        # Get company_id from view kwargs
        company_id = view.kwargs.get('company_id') or view.kwargs.get('pk')
        
        if not company_id:
            return False
        
        # Check if user has active CompanyUser for this company
        try:
            company_user = CompanyUser.objects.get(
                user=request.user,
                company_id=company_id,
                is_active=True
            )
            return True
        except CompanyUser.DoesNotExist:
            return False


class CompanyUserPermission(BasePermission):
    """
    Check if user has CompanyUser access AND specific role.
    Must be used with company_id URL parameter.
    
    Usage:
    permission_classes = [CompanyUserPermission]
    required_roles = ['ADMIN', 'MANAGER']  # In the view
    """
    
    message = "You do not have permission to access this resource"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get company_id from URL kwargs or query params
        company_id = (
            view.kwargs.get('company_id') or 
            view.kwargs.get('pk') or 
            request.query_params.get('company_id')
        )
        
        if not company_id:
            # Try to get from request.data (POST/PUT)
            company_id = request.data.get('company_id') if isinstance(request.data, dict) else None
        
        if not company_id:
            return False
        
        # Check if user has active CompanyUser for this company
        try:
            company_user = CompanyUser.objects.get(
                user=request.user,
                company_id=company_id,
                is_active=True
            )
            
            # Attach to request for use in view
            request.company_user = company_user
            request.active_company_id = company_id
            
            # Check role if required_roles is specified in view
            required_roles = getattr(view, 'required_roles', None)
            if required_roles and company_user.role not in required_roles:
                self.message = f"This action requires one of these roles: {', '.join(required_roles)}"
                return False
            
            return True
        
        except CompanyUser.DoesNotExist:
            self.message = "You do not have access to this company"
            return False


class IsCompanyOwner(BasePermission):
    """
    Check if user is OWNER of the company.
    """
    message = "Only company owners can perform this action"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        company_id = view.kwargs.get('company_id') or view.kwargs.get('pk')
        
        if not company_id:
            return False
        
        try:
            company_user = CompanyUser.objects.get(
                user=request.user,
                company_id=company_id,
                role='OWNER',
                is_active=True
            )
            return True
        except CompanyUser.DoesNotExist:
            return False


class IsCompanyAdmin(BasePermission):
    """
    Check if user is ADMIN or OWNER of the company.
    """
    message = "Only company admins can perform this action"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        company_id = view.kwargs.get('company_id') or view.kwargs.get('pk')
        
        if not company_id:
            return False
        
        try:
            company_user = CompanyUser.objects.get(
                user=request.user,
                company_id=company_id,
                role__in=['OWNER', 'ADMIN'],
                is_active=True
            )
            return True
        except CompanyUser.DoesNotExist:
            return False


class IsInternalUser(BasePermission):
    """
    Check if user is marked as internal user.
    Internal users = ERP staff (not portal users like retailers)
    """
    message = "This resource is only available for internal users"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_internal_user


class IsExternalUser(BasePermission):
    """
    Check if user is marked as external/portal user.
    External users = Retailers, Suppliers, Partners
    """
    message = "This resource is only available for external users"
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.is_portal_user
