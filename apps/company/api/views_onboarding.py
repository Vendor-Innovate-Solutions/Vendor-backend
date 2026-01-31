"""
Company onboarding APIs for multi-phase company creation.
Handles MANUFACTURER company creation with default settings and financial year.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.company.models import Company, CompanyUser, CompanyFeature, FinancialYear, Currency
from apps.company.api.serializers import CompanySerializer
from datetime import datetime, timedelta

User = get_user_model()


class CompanyCreationSerializer:
    """Serializer for company creation during onboarding"""
    pass


class ManufacturerCompanyCreationView(APIView):
    """
    Create company for MANUFACTURER users.
    Only allowed if user.selected_role == 'MANUFACTURER' and user has no company yet.
    
    POST /onboarding/create-company
    
    Request:
    {
        "name": "ABC Manufacturing",
        "code": "ABC001",
        "legal_name": "ABC Manufacturing Private Limited",
        "company_type": "PRIVATE_LIMITED",
        "timezone": "Asia/Kolkata",
        "language": "en",
        "base_currency": "currency-uuid"
    }
    
    Response (201 Created):
    {
        "message": "Company created successfully",
        "company": {
            "id": "company-uuid",
            "code": "ABC001",
            "name": "ABC Manufacturing",
            "legal_name": "ABC Manufacturing Private Limited",
            "company_type": "PRIVATE_LIMITED",
            "timezone": "Asia/Kolkata",
            "language": "en",
            "base_currency": "currency-uuid",
            "is_active": true
        },
        "company_user": {
            "company": "company-uuid",
            "user": "user-id",
            "role": "OWNER",
            "is_default": true
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        user = request.user
        
        # Authorization check
        if user.selected_role != 'MANUFACTURER':
            return Response(
                {
                    "error": "Only MANUFACTURER users can create companies",
                    "current_role": user.selected_role
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user already has a company
        if user.company_memberships.filter(is_active=True).exists():
            return Response(
                {
                    "error": "User already has an active company. Create another company via admin."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate required fields
        required_fields = ['name', 'code', 'legal_name', 'base_currency']
        for field in required_fields:
            if not request.data.get(field):
                return Response(
                    {"error": f"Field '{field}' is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        try:
            # Validate currency exists
            currency_id = request.data.get('base_currency')
            try:
                currency = Currency.objects.get(id=currency_id)
            except Currency.DoesNotExist:
                return Response(
                    {"error": f"Currency with ID {currency_id} not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate company code is unique
            if Company.objects.filter(code=request.data.get('code')).exists():
                return Response(
                    {"error": f"Company code '{request.data.get('code')}' already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create company with atomic transaction
            company = Company.objects.create(
                code=request.data.get('code'),
                name=request.data.get('name'),
                legal_name=request.data.get('legal_name'),
                company_type=request.data.get('company_type', 'PRIVATE_LIMITED'),
                timezone=request.data.get('timezone', 'UTC'),
                language=request.data.get('language', 'en'),
                base_currency=currency,
                is_active=True
            )
            
            # Create CompanyUser with OWNER role
            company_user = CompanyUser.objects.create(
                company=company,
                user=user,
                role='OWNER',  # Manufacturer creating company is OWNER
                is_default=True,
                is_active=True
            )
            
            # Create default CompanyFeature
            company_feature = CompanyFeature.objects.create(
                company=company,
                inventory_enabled=True,
                accounting_enabled=True,
                payroll_enabled=False,
                gst_enabled=False,
                locked=False
            )
            
            # Create default Financial Year (current year)
            current_year = datetime.now().year
            fy_start = datetime(current_year, 4, 1).date()  # April 1 (India FY standard)
            fy_end = datetime(current_year + 1, 3, 31).date()  # March 31
            
            financial_year = FinancialYear.objects.create(
                company=company,
                name=f"FY {current_year}-{current_year + 1}",
                start_date=fy_start,
                end_date=fy_end,
                is_current=True,
                is_closed=False
            )
            
            # Set active company for user
            user.active_company = company
            user.save()
            
            return Response(
                {
                    "message": "Company created successfully",
                    "company": CompanySerializer(company).data,
                    "company_user": {
                        "company": str(company.id),
                        "user": str(user.id),
                        "role": company_user.role,
                        "is_default": company_user.is_default
                    },
                    "financial_year": {
                        "id": str(financial_year.id),
                        "name": financial_year.name,
                        "start_date": financial_year.start_date,
                        "end_date": financial_year.end_date,
                        "is_current": financial_year.is_current
                    }
                },
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CompanyInviteView(APIView):
    """
    Send invite to external user (Retailer, Supplier, etc.)
    
    POST /companies/{company_id}/invite
    
    Request:
    {
        "email": "retailer@example.com",
        "role": "SALES_REP",
        "message": "Optional invite message"
    }
    
    Response:
    {
        "message": "Invite sent successfully",
        "invite_token": "token123...",
        "invite_url": "https://frontend.com/invite/token123"
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, company_id):
        # TODO: Implement invite flow
        return Response({"message": "Invite API coming soon"}, status=status.HTTP_501_NOT_IMPLEMENTED)


class InviteAcceptView(APIView):
    """
    Accept company invite (external user onboarding)
    
    POST /invites/{token}/accept
    
    Response:
    {
        "message": "Invite accepted successfully",
        "company_user": {...}
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, token):
        # TODO: Implement invite acceptance
        return Response({"message": "Accept invite API coming soon"}, status=status.HTTP_501_NOT_IMPLEMENTED)


class ExternalUserProfileView(APIView):
    """
    Create independent external user profile (no company required)
    Used for retailers, suppliers creating standalone profiles
    
    POST /partner/profile
    
    Request:
    {
        "business_name": "XYZ Retail",
        "business_type": "RETAILER",
        "gstin": "27AABCT1234A1Z5",
        "contact_person": "John Doe"
    }
    
    Response:
    {
        "message": "Profile created successfully",
        "profile": {...}
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # TODO: Implement external profile creation
        return Response({"message": "External profile API coming soon"}, status=status.HTTP_501_NOT_IMPLEMENTED)
