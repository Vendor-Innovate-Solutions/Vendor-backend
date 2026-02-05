"""
Post-login routing middleware for role-based redirection.
Enforces server-side routing logic based on user state.
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class PostLoginRoutingMiddleware(MiddlewareMixin):
    """
    Middleware to enforce post-login routing based on user state.
    
    Rules:
    1. If user.selected_role is None → redirect to /select-role
    2. If user.selected_role == MANUFACTURER and user has no company → redirect to /onboarding/company
    3. If user has multiple companies and no active_company → redirect to /select-company
    
    This middleware applies only to protected endpoints (requires authentication).
    """
    
    # Endpoints that don't require role/company validation
    EXEMPT_PATHS = [
        '/auth/login',
        '/auth/logout',
        '/auth/signup',
        '/auth/select-role',
        '/api/users/select-role',  # Add the actual API path
        '/me/context',
        '/api/users/me/context',   # Add the actual API path
        '/invites/',
        '/partner/profile',
        '/health',
        '/admin',
    ]
    
    def should_check_routing(self, request):
        """Check if this request should be validated for routing"""
        # Only validate authenticated requests
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Skip exempt paths
        for exempt_path in self.EXEMPT_PATHS:
            if request.path.startswith(exempt_path):
                return False
        
        # Skip non-API requests
        if not request.path.startswith('/api/'):
            return False
        
        return True
    
    def get_routing_redirect(self, user):
        """
        Determine if user should be redirected.
        Returns (should_redirect, redirect_path, error_data) tuple
        """
        # Check 1: Role not selected
        if user.selected_role is None:
            return True, '/auth/select-role', {
                'code': 'ROLE_NOT_SELECTED',
                'message': 'Please select your role to continue',
                'redirect_to': '/auth/select-role'
            }
        
        # Check 2: Manufacturer without company
        if user.selected_role == 'MANUFACTURER':
            has_company = user.company_memberships.filter(is_active=True).exists()
            if not has_company:
                return True, '/onboarding/company', {
                    'code': 'NO_COMPANY',
                    'message': 'Please create or join a company to continue',
                    'redirect_to': '/onboarding/company',
                    'role': 'MANUFACTURER'
                }
        
        # Check 3: Multiple companies, no active company selected
        company_count = user.company_memberships.filter(is_active=True).count()
        if company_count > 1 and user.active_company is None:
            return True, '/select-company', {
                'code': 'SELECT_COMPANY',
                'message': 'Please select your active company',
                'redirect_to': '/select-company'
            }
        
        return False, None, None
    
    def process_request(self, request):
        """Process request and enforce routing"""
        if not self.should_check_routing(request):
            return None
        
        should_redirect, redirect_path, error_data = self.get_routing_redirect(request.user)
        
        if should_redirect:
            # Return JSON response with redirect information
            # Use JsonResponse instead of DRF Response to avoid rendering issues
            response_data = {
                'error': 'REDIRECT_REQUIRED',
                'status_code': 307,
                **error_data
            }
            
            response = JsonResponse(response_data, status=307)
            response['Location'] = redirect_path
            return response
        
        return None
