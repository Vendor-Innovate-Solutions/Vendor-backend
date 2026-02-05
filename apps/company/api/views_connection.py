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
from apps.portal.models import RetailerCompanyAccess, RetailerUser
from apps.party.models import Party


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
        
        # Check if user already has a RetailerUser record (OneToOne with User)
        existing_retailer = RetailerUser.objects.filter(user=user).first()
        
        if existing_retailer:
            # Check if there's already an access record for this company
            existing_access = RetailerCompanyAccess.objects.filter(
                retailer=existing_retailer,
                company=company
            ).first()
            
            if existing_access:
                return Response(
                    {
                        "error": "You are already connected to this company",
                        "status": existing_access.status,
                        "connection_id": str(existing_access.id)
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            retailer = existing_retailer
            party = existing_retailer.party
        else:
            # Create retailer profile if doesn't exist
            # First, check if user has a party in this company
            party = Party.objects.filter(
                company=company,
                email=user.email
            ).first()
            
            if not party:
                # Create a new party for the retailer
                from apps.accounting.models import Ledger, AccountGroup
                from apps.company.models import FinancialYear
                import uuid
                
                # Get active financial year
                financial_year = FinancialYear.objects.filter(
                    company=company,
                    is_current=True
                ).first()
                
                if not financial_year:
                    # Fallback: get most recent FY that's not closed
                    financial_year = FinancialYear.objects.filter(
                        company=company,
                        is_closed=False
                    ).order_by('-start_date').first()
                
                if not financial_year:
                    # Last fallback: get any FY
                    financial_year = FinancialYear.objects.filter(
                        company=company
                    ).order_by('-start_date').first()
                
                if not financial_year:
                    return Response(
                        {"error": "Company does not have a financial year configured"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Get Sundry Debtors group
                debtors_group = AccountGroup.objects.filter(
                    company=company,
                    name__icontains='sundry debtor'
                ).first()
                
                if not debtors_group:
                    # Fallback: get any asset group for customers
                    debtors_group = AccountGroup.objects.filter(
                        company=company,
                        nature='DEBIT'
                    ).first()
                
                if not debtors_group:
                    return Response(
                        {"error": "Company does not have account groups configured. Please contact the company administrator."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Generate unique ledger code
                retailer_name = user.get_full_name() or user.email.split('@')[0]
                ledger_code = f"RET-{uuid.uuid4().hex[:8].upper()}"
                
                # Create ledger
                ledger = Ledger.objects.create(
                    company=company,
                    code=ledger_code,
                    name=f"{retailer_name} (Retailer)",
                    group=debtors_group,
                    account_type='CUSTOMER',
                    opening_balance_fy=financial_year,
                    is_bill_wise=True
                )
                
                # Create party
                party = Party.objects.create(
                    company=company,
                    name=retailer_name,
                    party_type='CUSTOMER',
                    ledger=ledger,
                    email=user.email,
                    phone=user.phone or '',
                    is_retailer=True
                )
            
            # Create RetailerUser (portal model - links user to party)
            retailer = RetailerUser.objects.create(
                user=user,
                party=party,
                is_primary_contact=True,
                can_place_orders=True,
                can_view_balance=True,
                can_view_statements=True
            )
        
        # Create approved connection (auto-approve when joining by company code)
        connection = RetailerCompanyAccess.objects.create(
            retailer=retailer,
            company=company,
            status='APPROVED',
            approved_by=None,  # Auto-approved via company code
            approved_at=timezone.now(),
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
        
        # Get retailer profile
        try:
            retailer = RetailerUser.objects.get(user=user)
        except RetailerUser.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        
        # Get connections
        connections = RetailerCompanyAccess.objects.filter(
            retailer=retailer
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
