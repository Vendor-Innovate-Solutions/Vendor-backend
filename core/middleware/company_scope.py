"""
Company scope middleware for multi-tenant isolation
"""
from django.utils.deprecation import MiddlewareMixin


class CompanyScopeMiddleware(MiddlewareMixin):
    """
    Resolves and validates company context for every request.
    
    Resolution order:
    1. X-Company-ID header (frontend can switch companies)
    2. user.active_company (default company for user)
    3. None (no company = no data access)
    
    Access validation:
    - Internal users: Must have CompanyUser membership
    - Portal users: Must have RetailerUser access
    - No validation match: request.company = None (empty querysets)
    """
    
    def process_request(self, request):
        """
        Inject company context into request object.
        
        Sets request.company to:
        - Company object if user has valid access
        - None if unauthenticated or no valid access
        """
        user = request.user
        
        # 1) Unauthenticated users → no company context
        if not user.is_authenticated:
            request.company = None
            return
        
        # 2) Resolve company ID from header first (allows frontend switching)
        company_id = request.headers.get('X-Company-ID')
        
        # 3) Fallback to user's active company if no header
        if not company_id and user.active_company:
            request.company = user.active_company
            return
        
        # 4) If no header and no active_company → try to get default company from CompanyUser
        if not company_id:
            from apps.company.models import CompanyUser
            # Try to get user's default company
            company_user = CompanyUser.objects.select_related('company').filter(
                user=user,
                is_active=True,
                is_default=True
            ).first()
            
            if not company_user:
                # Fallback to any active company membership
                company_user = CompanyUser.objects.select_related('company').filter(
                    user=user,
                    is_active=True
                ).first()
            
            if company_user:
                request.company = company_user.company
            else:
                request.company = None
            return
        
        # 5) Resolve company_id to Company object
        from apps.company.models import Company
        try:
            company = Company.objects.get(id=company_id, is_active=True)
        except Company.DoesNotExist:
            request.company = None
            return  # Invalid company ID → no access
        
        # 6) Validate user has access to this company
        if self._validate_company_access(user, company):
            request.company = company
        else:
            request.company = None  # User has no access → block
    
    def _validate_company_access(self, user, company):
        """
        Validate that user has permission to access this company.
        
        Args:
            user: User instance
            company: Company instance
        
        Returns:
            bool: True if user has access, False otherwise
        """
        from apps.company.models import CompanyUser
        from apps.portal.models import RetailerUser, RetailerCompanyAccess
        
        # Check internal user access (ERP staff)
        if CompanyUser.objects.filter(
            user=user,
            company=company,
            is_active=True
        ).exists():
            return True
        
        # Check retailer user access (customer portal)
        # Use RetailerCompanyAccess to check approved access
        try:
            retailer = RetailerUser.objects.get(user=user)
            if RetailerCompanyAccess.objects.filter(
                retailer=retailer,
                company=company,
                status='APPROVED'
            ).exists():
                return True
        except RetailerUser.DoesNotExist:
            pass
        
        # No matching access record
        return False
