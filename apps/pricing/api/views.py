"""
Pricing API views.
Exposes item pricing to authenticated users including retailers.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.inventory.models import StockItem
from apps.pricing.selectors import resolve_price, get_item_prices_bulk


class ItemPricingView(APIView):
    """
    Get pricing for a specific item.
    
    GET: Returns price based on user's party and company price lists
    """
    
    def get(self, request, item_id):
        """
        Get price for an item.
        
        Price resolution:
        - If user has party: use party price list
        - Else: use company default price list
        - Fallback: item default price
        """
        company = request.company
        
        try:
            # Get item
            item = StockItem.objects.get(id=item_id, company=company)
            
            # Determine party (for retailer users)
            party = None
            if hasattr(request.user, 'party'):
                party = request.user.party
            elif hasattr(request.user, 'retailer_mappings'):
                # Get party from retailer mapping
                retailer_mapping = request.user.retailer_mappings.filter(
                    company=company,
                    status='APPROVED'
                ).first()
                if retailer_mapping and retailer_mapping.party:
                    party = retailer_mapping.party
            
            # Resolve price
            price = resolve_price(company, item, party)
            
            return Response({
                'item_id': str(item.id),
                'item_name': item.name,
                'item_code': item.item_code if hasattr(item, 'item_code') else None,
                'price': float(price),
                'currency': company.default_currency.code if hasattr(company, 'default_currency') else 'INR',
                'party_id': str(party.id) if party else None,
                'party_name': party.name if party else None
            })
            
        except StockItem.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class BulkItemPricingView(APIView):
    """
    Get pricing for multiple items at once.
    
    POST: Returns prices for all requested items
    """
    
    def post(self, request):
        """
        Get prices for multiple items.
        
        Body:
            item_ids: List of item IDs
        """
        company = request.company
        item_ids = request.data.get('item_ids', [])
        
        if not item_ids:
            return Response(
                {'error': 'item_ids required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine party
        party = None
        if hasattr(request.user, 'party'):
            party = request.user.party
        elif hasattr(request.user, 'retailer_mappings'):
            retailer_mapping = request.user.retailer_mappings.filter(
                company=company,
                status='APPROVED'
            ).first()
            if retailer_mapping and retailer_mapping.party:
                party = retailer_mapping.party
        
        # Get bulk prices
        prices = get_item_prices_bulk(company, item_ids, party)
        
        return Response({
            'prices': prices,
            'party_id': str(party.id) if party else None,
            'currency': company.default_currency.code if hasattr(company, 'default_currency') else 'INR'
        })
