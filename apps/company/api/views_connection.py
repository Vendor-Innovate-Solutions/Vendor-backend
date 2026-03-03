"""
Company connection APIs for retailer-manufacturer relationships.
Handles company code generation and retailer connections.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction

from apps.company.models import Company, CompanyUser
from apps.portal.models import RetailerCompanyAccess
from apps.party.models import Party, RetailerUser
from core.permissions.base import RolePermission


class GenerateCompanyCodeView(APIView):
    """
    Generate or retrieve company code for retailers to join.
    Manufacturers use this to get their company code to share with retailers.
    
    GET /company/connection/generate-code/
    
    Response:
    {
        "company_code": "ABC001",
        "company_name": "ABC Manufacturing",
        "message": "Share this code with retailers to allow them to connect to your company"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get company code for manufacturer's active company."""
        user = request.user
        
        # Get user's active company (use filter().first() to handle multiple records)
        company_user = CompanyUser.objects.select_related('company').filter(
            user=user,
            is_active=True,
            is_default=True
        ).first()
        
        if not company_user:
            # Fallback: get any active company membership
            company_user = CompanyUser.objects.select_related('company').filter(
                user=user,
                is_active=True
            ).first()
        
        if not company_user:
            return Response(
                {
                    "error": "No active company found for this user",
                    "detail": "Please create or select a company first"
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        company = company_user.company
        return Response({
            "company_code": company.code,
            "company_name": company.name,
            "company_id": str(company.id),
            "message": "Share this code with retailers to allow them to connect to your company"
        })


class JoinByCompanyCodeView(APIView):
    """
    Retailer joins a company using company code.
    
    POST /retailer/join-by-company-code/
    
    Request:
    {
        "company_code": "ABC001"
    }
    
    Response:
    {
        "message": "Successfully connected to company",
        "connection": {
            "id": "uuid",
            "company_id": "uuid",
            "company_name": "ABC Manufacturing",
            "status": "APPROVED",
            "connected_at": "2026-02-01T..."
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Join company by code."""
        user = request.user
        company_code = request.data.get('company_code', '').strip().upper()
        
        if not company_code:
            return Response(
                {"error": "Company code is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify user is a retailer
        if user.selected_role != 'RETAILER':
            return Response(
                {
                    "error": "Only retailers can join companies using company code",
                    "current_role": user.selected_role
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Find company by code
        try:
            company = Company.objects.get(code=company_code, is_active=True, is_deleted=False)
        except Company.DoesNotExist:
            return Response(
                {"error": f"No active company found with code '{company_code}'"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create retailer user for this specific company
        retailer = RetailerUser.objects.filter(user=user, company=company).first()
        party = retailer.party if retailer else None

        if not party:
            # First, try to reuse an existing party in this company by email
            party = Party.objects.filter(
                company=company,
                email=user.email
            ).first()

        if not party:
            # Create a new party for the retailer
            from apps.accounting.models import Ledger, AccountGroup
            from apps.company.models import FinancialYear

            ledger = None

            # Try to create a ledger if AccountGroup exists
            debtors_group = AccountGroup.objects.filter(
                company=company,
                name__icontains='sundry debtor'
            ).first()

            if not debtors_group:
                debtors_group = AccountGroup.objects.filter(
                    company=company,
                    nature='ASSET'
                ).first()

            # Get the active financial year for the company (required by Ledger model)
            active_fy = FinancialYear.objects.filter(
                company=company,
                is_current=True
            ).first()

            if not active_fy:
                # Fallback: get the most recent non-closed FY for this company
                active_fy = FinancialYear.objects.filter(
                    company=company,
                    is_closed=False
                ).order_by('-start_date').first()

            if not active_fy:
                # Last resort: any FY for this company
                active_fy = FinancialYear.objects.filter(
                    company=company
                ).order_by('-start_date').first()

            # Only create ledger if we have both a valid group AND a financial year
            if debtors_group and active_fy:
                ledger = Ledger.objects.create(
                    company=company,
                    name=f"{user.get_full_name() or user.email} (Retailer)",
                    code=f"RET-{user.id}",
                    group=debtors_group,
                    opening_balance_fy=active_fy,
                )


            # Create party (ledger can be null)
            party = Party.objects.create(
                company=company,
                name=user.get_full_name() or user.email,
                party_type='CUSTOMER',
                ledger=ledger,
                email=user.email,
                phone=user.phone or '',
                is_retailer=True
            )

        if retailer:
            if retailer.party_id != party.id:
                retailer.party = party
                retailer.save(update_fields=['party'])
        else:
            retailer = RetailerUser.objects.create(
                user=user,
                company=company,
                party=party,
                status='PENDING'
            )
        
        # Check if connection already exists
        existing_access = RetailerCompanyAccess.objects.filter(
            retailer=retailer,
            company=company
        ).first()
        
        if existing_access:
            if existing_access.status == 'APPROVED':
                return Response(
                    {
                        "error": "You are already connected to this company",
                        "status": existing_access.status,
                        "connection_id": str(existing_access.id)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Reconnect suspended/rejected/pending access via valid company code.
            now = timezone.now()
            existing_access.status = 'APPROVED'
            existing_access.approved_by = None
            existing_access.approved_at = now
            existing_access.notes = f"Reconnected via company code: {company_code}"
            existing_access.save(update_fields=['status', 'approved_by', 'approved_at', 'notes'])

            retailer_updates = []
            if retailer.status != 'APPROVED':
                retailer.status = 'APPROVED'
                retailer_updates.append('status')
            if retailer.approved_at is None:
                retailer.approved_at = now
                retailer_updates.append('approved_at')
            if retailer_updates:
                retailer.save(update_fields=retailer_updates)

            return Response(
                {
                    "message": f"Successfully reconnected to {company.name}",
                    "connection": {
                        "id": str(existing_access.id),
                        "company_id": str(company.id),
                        "company_name": company.name,
                        "company_code": company.code,
                        "status": existing_access.status,
                        "connected_at": existing_access.approved_at.isoformat()
                    }
                },
                status=status.HTTP_200_OK
            )
        
        # Create approved connection (auto-approve when joining by company code)
        now = timezone.now()
        retailer_updates = []
        if retailer.status != 'APPROVED':
            retailer.status = 'APPROVED'
            retailer_updates.append('status')
        if retailer.approved_at is None:
            retailer.approved_at = now
            retailer_updates.append('approved_at')
        if retailer_updates:
            retailer.save(update_fields=retailer_updates)

        connection = RetailerCompanyAccess.objects.create(
            retailer=retailer,
            company=company,
            status='APPROVED',
            approved_by=None,  # Auto-approved via company code
            approved_at=now,
            notes=f"Auto-approved via company code: {company_code}"
        )
        
        return Response({
            "message": f"Successfully connected to {company.name}",
            "connection": {
                "id": str(connection.id),
                "company_id": str(company.id),
                "company_name": company.name,
                "company_code": company.code,
                "status": connection.status,
                "connected_at": connection.approved_at.isoformat()
            }
        }, status=status.HTTP_201_CREATED)


class RetailerCompanyListView(APIView):
    """
    Get list of companies the retailer is connected to.
    
    GET /retailer/companies/
    
    Response:
    [
        {
            "id": "uuid",
            "company_id": "uuid",
            "company_name": "ABC Manufacturing",
            "company_code": "ABC001",
            "status": "APPROVED",
            "connected_at": "2026-02-01T..."
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List connected companies for retailer."""
        user = request.user
        
        # Get all retailer profiles for this user (one per company)
        retailer_ids = RetailerUser.objects.filter(user=user).values_list('id', flat=True)
        
        if not retailer_ids:
            return Response([], status=status.HTTP_200_OK)
        
        # Get connections for all retailer profiles
        connections = RetailerCompanyAccess.objects.filter(
            retailer_id__in=retailer_ids
        ).select_related('company').order_by('-approved_at', '-created_at')
        
        # Filter by status if provided
        filter_status = request.query_params.get('status')
        if filter_status:
            connections = connections.filter(status=filter_status.upper())
        
        data = [{
            "id": str(conn.id),
            "company_id": str(conn.company.id),
            "company_name": conn.company.name,
            "company_code": conn.company.code,
            "status": conn.status,
            "connected_at": conn.approved_at.isoformat() if conn.approved_at else conn.created_at.isoformat(),
            "notes": conn.notes
        } for conn in connections]
        
        return Response(data)


class UpdateConnectionStatusView(APIView):
    """
    Update retailer connection status for manufacturer dashboard actions.

    POST /company/update-connection/

    Request:
    {
        "connection_id": "uuid",  # RetailerUser id from portal/retailers list
        "status": "approved" | "suspended" | "blocked" | "rejected"
    }
    """
    permission_classes = [IsAuthenticated, RolePermission.require(['ADMIN', 'OWNER'])]

    @transaction.atomic
    def post(self, request):
        connection_id = request.data.get('connection_id')
        target_status = str(request.data.get('status', '')).strip().lower()

        if not connection_id:
            return Response(
                {"error": "connection_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if target_status not in ('approved', 'suspended', 'blocked', 'rejected'):
            return Response(
                {"error": "Invalid status. Use approved, suspended, blocked, or rejected."},
                status=status.HTTP_400_BAD_REQUEST
            )

        company = getattr(request, 'company', None)
        if not company:
            company_user = CompanyUser.objects.select_related('company').filter(
                user=request.user,
                is_active=True,
                is_default=True
            ).first()

            if not company_user:
                company_user = CompanyUser.objects.select_related('company').filter(
                    user=request.user,
                    is_active=True
                ).first()

            if not company_user:
                return Response(
                    {"error": "No active company found for this user"},
                    status=status.HTTP_404_NOT_FOUND
                )

            company = company_user.company

        try:
            retailer_user = RetailerUser.objects.get(
                id=connection_id,
                company=company
            )
        except RetailerUser.DoesNotExist:
            return Response(
                {"error": "Connection not found for this company"},
                status=status.HTTP_404_NOT_FOUND
            )

        access = RetailerCompanyAccess.objects.filter(
            retailer=retailer_user,
            company=company
        ).first()

        if not access:
            access = RetailerCompanyAccess.objects.create(
                retailer=retailer_user,
                company=company,
                status='PENDING'
            )

        now = timezone.now()

        if target_status == 'approved':
            retailer_user.status = 'APPROVED'
            retailer_user.approved_at = now
            retailer_user.rejection_reason = ''
            access.status = 'APPROVED'
            access.approved_by = request.user
            access.approved_at = now
            message = "Connection approved"
        elif target_status in ('suspended', 'blocked'):
            retailer_user.status = 'SUSPENDED'
            access.status = 'BLOCKED'
            message = "Connection suspended"
        else:
            retailer_user.status = 'REJECTED'
            access.status = 'REJECTED'
            message = "Connection rejected"

        retailer_user.save(update_fields=['status', 'approved_at', 'rejection_reason'])
        access.save(update_fields=['status', 'approved_by', 'approved_at'])

        return Response({
            "message": message,
            "connection_id": str(retailer_user.id),
            "retailer_status": retailer_user.status,
            "access_status": access.status
        })
