"""
Authentication API views.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from core.auth.serializers import ERPTokenObtainPairSerializer
from apps.company.models import CompanyUser
from apps.portal.models import RetailerCompanyAccess


class LoginView(TokenObtainPairView):
    """
    JWT Login endpoint with custom claims.
    
    POST /auth/login/
    {
        "email": "user@example.com",
        "password": "password123"
    }
    
    Response:
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhb...",
        "refresh": "eyJ0eXAiOiJKV1QiLCJhb..."
    }
    
    Token includes custom claims:
    - username, email
    - active_company (id, name, code)
    - roles (all active CompanyUser roles)
    - available_companies (for switching)
    - is_internal_user, is_portal_user
    - retailer (party info for portal users)
    """
    serializer_class = ERPTokenObtainPairSerializer


class RefreshView(TokenRefreshView):
    """
    JWT Refresh endpoint.
    
    POST /auth/refresh/
    {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhb..."
    }
    
    Response:
    {
        "access": "eyJ0eXAiOiJKV1QiLCJhb..."
    }
    """
    pass


class LogoutView(APIView):
    """
    Logout endpoint (blacklist refresh token).
    
    POST /auth/logout/
    {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhb..."
    }
    
    Requires: rest_framework_simplejwt.token_blacklist in INSTALLED_APPS
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {'detail': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SwitchCompanyView(APIView):
    """
    Switch active company for authenticated user.
    
    POST /auth/switch-company/
    {
        "company_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    
    Response:
    {
        "detail": "Company switched successfully",
        "active_company": {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "ABC Corp",
            "code": "ABC"
        }
    }
    
    Validates:
    - User has CompanyUser access to requested company (internal users)
    - User has RetailerCompanyAccess with status='APPROVED' (portal users)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        company_id = request.data.get('company_id')
        
        if not company_id:
            return Response(
                {'error': 'company_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check internal user access
        if user.is_internal_user:
            company_user = CompanyUser.objects.filter(
                user=user,
                company_id=company_id,
                is_active=True
            ).select_related('company').first()
            
            if company_user:
                user.active_company = company_user.company
                user.save(update_fields=['active_company'])
                
                return Response({
                    'detail': 'Company switched successfully',
                    'active_company': {
                        'id': str(company_user.company.id),
                        'name': company_user.company.name,
                        'code': company_user.company.code,
                    }
                }, status=status.HTTP_200_OK)
        
        # Check retailer user access
        if user.is_portal_user:
            try:
                retailer = user.retailer_profile
                access = RetailerCompanyAccess.objects.filter(
                    retailer=retailer,
                    company_id=company_id,
                    status='APPROVED'
                ).select_related('company').first()
                
                if access:
                    user.active_company = access.company
                    user.save(update_fields=['active_company'])
                    
                    return Response({
                        'detail': 'Company switched successfully',
                        'active_company': {
                            'id': str(access.company.id),
                            'name': access.company.name,
                            'code': access.company.code,
                        }
                    }, status=status.HTTP_200_OK)
            except Exception:
                pass
        
        # No valid access found
        return Response(
            {'error': 'You do not have access to this company'},
            status=status.HTTP_403_FORBIDDEN
        )


class MeView(APIView):
    """
    Get current user info.
    
    GET /auth/me/
    
    Response:
    {
        "id": "123",
        "username": "john.doe",
        "email": "john@example.com",
        "is_internal_user": true,
        "is_portal_user": false,
        "active_company": {
            "id": "456",
            "name": "ABC Corp",
            "code": "ABC"
        },
        "roles": ["ADMIN", "ACCOUNTANT"],
        "available_companies": [...]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Build response
        data = {
            'id': str(user.id),
            'username': user.username,
            'email': user.email or '',
            'is_internal_user': user.is_internal_user,
            'is_portal_user': user.is_portal_user,
        }
        
        # Active company
        if user.active_company:
            data['active_company'] = {
                'id': str(user.active_company.id),
                'name': user.active_company.name,
                'code': user.active_company.code,
            }
        else:
            data['active_company'] = None
        
        # Roles (for internal users)
        if user.is_internal_user:
            roles = list(
                CompanyUser.objects.filter(user=user, is_active=True)
                .values_list('role', flat=True)
            )
            data['roles'] = roles
            
            # Available companies
            companies = CompanyUser.objects.filter(
                user=user,
                is_active=True
            ).select_related('company').values(
                'company__id', 'company__name', 'company__code', 'role'
            )
            data['available_companies'] = [
                {
                    'id': str(c['company__id']),
                    'name': c['company__name'],
                    'code': c['company__code'],
                    'role': c['role'],
                }
                for c in companies
            ]
        
        # Retailer info (for portal users)
        if user.is_portal_user:
            try:
                retailer = user.retailer_profile
                data['retailer'] = {
                    'party_id': str(retailer.party.id),
                    'party_name': retailer.party.name,
                    'can_place_orders': retailer.can_place_orders,
                    'can_view_balance': retailer.can_view_balance,
                }
                
                # Available companies (via RetailerCompanyAccess)
                accesses = RetailerCompanyAccess.objects.filter(
                    retailer=retailer,
                    status='APPROVED'
                ).select_related('company').values(
                    'company__id', 'company__name', 'company__code'
                )
                data['available_companies'] = [
                    {
                        'id': str(a['company__id']),
                        'name': a['company__name'],
                        'code': a['company__code'],
                    }
                    for a in accesses
                ]
            except Exception:
                data['retailer'] = None
                data['available_companies'] = []
        
        return Response(data, status=status.HTTP_200_OK)
