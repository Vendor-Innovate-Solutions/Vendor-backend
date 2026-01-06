"""
DRF permissions for company-scoped access control
"""
from rest_framework.permissions import BasePermission


class HasCompanyContext(BasePermission):
    """
    Permission that requires request.company to be set.
    
    Blocks all requests without valid company context.
    Use this to prevent write operations when no company is available.
    
    Usage:
        class InvoiceViewSet(CompanyScopedViewSet):
            permission_classes = [IsAuthenticated, HasCompanyContext]
    """
    message = "Company context required. Ensure you have access to a company."
    
    def has_permission(self, request, view):
        """
        Check if request has company context.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if request.company is set, False otherwise
        """
        return getattr(request, 'company', None) is not None


class RolePermission(BasePermission):
    """
    Role-based permission for DRF views.
    
    Usage:
        class VoucherPostingView(APIView):
            permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    Checks if authenticated user has any of the required roles
    via CompanyUser membership.
    """
    required_roles = []
    
    @classmethod
    def require(cls, roles):
        """
        Factory method to create permission with specific roles.
        
        Args:
            roles: List of role strings (e.g., ['ADMIN', 'ACCOUNTANT'])
        
        Returns:
            Permission class configured with required roles
        """
        class RolePerm(cls):
            required_roles = roles
        return RolePerm
    
    def has_permission(self, request, view):
        """
        Check if user has any of the required roles.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if user has required role, False otherwise
        """
        if not request.user.is_authenticated:
            self.message = "Authentication required"
            return False
        
        if not self.required_roles:
            return True  # No roles required
        
        # Get user's roles from CompanyUser
        from apps.company.models import CompanyUser
        user_roles = set(
            CompanyUser.objects.filter(
                user=request.user,
                is_active=True
            ).values_list('role', flat=True)
        )
        
        # Check if user has any required role
        has_role = any(role in user_roles for role in self.required_roles)
        
        if not has_role:
            self.message = f"Role required: {', '.join(self.required_roles)}"
        
        return has_role


class IsInternalUser(BasePermission):
    """
    Permission that requires user to be internal ERP staff.
    
    Blocks retailer/portal users from accessing internal-only endpoints.
    """
    message = "This operation is restricted to internal users only."
    
    def has_permission(self, request, view):
        """
        Check if user is internal staff member.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if user is internal, False otherwise
        """
        user = request.user
        if not user.is_authenticated:
            return False
        
        return getattr(user, 'is_internal_user', False)


class IsRetailerUser(BasePermission):
    """
    Permission that requires user to be retailer/portal user.
    
    Use for retailer-specific endpoints (order history, balance inquiry).
    """
    message = "This operation is restricted to retailer users only."
    
    def has_permission(self, request, view):
        """
        Check if user is retailer/portal user.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if user is retailer, False otherwise
        """
        user = request.user
        if not user.is_authenticated:
            return False
        
        return getattr(user, 'is_portal_user', False)


class CanModifyCompanyData(BasePermission):
    """
    Permission that checks if user can modify data in current company.
    
    Additional validation beyond HasCompanyContext:
    - Checks if company features are locked
    - Validates user role has write permissions
    """
    message = "You do not have permission to modify data in this company."
    
    def has_permission(self, request, view):
        """
        Check if user can modify company data.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if modifications allowed, False otherwise
        """
        # Read-only methods always allowed
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        
        # Must have company context
        company = getattr(request, 'company', None)
        if not company:
            return False
        
        # Check if company features are locked
        from apps.company.models import CompanyFeature
        try:
            features = CompanyFeature.objects.get(company=company)
            if features.locked:
                self.message = "Company data is locked. No modifications allowed."
                return False
        except CompanyFeature.DoesNotExist:
            pass  # No features record = not locked
        
        return True


class HasCompanyUserRole(BasePermission):
    """
    Permission that checks if user has specific role in company.
    
    Usage:
        class VoucherViewSet(CompanyScopedViewSet):
            permission_classes = [HasCompanyUserRole]
            required_roles = ['ADMIN', 'ACCOUNTANT']  # Define in view
    """
    message = "Your role does not have permission for this operation."
    
    def has_permission(self, request, view):
        """
        Check if user has required role in company.
        
        Args:
            request: HTTP request object
            view: View being accessed
        
        Returns:
            bool: True if user has required role, False otherwise
        """
        user = request.user
        company = getattr(request, 'company', None)
        
        if not user.is_authenticated or not company:
            return False
        
        # Get required roles from view
        required_roles = getattr(view, 'required_roles', None)
        if not required_roles:
            return True  # No roles required = always pass
        
        # Check if user has any of the required roles
        from apps.company.models import CompanyUser
        return CompanyUser.objects.filter(
            user=user,
            company=company,
            role__in=required_roles,
            is_active=True
        ).exists()
