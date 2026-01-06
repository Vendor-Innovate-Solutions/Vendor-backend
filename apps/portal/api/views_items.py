"""
Portal catalog API.
Exposes company product catalog to approved retailers.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q

from core.permissions.base import RolePermission
from apps.inventory.models import StockItem
from apps.pricing.selectors import resolve_price


class PortalItemListView(APIView):
    """
    List available items in company catalog.
    
    GET: Returns active items with pricing
    Requires: Company context (retailers must be approved)
    """
    
    def get(self, request):
        """
        List catalog items.
        
        Query params:
            q: Search query (name, code, description)
            category: Filter by category
            group: Filter by item group
            limit: Max results (default: 100)
        """
        company = request.company
        
        # Get query params
        search_query = request.query_params.get('q', '').strip()
        category = request.query_params.get('category', '').strip()
        group = request.query_params.get('group', '').strip()
        limit = min(int(request.query_params.get('limit', 100)), 500)
        
        # Build queryset
        qs = StockItem.objects.filter(
            company=company,
            is_active=True
        )
        
        if search_query:
            qs = qs.filter(
                Q(name__icontains=search_query) |
                Q(item_code__icontains=search_query) |
                Q(description__icontains=search_query)
            )
        
        if category:
            qs = qs.filter(category__icontains=category)
        
        if group and hasattr(StockItem, 'item_group'):
            qs = qs.filter(item_group__name__icontains=group)
        
        qs = qs[:limit]
        
        # Determine party for pricing
        party = None
        if hasattr(request.user, 'retailer_mappings'):
            retailer_mapping = request.user.retailer_mappings.filter(
                company=company,
                status='APPROVED'
            ).first()
            if retailer_mapping and retailer_mapping.party:
                party = retailer_mapping.party
        
        # Build response with pricing
        items = []
        for item in qs:
            try:
                price = resolve_price(company, item, party)
            except:
                price = None
            
            items.append({
                'id': str(item.id),
                'name': item.name,
                'item_code': item.item_code if hasattr(item, 'item_code') else None,
                'description': item.description if hasattr(item, 'description') else '',
                'uom': item.uom if hasattr(item, 'uom') else 'Nos',
                'price': float(price) if price else None,
                'in_stock': item.available_quantity > 0 if hasattr(item, 'available_quantity') else True,
                'image_url': item.image_url if hasattr(item, 'image_url') else None
            })
        
        return Response({
            'items': items,
            'count': len(items),
            'party_id': str(party.id) if party else None
        })


class PortalItemDetailView(APIView):
    """
    Get detailed information about a catalog item.
    
    GET: Returns item details with pricing
    """
    
    def get(self, request, item_id):
        """Get item details."""
        company = request.company
        
        try:
            item = StockItem.objects.get(id=item_id, company=company, is_active=True)
            
            # Get party for pricing
            party = None
            if hasattr(request.user, 'retailer_mappings'):
                retailer_mapping = request.user.retailer_mappings.filter(
                    company=company,
                    status='APPROVED'
                ).first()
                if retailer_mapping and retailer_mapping.party:
                    party = retailer_mapping.party
            
            # Resolve price
            try:
                price = resolve_price(company, item, party)
            except:
                price = None
            
            return Response({
                'id': str(item.id),
                'name': item.name,
                'item_code': item.item_code if hasattr(item, 'item_code') else None,
                'description': item.description if hasattr(item, 'description') else '',
                'uom': item.uom if hasattr(item, 'uom') else 'Nos',
                'price': float(price) if price else None,
                'specifications': item.specifications if hasattr(item, 'specifications') else {},
                'images': item.images if hasattr(item, 'images') else [],
                'available_quantity': float(item.available_quantity) if hasattr(item, 'available_quantity') else None,
                'lead_time_days': item.lead_time_days if hasattr(item, 'lead_time_days') else None
            })
            
        except StockItem.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
