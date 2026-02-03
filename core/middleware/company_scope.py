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
    
    def _authenticate_jwt(self, request):
        """
        Manually authenticate JWT token since DRF authentication only runs in view layer.
        This allows middleware to access the authenticated user.
        """
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ', 1)[1]
        jwt_auth = JWTAuthentication()
        
        try:
            validated_token = jwt_auth.get_validated_token(token)
            user = jwt_auth.get_user(validated_token)
            return user
        except (InvalidToken, TokenError) as e:
            print(f">>> JWT authentication failed: {e}")
            return None
        except Exception as e:
            print(f">>> Unexpected JWT error: {e}")
            return None
    
    def process_request(self, request):
        """
        Inject company context into request object.
        
        Sets request.company to:
        - Company object if user has valid access
        - None if unauthenticated or no valid access
        """
        print(f"\n>>> MIDDLEWARE CALLED: {request.path}")
        print(f">>> Authorization header: {request.headers.get('Authorization', 'NOT PRESENT')[:50] if request.headers.get('Authorization') else 'NOT PRESENT'}")
        
        # Try to authenticate via JWT first (since DRF auth runs in view layer)
        user = request.user
        if not user.is_authenticated:
            jwt_user = self._authenticate_jwt(request)
            if jwt_user:
                user = jwt_user
                # Set user on request so subsequent code can use it
                request.user = jwt_user
                request._jwt_authenticated = True  # Flag for debugging
                print(f">>> JWT authenticated user: {user.email}")
        
        print(f">>> User authenticated: {user.is_authenticated}")
        if user.is_authenticated:
            print(f">>> User email: {user.email}")
        
        # 1) Unauthenticated users → no company context
        if not user.is_authenticated:
            request.company = None
            print(">>> Unauthenticated - setting company to None")
            return
        
        # Debug output
        print(f"\n=== CompanyScopeMiddleware DEBUG ===")
        print(f"User: {user.email}")
        print(f"Active Company: {user.active_company}")
        
        # 2) Resolve company ID from header first (allows frontend switching)
        company_id = request.headers.get('X-Company-ID')
        print(f"X-Company-ID header: {company_id}")
        
        # 3) Fallback to user's active company if no header
        if not company_id and user.active_company:
            print(f"✓ Using active_company: {user.active_company.id} - {user.active_company.name}")
            request.company = user.active_company
            print(f"=== END DEBUG ===\n")
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
        has_access = self._validate_company_access(user, company)
        print(f"Validating access to company {company.id}: {has_access}")
        if has_access:
            request.company = company
            print(f"✓ Access granted to company {company.id}")
        else:
            print(f"✗ User {user.email} DENIED access to company {company.id}")
            request.company = None  # User has no access → block
        print(f"=== END DEBUG ===\n")
    
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
