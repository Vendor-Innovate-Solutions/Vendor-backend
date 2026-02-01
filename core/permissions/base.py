"""
Custom permissions classes for API access control.
"""
from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """
    Permission class that allows access only to users in the 'admin' group.
    """
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name="admin").exists()


class IsEmployeeUser(BasePermission):
    """
    Permission class that allows access only to users in the 'employee' group.
    """
    def has_permission(self, request, view):
        return request.user and request.user.groups.filter(name="employee").exists()


class HasCompanyContext(BasePermission):
    """
    Permission class that requires a company context to be set.
    Checks for company_id in request data or user's active company.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if company_id is in request data
        company_id = request.data.get('company') or request.query_params.get('company')
        if company_id:
            return True
        
        # Check if user has an active company (if user model has this field)
        if hasattr(request.user, 'active_company') and request.user.active_company:
            return True
        
        return False


class RolePermission(BasePermission):
    """
    Permission class for role-based access control.
    Checks if user has required role for the action.
    """
    # Role hierarchy
    ROLE_HIERARCHY = {
        'super_admin': 100,
        'ADMIN': 80,
        'admin': 80,
        'ACCOUNTANT': 70,
        'accountant': 70,
        'manager': 60,
        'MANAGER': 60,
        'employee': 40,
        'user': 20,
    }
    
    def __init__(self, required_role='user'):
        self.required_role = required_role
        super().__init__()
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user's role
        user_role = getattr(request.user, 'role', 'user')
        
        # Check if user's role meets requirement
        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        required_level = self.ROLE_HIERARCHY.get(self.required_role, 0)
        
        return user_level >= required_level
    
    @classmethod
    def require(cls, roles):
        """
        Factory method to create a permission class that requires any of the given roles.
        Used as: RolePermission.require(["ADMIN", "ACCOUNTANT"])
        """
        class MultiRolePermission(BasePermission):
            def has_permission(self, request, view):
                if not request.user or not request.user.is_authenticated:
                    return False
                
                from apps.company.models import CompanyUser
                
                # Get user role from multiple sources
                user_role = getattr(request.user, 'role', None)
                
                # Check CompanyUser role - try with request.company first
                if hasattr(request, 'company') and request.company:
                    company_user = CompanyUser.objects.filter(
                        user=request.user,
                        company=request.company,
                        is_active=True
                    ).first()
                    if company_user:
                        user_role = company_user.role
                else:
                    # Fallback: get role from any active CompanyUser membership
                    company_user = CompanyUser.objects.filter(
                        user=request.user,
                        is_active=True
                    ).first()
                    if company_user:
                        user_role = company_user.role
                
                if not user_role:
                    user_role = 'user'
                
                # Normalize roles for comparison
                normalized_roles = [r.upper() for r in roles]
                user_role_upper = user_role.upper()
                
                # OWNER has all permissions (highest level)
                if user_role_upper == 'OWNER':
                    return True
                
                # Check if user has any of the required roles
                return user_role_upper in normalized_roles
        
        return MultiRolePermission
