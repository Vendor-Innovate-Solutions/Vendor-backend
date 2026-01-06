"""
Company API views.
Handles company-related endpoints including discovery.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from apps.company.models import Company


class CompanyDiscoveryView(APIView):
    """
    Public endpoint for discovering companies.
    
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
                Q(company_code__icontains=query)
            )
        
        if city:
            qs = qs.filter(city__icontains=city)
        
        if category:
            qs = qs.filter(business_category__icontains=category) if hasattr(Company, 'business_category') else qs
        
        # Limit results
        qs = qs[:50]
        
        data = [{
            'id': str(c.id),
            'name': c.name,
            'company_code': c.company_code if hasattr(c, 'company_code') else None,
            'city': c.city if hasattr(c, 'city') else None,
            'state': c.state if hasattr(c, 'state') else None,
            'gstin': c.gstin if hasattr(c, 'gstin') else None,
            'email': c.email if hasattr(c, 'email') else None,
            'phone': c.phone if hasattr(c, 'phone') else None,
        } for c in qs]
        
        return Response(data)
