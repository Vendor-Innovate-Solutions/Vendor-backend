"""
Company Setup API Views for Multi-Phase Onboarding
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from apps.company.models import Company, Address, CompanyFeature
from apps.company.api.serializers_extended import (
    CompanyBusinessSettingsSerializer,
    AddressCreateSerializer,
    AddressDetailSerializer,
    CompanyFeatureSerializer,
    CompanySetupStatusSerializer,
    CompanyDetailedSerializer
)


class CompanyBusinessSettingsView(APIView):
    """
    PHASE 2: Update business settings and module toggles
    
    PUT /api/company/<company_id>/business-settings/
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, company_id):
        """Get company by ID"""
        try:
            return Company.objects.get(id=company_id, is_deleted=False)
        except Company.DoesNotExist:
            return None
    
    def get(self, request, company_id):
        """Get current business settings"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get features if they exist
        try:
            features = CompanyFeature.objects.get(company=company)
            features_data = CompanyFeatureSerializer(features).data
        except CompanyFeature.DoesNotExist:
            features_data = None
        
        data = CompanyDetailedSerializer(company).data
        return Response(data, status=status.HTTP_200_OK)
    
    def put(self, request, company_id):
        """Update business settings"""
        company = self.get_object(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CompanyBusinessSettingsSerializer(data=request.data)
        if serializer.is_valid():
            company, features = serializer.update_company_settings(company)
            
            return Response(
                {
                    "message": "Business settings updated successfully",
                    "company": CompanyDetailedSerializer(company).data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyAddressListCreateView(APIView):
    """
    PHASE 3: Manage company addresses
    
    GET /api/company/<company_id>/addresses/
    POST /api/company/<company_id>/addresses/
    """
    permission_classes = [IsAuthenticated]
    
    def get_company(self, company_id):
        """Get company by ID"""
        try:
            return Company.objects.get(id=company_id, is_deleted=False)
        except Company.DoesNotExist:
            return None
    
    def get(self, request, company_id):
        """List all addresses for company"""
        company = self.get_company(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        addresses = Address.objects.filter(company=company).order_by('-created_at')
        serializer = AddressDetailSerializer(addresses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, company_id):
        """Create new address for company"""
        company = self.get_company(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AddressCreateSerializer(data=request.data)
        if serializer.is_valid():
            address = serializer.save(company=company)
            response_serializer = AddressDetailSerializer(address)
            return Response(
                {
                    "message": "Address added successfully",
                    "address": response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyAddressDetailView(APIView):
    """
    Manage individual address
    
    GET /api/company/<company_id>/addresses/<address_id>/
    PUT /api/company/<company_id>/addresses/<address_id>/
    PATCH /api/company/<company_id>/addresses/<address_id>/
    DELETE /api/company/<company_id>/addresses/<address_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, company_id, address_id):
        """Get address by company and address ID"""
        try:
            return Address.objects.get(
                id=address_id,
                company_id=company_id,
                company__is_deleted=False
            )
        except Address.DoesNotExist:
            return None
    
    def get(self, request, company_id, address_id):
        """Get address details"""
        address = self.get_object(company_id, address_id)
        if not address:
            return Response(
                {"error": "Address not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AddressDetailSerializer(address)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, company_id, address_id):
        """Update address (full update)"""
        address = self.get_object(company_id, address_id)
        if not address:
            return Response(
                {"error": "Address not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AddressCreateSerializer(data=request.data)
        if serializer.is_valid():
            for field, value in serializer.validated_data.items():
                setattr(address, field, value)
            address.save()
            
            response_serializer = AddressDetailSerializer(address)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, company_id, address_id):
        """Update address (partial update)"""
        address = self.get_object(company_id, address_id)
        if not address:
            return Response(
                {"error": "Address not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AddressCreateSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            for field, value in serializer.validated_data.items():
                setattr(address, field, value)
            address.save()
            
            response_serializer = AddressDetailSerializer(address)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, company_id, address_id):
        """Delete address"""
        address = self.get_object(company_id, address_id)
        if not address:
            return Response(
                {"error": "Address not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        address.delete()
        return Response(
            {"message": "Address deleted successfully"},
            status=status.HTTP_200_OK
        )


class CompanySetupStatusView(APIView):
    """
    Get company setup completion status
    
    GET /api/company/<company_id>/setup-status/
    """
    permission_classes = [AllowAny]
    
    def get(self, request, company_id):
        """Get setup status"""
        try:
            company = Company.objects.get(id=company_id, is_deleted=False)
        except Company.DoesNotExist:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        status_data = CompanySetupStatusSerializer.get_setup_status(company)
        return Response(status_data, status=status.HTTP_200_OK)


class CompanyFeatureView(APIView):
    """
    Get or update company features/modules
    
    GET /api/company/<company_id>/features/
    PUT /api/company/<company_id>/features/
    """
    permission_classes = [IsAuthenticated]
    
    def get_company(self, company_id):
        """Get company by ID"""
        try:
            return Company.objects.get(id=company_id, is_deleted=False)
        except Company.DoesNotExist:
            return None
    
    def get(self, request, company_id):
        """Get company features"""
        company = self.get_company(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        features, created = CompanyFeature.objects.get_or_create(company=company)
        serializer = CompanyFeatureSerializer(features)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def put(self, request, company_id):
        """Update company features"""
        company = self.get_company(company_id)
        if not company:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        features, created = CompanyFeature.objects.get_or_create(company=company)
        serializer = CompanyFeatureSerializer(features, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Features updated successfully",
                    "features": serializer.data
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
