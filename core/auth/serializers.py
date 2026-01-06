"""
Custom JWT serializers with ERP-specific claims.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class ERPTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that includes:
    - username
    - active_company (current company context)
    - roles (all CompanyUser roles for this user)
    - is_internal_user / is_portal_user flags
    
    Frontend can use these claims to:
    - Display active company
    - Show/hide features based on roles
    - Route to correct dashboard (internal vs retailer)
    """
    
    @classmethod
    def get_token(cls, user):
        """
        Add custom claims to JWT token.
        
        Args:
            user: User instance
        
        Returns:
            Token with custom claims
        """
        token = super().get_token(user)
        
        # Basic user info
        token['username'] = user.username
        token['email'] = user.email or ''
        
        # User type flags
        token['is_internal_user'] = getattr(user, 'is_internal_user', False)
        token['is_portal_user'] = getattr(user, 'is_portal_user', False)
        
        # Active company context
        if user.active_company:
            token['active_company'] = {
                'id': str(user.active_company.id),
                'name': user.active_company.name,
                'code': user.active_company.code,
            }
        else:
            token['active_company'] = None
        
        # User roles (for internal users)
        if hasattr(user, 'company_memberships'):
            roles = list(
                user.company_memberships
                .filter(is_active=True)
                .values_list('role', flat=True)
            )
            token['roles'] = roles
        else:
            token['roles'] = []
        
        # Available companies (for company switching)
        if hasattr(user, 'company_memberships'):
            companies = list(
                user.company_memberships
                .filter(is_active=True)
                .values('company__id', 'company__name', 'company__code', 'role')
            )
            token['available_companies'] = [
                {
                    'id': str(c['company__id']),
                    'name': c['company__name'],
                    'code': c['company__code'],
                    'role': c['role'],
                }
                for c in companies
            ]
        else:
            token['available_companies'] = []
        
        # Retailer info (for portal users)
        if hasattr(user, 'retailer_profile'):
            try:
                retailer = user.retailer_profile
                token['retailer'] = {
                    'party_id': str(retailer.party.id),
                    'party_name': retailer.party.name,
                    'can_place_orders': retailer.can_place_orders,
                    'can_view_balance': retailer.can_view_balance,
                }
            except Exception:
                token['retailer'] = None
        else:
            token['retailer'] = None
        
        return token
