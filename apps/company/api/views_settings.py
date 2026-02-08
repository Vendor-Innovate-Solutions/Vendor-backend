"""
Company Settings API Views
Handles company information, module configuration, financial year, GST, and branding settings.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
from apps.company.models import Company, CompanyFeature, FinancialYear
from apps.company.api.serializers import CompanySerializer


class CompanySettingsView(APIView):
    """
    Get or update company settings (info, branding, GST).
    
    GET /api/company/settings/
    PATCH /api/company/settings/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """Get current company settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get company features
        try:
            features = CompanyFeature.objects.get(company=company)
        except CompanyFeature.DoesNotExist:
            features = CompanyFeature.objects.create(
                company=company,
                inventory_enabled=True,
                accounting_enabled=True,
                payroll_enabled=False,
                gst_enabled=False,
                locked=False
            )
        
        # Get current financial year
        try:
            current_fy = FinancialYear.objects.get(company=company, is_current=True)
            fy_data = {
                "id": str(current_fy.id),
                "name": current_fy.name,
                "start_date": current_fy.start_date.isoformat(),
                "end_date": current_fy.end_date.isoformat(),
                "is_current": current_fy.is_current,
                "is_closed": current_fy.is_closed
            }
        except FinancialYear.DoesNotExist:
            fy_data = None
        
        # Serialize company data
        serializer = CompanySerializer(company)
        company_data = serializer.data
        
        # Add features and FY to response
        company_data['features'] = {
            "inventory_enabled": features.inventory_enabled,
            "accounting_enabled": features.accounting_enabled,
            "payroll_enabled": features.payroll_enabled,
            "gst_enabled": features.gst_enabled,
            "locked": features.locked
        }
        company_data['current_financial_year'] = fy_data
        
        return Response(company_data, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def patch(self, request):
        """Update company settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update company fields
        updatable_fields = [
            'name', 'legal_name', 'company_type', 'phone', 'email', 'website',
            'address_line1', 'address_line2', 'city', 'state', 'country', 'pincode',
            'gstin', 'pan', 'invoice_footer', 'invoice_terms', 'timezone', 'language'
        ]
        
        for field in updatable_fields:
            if field in request.data:
                setattr(company, field, request.data[field])
        
        # Handle logo upload
        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']
        
        # Handle base_currency
        if 'base_currency' in request.data:
            company.base_currency_id = request.data['base_currency']
        
        company.save()
        
        # Update features if provided
        if 'features' in request.data:
            features_data = request.data['features']
            features, created = CompanyFeature.objects.get_or_create(company=company)
            
            feature_fields = ['inventory_enabled', 'accounting_enabled', 'payroll_enabled', 'gst_enabled', 'locked']
            for field in feature_fields:
                if field in features_data:
                    setattr(features, field, features_data[field])
            
            features.save()
        
        # Return updated data
        serializer = CompanySerializer(company)
        return Response(
            {
                "message": "Company settings updated successfully",
                "company": serializer.data
            },
            status=status.HTTP_200_OK
        )


class CompanyModulesView(APIView):
    """
    Get or update company module settings.
    
    GET /api/company/modules/
    PATCH /api/company/modules/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current module settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        features, created = CompanyFeature.objects.get_or_create(
            company=company,
            defaults={
                'inventory_enabled': True,
                'accounting_enabled': True,
                'payroll_enabled': False,
                'gst_enabled': False,
                'locked': False
            }
        )
        
        return Response({
            "inventory_enabled": features.inventory_enabled,
            "accounting_enabled": features.accounting_enabled,
            "payroll_enabled": features.payroll_enabled,
            "gst_enabled": features.gst_enabled,
            "locked": features.locked
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Update module settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        features, created = CompanyFeature.objects.get_or_create(company=company)
        
        # Update module settings
        if 'inventory_enabled' in request.data:
            features.inventory_enabled = request.data['inventory_enabled']
        if 'accounting_enabled' in request.data:
            features.accounting_enabled = request.data['accounting_enabled']
        if 'payroll_enabled' in request.data:
            features.payroll_enabled = request.data['payroll_enabled']
        if 'gst_enabled' in request.data:
            features.gst_enabled = request.data['gst_enabled']
        if 'locked' in request.data:
            features.locked = request.data['locked']
        
        features.save()
        
        return Response({
            "message": "Module settings updated successfully",
            "modules": {
                "inventory_enabled": features.inventory_enabled,
                "accounting_enabled": features.accounting_enabled,
                "payroll_enabled": features.payroll_enabled,
                "gst_enabled": features.gst_enabled,
                "locked": features.locked
            }
        }, status=status.HTTP_200_OK)


class CompanyBrandingView(APIView):
    """
    Get or update company branding (logo, invoice footer).
    
    GET /api/company/branding/
    PATCH /api/company/branding/
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    
    def get(self, request):
        """Get current branding settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            "logo": company.logo.url if company.logo else None,
            "invoice_footer": company.invoice_footer,
            "invoice_terms": company.invoice_terms
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Update branding settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update branding fields
        if 'logo' in request.FILES:
            company.logo = request.FILES['logo']
        
        if 'invoice_footer' in request.data:
            company.invoice_footer = request.data['invoice_footer']
        
        if 'invoice_terms' in request.data:
            company.invoice_terms = request.data['invoice_terms']
        
        company.save()
        
        return Response({
            "message": "Branding updated successfully",
            "logo": company.logo.url if company.logo else None,
            "invoice_footer": company.invoice_footer,
            "invoice_terms": company.invoice_terms
        }, status=status.HTTP_200_OK)


class CompanyGSTView(APIView):
    """
    Get or update company GST settings.
    
    GET /api/company/gst/
    PATCH /api/company/gst/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current GST settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get GST enabled status from features
        try:
            features = CompanyFeature.objects.get(company=company)
            gst_enabled = features.gst_enabled
        except CompanyFeature.DoesNotExist:
            gst_enabled = False
        
        return Response({
            "gstin": company.gstin,
            "pan": company.pan,
            "gst_enabled": gst_enabled,
            "state": company.state,
            "country": company.country
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Update GST settings"""
        user = request.user
        company = user.active_company
        
        if not company:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update GST fields
        if 'gstin' in request.data:
            company.gstin = request.data['gstin']
        
        if 'pan' in request.data:
            company.pan = request.data['pan']
        
        if 'state' in request.data:
            company.state = request.data['state']
        
        if 'country' in request.data:
            company.country = request.data['country']
        
        company.save()
        
        # Update GST enabled status in features
        if 'gst_enabled' in request.data:
            features, created = CompanyFeature.objects.get_or_create(company=company)
            features.gst_enabled = request.data['gst_enabled']
            features.save()
        
        return Response({
            "message": "GST settings updated successfully",
            "gstin": company.gstin,
            "pan": company.pan,
            "gst_enabled": request.data.get('gst_enabled', False),
            "state": company.state,
            "country": company.country
        }, status=status.HTTP_200_OK)
