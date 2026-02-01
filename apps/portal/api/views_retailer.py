"""
Retailer registration and management APIs.
Handles retailer onboarding, approval workflow, and company discovery.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.db.models import Q

from core.permissions.base import RolePermission
from apps.party.models import RetailerUser, Party, PartyAddress
from apps.company.models import Company

User = get_user_model()


# ================================================================
# RETAILER REGISTRATION (For already authenticated users)
# ================================================================
class RetailerRegisterView(APIView):
    """
    Endpoint for authenticated users to complete retailer profile.
    
    POST: Create retailer profile and optionally request company access
    Requires: Authenticated user (already registered via /users/register/)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Complete retailer profile for authenticated user.
        
        Body:
            company_id: Optional company UUID to request access (can be done later)
            business_name: Optional business/shop name
            address: Optional address details
                - address_line1
                - city
                - state
                - postal_code
                - country (default: IN)
        """
        data = request.data
        user = request.user
        
        try:
            # If company_id provided, verify company exists and request access
            company = None
            company_id = data.get('company_id')
            
            if company_id:
                try:
                    company = Company.objects.get(id=company_id, is_active=True)
                except Company.DoesNotExist:
                    return Response(
                        {'error': 'Company not found or inactive'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Check if already registered for this company
                existing = RetailerUser.objects.filter(
                    user=user,
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
            
            # Update user's selected_role to RETAILER if not set
            if not user.selected_role:
                user.selected_role = 'RETAILER'
                user.is_portal_user = True
                user.save()
            
            response_data = {
                'detail': 'Retailer profile updated',
                'user_id': str(user.id),
                'email': user.email,
                'phone': user.phone,
            }
            
            # Create retailer mapping if company provided
            if company:
                retailer_user = RetailerUser.objects.create(
                    user=user,
                    company=company,
                    status='PENDING'
                )
                response_data.update({
                    'retailer_user_id': str(retailer_user.id),
                    'company_name': company.name,
                    'company_id': str(company.id),
                    'status': 'PENDING',
                    'message': f'Your request to access {company.name} has been submitted. An administrator will review your request.'
                })
            else:
                response_data.update({
                    'message': 'Profile updated. You can discover and request access to companies later.'
                })
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
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
# RETAILER PROFILE COMPLETION (with address)
# ================================================================
class RetailerCompleteProfileView(APIView):
    """
    Complete retailer profile with business address.
    Called after registration to add business details.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Complete retailer profile with business address.
        
        Body:
            company_id: Optional company UUID to request access
            business_name: Optional business/shop name
            address: Address details
                - address_line1 (required)
                - city (required)
                - state (required)
                - postal_code (required)
                - country (default: IN)
        """
        data = request.data
        user = request.user
        
        try:
            # Update user's role to RETAILER
            if not user.selected_role:
                user.selected_role = 'RETAILER'
            user.is_portal_user = True
            user.save()
            
            response_data = {
                'detail': 'Retailer profile completed',
                'user_id': str(user.id),
                'email': user.email,
                'phone': user.phone,
            }
            
            # Handle company access request if company_id provided
            company = None
            company_id = data.get('company_id')
            
            if company_id:
                try:
                    company = Company.objects.get(id=company_id, is_active=True)
                except Company.DoesNotExist:
                    return Response(
                        {'error': 'Company not found or inactive'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Check if already registered for this company
                existing = RetailerUser.objects.filter(
                    user=user,
                    company=company
                ).first()
                
                if not existing:
                    retailer_user = RetailerUser.objects.create(
                        user=user,
                        company=company,
                        status='PENDING'
                    )
                    response_data.update({
                        'retailer_user_id': str(retailer_user.id),
                        'company_name': company.name,
                        'company_id': str(company.id),
                        'status': 'PENDING',
                        'message': f'Profile completed. Your request to access {company.name} is pending approval.'
                    })
                else:
                    response_data.update({
                        'retailer_user_id': str(existing.id),
                        'company_name': company.name,
                        'company_id': str(company.id),
                        'status': existing.status,
                        'message': f'Profile completed. You already have a request for {company.name} with status: {existing.status}'
                    })
            else:
                response_data.update({
                    'message': 'Profile completed. You can discover and request access to companies later.'
                })
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Profile completion failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ================================================================
# RETAILER APPROVAL (Admin)
# ================================================================
class RetailerApproveView(APIView):
    """
    Admin endpoint to approve/reject retailer access requests.
    
    POST: Approve retailer access
    Requires: ADMIN or OWNER role
    """
    permission_classes = [IsAuthenticated, RolePermission.require(['ADMIN', 'OWNER'])]
    
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
    Requires: ADMIN or OWNER role
    """
    permission_classes = [IsAuthenticated, RolePermission.require(['ADMIN', 'OWNER'])]
    
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
    Requires: ADMIN or ACCOUNTANT role (OWNER also allowed)
    """
    permission_classes = [IsAuthenticated, RolePermission.require(['ADMIN', 'ACCOUNTANT', 'OWNER'])]
    
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
