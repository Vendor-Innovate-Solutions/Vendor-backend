"""
Retailer registration and management APIs.
Handles retailer onboarding, approval workflow, and company discovery.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.db.models import Q

from core.permissions.base import RolePermission
from apps.party.models import RetailerUser, Party
from apps.company.models import Company

User = get_user_model()


# ================================================================
# RETAILER REGISTRATION
# ================================================================
class RetailerRegisterView(APIView):
    """
    Public endpoint for retailer self-registration.
    
    POST: Create user account and request company access
    No authentication required
    """
    authentication_classes = []  # Public endpoint
    permission_classes = []
    
    def post(self, request):
        """
        Register new retailer and request access to company.
        
        Body:
            email: Retailer email (becomes username)
            password: Account password
            company_id: Company UUID to request access
            full_name: Optional full name
            phone: Optional phone number
        """
        data = request.data
        
        # Validate required fields
        if not all(key in data for key in ['email', 'password', 'company_id']):
            return Response(
                {'error': 'email, password, and company_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Check if user already exists
            if User.objects.filter(username=data['email']).exists():
                return Response(
                    {'error': 'User with this email already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify company exists and is active
            try:
                company = Company.objects.get(id=data['company_id'], is_active=True)
            except Company.DoesNotExist:
                return Response(
                    {'error': 'Company not found or inactive'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Check if already registered for this company
            existing = RetailerUser.objects.filter(
                user__username=data['email'],
                company=company
            ).first()
            
            if existing:
                return Response(
                    {
                        'error': f'Already registered for this company',
                        'status': existing.status
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create user account
            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                password=data['password'],
                first_name=data.get('full_name', '').split()[0] if 'full_name' in data else '',
                last_name=' '.join(data.get('full_name', '').split()[1:]) if 'full_name' in data else ''
            )
            
            # Create retailer mapping (pending approval)
            retailer_user = RetailerUser.objects.create(
                user=user,
                company=company,
                status='PENDING'
            )
            
            return Response({
                'detail': 'Registration pending approval',
                'user_id': str(user.id),
                'retailer_user_id': str(retailer_user.id),
                'company_name': company.name,
                'status': 'PENDING',
                'message': f'Your request to access {company.name} has been submitted. An administrator will review your request.'
            }, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Registration failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# RETAILER APPROVAL (Admin)
# ================================================================
class RetailerApproveView(APIView):
    """
    Admin endpoint to approve/reject retailer access requests.
    
    POST: Approve retailer access
    Requires: ADMIN role
    """
    permission_classes = [RolePermission.require(['ADMIN'])]
    
    def post(self, request, retailer_id):
        """
        Approve retailer access request.
        
        Body:
            party_id: Optional party ID to link retailer to existing customer
            create_party: If true and no party_id, create new party
        """
        company = request.company
        
        try:
            # Get retailer user with company scoping
            retailer_user = RetailerUser.objects.select_related(
                'user', 'company'
            ).get(id=retailer_id, company=company)
            
            # Check current status
            if retailer_user.status == 'APPROVED':
                return Response(
                    {'error': 'Retailer already approved'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Link to party if provided or create new
            party_id = request.data.get('party_id')
            create_party = request.data.get('create_party', False)
            
            if party_id:
                # Link to existing party
                party = Party.objects.get(id=party_id, company=company)
                retailer_user.party = party
            elif create_party:
                # Create new party for retailer
                from apps.accounting.models import Ledger, LedgerGroup
                
                # Get or create Sundry Debtors group
                debtors_group = LedgerGroup.objects.filter(
                    company=company,
                    name__icontains='sundry debtor'
                ).first()
                
                if not debtors_group:
                    debtors_group = LedgerGroup.objects.filter(
                        company=company,
                        group_type='CURRENT_ASSET'
                    ).first()
                
                # Create ledger for party
                ledger = Ledger.objects.create(
                    company=company,
                    name=f"{retailer_user.user.email} (Retailer)",
                    ledger_group=debtors_group,
                    created_by=request.user
                )
                
                # Create party
                party = Party.objects.create(
                    company=company,
                    name=retailer_user.user.get_full_name() or retailer_user.user.email,
                    party_type='CUSTOMER',
                    ledger=ledger,
                    email=retailer_user.user.email,
                    phone=request.data.get('phone', ''),
                    is_retailer=True,
                    created_by=request.user
                )
                retailer_user.party = party
            
            # Approve access
            retailer_user.status = 'APPROVED'
            retailer_user.approved_by = request.user
            retailer_user.approved_at = timezone.now()
            retailer_user.save(update_fields=['status', 'approved_by', 'approved_at', 'party'])
            
            return Response({
                'detail': 'Retailer approved successfully',
                'retailer_user_id': str(retailer_user.id),
                'user_email': retailer_user.user.email,
                'status': 'APPROVED',
                'party_id': str(retailer_user.party.id) if retailer_user.party else None
            })
            
        except RetailerUser.DoesNotExist:
            return Response(
                {'error': 'Retailer user not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Party.DoesNotExist:
            return Response(
                {'error': 'Party not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Approval failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RetailerRejectView(APIView):
    """
    Admin endpoint to reject retailer access requests.
    
    POST: Reject retailer access
    Requires: ADMIN role
    """
    permission_classes = [RolePermission.require(['ADMIN'])]
    
    def post(self, request, retailer_id):
        """
        Reject retailer access request.
        
        Body:
            reason: Reason for rejection
        """
        company = request.company
        reason = request.data.get('reason', '')
        
        try:
            retailer_user = RetailerUser.objects.get(id=retailer_id, company=company)
            
            if retailer_user.status == 'REJECTED':
                return Response(
                    {'error': 'Retailer already rejected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            retailer_user.status = 'REJECTED'
            retailer_user.rejection_reason = reason
            retailer_user.save(update_fields=['status', 'rejection_reason'])
            
            return Response({
                'detail': 'Retailer access rejected',
                'retailer_user_id': str(retailer_user.id),
                'status': 'REJECTED'
            })
            
        except RetailerUser.DoesNotExist:
            return Response(
                {'error': 'Retailer user not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class RetailerListView(APIView):
    """
    Admin endpoint to list retailer access requests.
    
    GET: List all retailer users for company
    Requires: ADMIN or ACCOUNTANT role
    """
    permission_classes = [RolePermission.require(['ADMIN', 'ACCOUNTANT'])]
    
    def get(self, request):
        """List retailer users with optional status filter."""
        company = request.company
        filter_status = request.query_params.get('status')
        
        qs = RetailerUser.objects.filter(company=company).select_related(
            'user', 'party', 'approved_by'
        ).order_by('-created_at')
        
        if filter_status:
            qs = qs.filter(status=filter_status)
        
        data = [{
            'id': str(ru.id),
            'user': {
                'id': str(ru.user.id),
                'email': ru.user.email,
                'full_name': ru.user.get_full_name()
            },
            'party': {
                'id': str(ru.party.id),
                'name': ru.party.name
            } if ru.party else None,
            'status': ru.status,
            'approved_by': ru.approved_by.email if ru.approved_by else None,
            'approved_at': ru.approved_at.isoformat() if ru.approved_at else None,
            'rejection_reason': ru.rejection_reason,
            'created_at': ru.created_at.isoformat()
        } for ru in qs]
        
        return Response(data)


# ================================================================
# COMPANY DISCOVERY (Public)
# ================================================================
class CompanyDiscoveryView(APIView):
    """
    Public endpoint for retailers to discover companies.
    
    GET: Search companies by name, city, or category
    No authentication required
    """
    authentication_classes = []
    permission_classes = []
    
    def get(self, request):
        """
        Search for companies.
        
        Query params:
            q: Search query (searches name)
            city: Filter by city
            category: Filter by business category
        """
        query = request.query_params.get('q', '').strip()
        city = request.query_params.get('city', '').strip()
        category = request.query_params.get('category', '').strip()
        
        qs = Company.objects.filter(is_active=True)
        
        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(business_name__icontains=query)
            )
        
        if city:
            qs = qs.filter(city__icontains=city)
        
        if category:
            qs = qs.filter(business_category__icontains=category)
        
        # Limit results
        qs = qs[:50]
        
        data = [{
            'id': str(c.id),
            'name': c.name,
            'business_name': c.business_name if hasattr(c, 'business_name') else c.name,
            'city': c.city if hasattr(c, 'city') else None,
            'state': c.state if hasattr(c, 'state') else None,
            'gstin': c.gstin if hasattr(c, 'gstin') else None
        } for c in qs]
        
        return Response(data)
