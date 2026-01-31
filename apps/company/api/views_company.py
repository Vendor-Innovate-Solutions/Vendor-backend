"""
Company Management API Views
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from apps.company.models import Company, Currency, CompanyUser, CompanyFeature, FinancialYear
from apps.company.api.serializers import (
    CompanySerializer,
    CompanyCreateSerializer,
    CurrencySerializer
)
from datetime import datetime


class CompanyListCreateView(APIView):
    """
    List all companies or create a new company.
    
    GET /api/company/
    POST /api/company/create/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all active companies"""
        companies = Company.objects.filter(is_deleted=False).select_related('base_currency')
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def post(self, request):
        """Create a new company and link it to the user"""
        serializer = CompanyCreateSerializer(data=request.data)
        if serializer.is_valid():
            company = serializer.save()
            user = request.user
            
            # Create CompanyUser with OWNER role
            company_user = CompanyUser.objects.create(
                company=company,
                user=user,
                role='OWNER',
                is_default=True,
                is_active=True
            )
            
            # Create default CompanyFeature
            CompanyFeature.objects.create(
                company=company,
                inventory_enabled=True,
                accounting_enabled=True,
                payroll_enabled=False,
                gst_enabled=False,
                locked=False
            )
            
            # Create default Financial Year (current year - April to March for India)
            current_year = datetime.now().year
            fy_start = datetime(current_year, 4, 1).date()
            fy_end = datetime(current_year + 1, 3, 31).date()
            
            financial_year = FinancialYear.objects.create(
                company=company,
                name=f"FY {current_year}-{current_year + 1}",
                start_date=fy_start,
                end_date=fy_end,
                is_current=True,
                is_closed=False
            )
            
            # Set user's active company
            user.active_company = company
            user.save()
            
            response_serializer = CompanySerializer(company)
            return Response(
                {
                    "message": "Company created successfully",
                    "company": response_serializer.data,
                    "company_user": {
                        "company": str(company.id),
                        "user": str(user.id),
                        "role": company_user.role,
                        "is_default": company_user.is_default
                    },
                    "financial_year": {
                        "id": str(financial_year.id),
                        "name": financial_year.name,
                        "start_date": str(financial_year.start_date),
                        "end_date": str(financial_year.end_date),
                        "is_current": financial_year.is_current
                    }
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyDetailView(APIView):
    """
    Retrieve, update or delete a company.
    
    GET /api/company/<company_id>/
    PUT /api/company/<company_id>/
    PATCH /api/company/<company_id>/
    DELETE /api/company/<company_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, company_id):
        """Get company by ID"""
        try:
            return Company.objects.select_related('base_currency').get(
                id=company_id,
                is_deleted=False
            )
        except Company.DoesNotExist:
            return None
    
    def get(self, request, company_id):
        """Retrieve company details"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, company_id):
        """Update company (full update)"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CompanySerializer(company, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, company_id):
        """Update company (partial update)"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, company_id):
        """Soft delete company"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        company.is_deleted = True
        company.is_active = False
        company.save()
        return Response(
            {"message": "Company deleted successfully"},
            status=status.HTTP_200_OK
        )


class CurrencyListView(APIView):
    """
    List all available currencies.
    
    GET /api/company/currencies/
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """List all currencies"""
        currencies = Currency.objects.all().order_by('code')
        serializer = CurrencySerializer(currencies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
