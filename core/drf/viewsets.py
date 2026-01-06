"""
DRF utilities for company-scoped views
"""
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied


class CompanyScopedViewSet(ModelViewSet):
    """
    Automatically filters querysets by request.company.
    
    Ensures multi-tenant data isolation at the ViewSet level.
    No queries can bypass company filtering.
    
    Usage:
        class InvoiceViewSet(CompanyScopedViewSet):
            queryset = Invoice.objects.all()
            serializer_class = InvoiceSerializer
    
    The queryset will automatically be filtered to only include
    records belonging to request.company.
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter queryset by company from request.
        
        Returns:
            QuerySet filtered by request.company, or empty queryset
            if no company context is available.
        """
        qs = super().get_queryset()
        company = getattr(self.request, "company", None)
        
        if company:
            # Only return data for the user's active company
            return qs.filter(company=company)
        
        # No company = no data (security: prevent data leakage)
        return qs.none()
    
    def perform_create(self, serializer):
        """
        Automatically inject company when creating records.
        
        Args:
            serializer: DRF serializer instance
        
        Raises:
            PermissionDenied: If no company context available
        """
        company = getattr(self.request, "company", None)
        
        if not company:
            raise PermissionDenied(
                "No company context available. Cannot create records."
            )
        
        serializer.save(company=company)
    
    def perform_update(self, serializer):
        """
        Ensure updates maintain company isolation.
        
        Args:
            serializer: DRF serializer instance
        """
        # Company is immutable - don't allow changes
        serializer.save()


class CompanyScopedReadOnlyViewSet(CompanyScopedViewSet):
    """
    Read-only version of CompanyScopedViewSet.
    
    Use for reference data that shouldn't be modified via API.
    """
    http_method_names = ['get', 'head', 'options']
