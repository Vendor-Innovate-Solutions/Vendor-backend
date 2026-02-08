"""
Price List API Views
Handle product price lists for different customer segments.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from apps.orders.models import PriceList, PriceListItem
from apps.products.models import Product


class PriceListListCreateView(APIView):
    """
    List all price lists or create a new one.
    
    GET /api/orders/price-lists/
    POST /api/orders/price-lists/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List price lists"""
        company = request.company
        
        price_lists = PriceList.objects.filter(company=company)
        
        # Filter by type
        pl_type = request.query_params.get('type')
        if pl_type:
            price_lists = price_lists.filter(price_list_type=pl_type.upper())
        
        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            price_lists = price_lists.filter(is_active=is_active.lower() == 'true')
        
        data = []
        for pl in price_lists:
            item_count = pl.items.count()
            data.append({
                "id": str(pl.id),
                "name": pl.name,
                "description": pl.description,
                "price_list_type": pl.price_list_type,
                "is_active": pl.is_active,
                "valid_from": pl.valid_from.isoformat() if pl.valid_from else None,
                "valid_to": pl.valid_to.isoformat() if pl.valid_to else None,
                "item_count": item_count,
                "created_at": pl.created_at.isoformat()
            })
        
        return Response(data, status=status.HTTP_200_OK)
    
    @transaction.atomic
    def post(self, request):
        """Create a new price list"""
        company = request.company
        
        # Validate required fields
        name = request.data.get('name')
        if not name:
            return Response(
                {"error": "name is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create price list
        price_list = PriceList.objects.create(
            company=company,
            name=name,
            description=request.data.get('description', ''),
            price_list_type=request.data.get('price_list_type', 'STANDARD'),
            is_active=request.data.get('is_active', True),
            valid_from=request.data.get('valid_from'),
            valid_to=request.data.get('valid_to')
        )
        
        return Response({
            "message": "Price list created successfully",
            "id": str(price_list.id),
            "name": price_list.name
        }, status=status.HTTP_201_CREATED)


class PriceListDetailView(APIView):
    """
    Get, update, or delete a price list.
    
    GET /api/orders/price-lists/<id>/
    PATCH /api/orders/price-lists/<id>/
    DELETE /api/orders/price-lists/<id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pl_id):
        """Get price list details with items"""
        company = request.company
        
        try:
            pl = PriceList.objects.get(id=pl_id, company=company)
        except PriceList.DoesNotExist:
            return Response(
                {"error": "Price list not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get items
        items = PriceListItem.objects.filter(
            price_list=pl
        ).select_related('product').order_by('product__name', 'min_quantity')
        
        item_data = []
        for item in items:
            item_data.append({
                "id": str(item.id),
                "product_id": str(item.product.id),
                "product_name": item.product.name,
                "product_sku": item.product.sku,
                "unit_price": str(item.unit_price),
                "min_quantity": str(item.min_quantity),
                "discount_percent": str(item.discount_percent),
                "is_active": item.is_active
            })
        
        data = {
            "id": str(pl.id),
            "name": pl.name,
            "description": pl.description,
            "price_list_type": pl.price_list_type,
            "is_active": pl.is_active,
            "valid_from": pl.valid_from.isoformat() if pl.valid_from else None,
            "valid_to": pl.valid_to.isoformat() if pl.valid_to else None,
            "items": item_data,
            "created_at": pl.created_at.isoformat()
        }
        
        return Response(data, status=status.HTTP_200_OK)
    
    def patch(self, request, pl_id):
        """Update price list"""
        company = request.company
        
        try:
            pl = PriceList.objects.get(id=pl_id, company=company)
        except PriceList.DoesNotExist:
            return Response(
                {"error": "Price list not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update fields
        if 'name' in request.data:
            pl.name = request.data['name']
        if 'description' in request.data:
            pl.description = request.data['description']
        if 'is_active' in request.data:
            pl.is_active = request.data['is_active']
        if 'valid_from' in request.data:
            pl.valid_from = request.data['valid_from']
        if 'valid_to' in request.data:
            pl.valid_to = request.data['valid_to']
        
        pl.save()
        
        return Response({
            "message": "Price list updated successfully"
        }, status=status.HTTP_200_OK)
    
    def delete(self, request, pl_id):
        """Delete price list"""
        company = request.company
        
        try:
            pl = PriceList.objects.get(id=pl_id, company=company)
        except PriceList.DoesNotExist:
            return Response(
                {"error": "Price list not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        pl.delete()
        return Response(
            {"message": "Price list deleted successfully"},
            status=status.HTTP_200_OK
        )


class PriceListItemManageView(APIView):
    """
    Add or update items in a price list.
    
    POST /api/orders/price-lists/<pl_id>/items/
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request, pl_id):
        """Add item to price list"""
        company = request.company
        
        try:
            pl = PriceList.objects.get(id=pl_id, company=company)
        except PriceList.DoesNotExist:
            return Response(
                {"error": "Price list not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate product
        product_id = request.data.get('product_id')
        if not product_id:
            return Response(
                {"error": "product_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            product = Product.objects.get(id=product_id, company=company)
        except Product.DoesNotExist:
            return Response(
                {"error": "Product not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create or update price list item
        unit_price = request.data.get('unit_price')
        min_quantity = request.data.get('min_quantity', 1)
        discount_percent = request.data.get('discount_percent', 0)
        
        item, created = PriceListItem.objects.update_or_create(
            price_list=pl,
            product=product,
            min_quantity=min_quantity,
            defaults={
                'unit_price': unit_price,
                'discount_percent': discount_percent,
                'is_active': request.data.get('is_active', True)
            }
        )
        
        return Response({
            "message": f"Item {'added' if created else 'updated'} successfully",
            "id": str(item.id)
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    def delete(self, request, pl_id, item_id):
        """Remove item from price list"""
        company = request.company
        
        try:
            pl = PriceList.objects.get(id=pl_id, company=company)
            item = PriceListItem.objects.get(id=item_id, price_list=pl)
        except (PriceList.DoesNotExist, PriceListItem.DoesNotExist):
            return Response(
                {"error": "Price list item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        item.delete()
        return Response(
            {"message": "Item removed successfully"},
            status=status.HTTP_200_OK
        )
