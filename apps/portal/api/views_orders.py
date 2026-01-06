"""
Portal order placement APIs.
Allows retailers to create, view, and reorder from their portal.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError

from core.permissions.base import RolePermission
from apps.orders.models import SalesOrder, OrderItem
from apps.orders.services.sales_order_service import SalesOrderService
from apps.party.models import RetailerUser


class PortalOrderCreateView(APIView):
    """
    Create sales order from portal.
    
    POST: Create new order
    Requires: RETAILER role or approved retailer user
    """
    permission_classes = [RolePermission.require(['RETAILER', 'ADMIN', 'SALES'])]
    
    def post(self, request):
        """
        Create new sales order.
        
        Body:
            items: List of {item_id, quantity, unit_rate (optional)}
            delivery_date: Expected delivery date
            notes: Order notes
            shipping_address_id: Optional shipping address
        """
        company = request.company
        data = request.data
        
        try:
            # Get retailer's party
            party = None
            if hasattr(request.user, 'retailer_mappings'):
                retailer_mapping = request.user.retailer_mappings.filter(
                    company=company,
                    status='APPROVED'
                ).first()
                
                if not retailer_mapping:
                    return Response(
                        {'error': 'No approved retailer access for this company'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                if not retailer_mapping.party:
                    return Response(
                        {'error': 'Retailer not linked to a party. Contact admin.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                party = retailer_mapping.party
            else:
                return Response(
                    {'error': 'User is not a retailer'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check credit limit
            if party.credit_limit > 0:
                # Calculate outstanding
                outstanding = SalesOrder.objects.filter(
                    company=company,
                    customer=party,
                    status__in=['CONFIRMED', 'PARTIALLY_DELIVERED', 'DELIVERED']
                ).count()  # Simplified - should sum invoice outstanding
                
                # For now, just check if credit limit feature is enabled
                # Full implementation would check actual outstanding amount
            
            # Get default currency and price list
            currency_id = data.get('currency_id')
            if not currency_id and hasattr(company, 'default_currency'):
                currency_id = company.default_currency.id
            
            price_list_id = party.price_list_id if hasattr(party, 'price_list_id') and party.price_list_id else None
            
            # Create order
            order = SalesOrderService.create_order(
                company=company,
                customer_party_id=party.id,
                currency_id=currency_id,
                price_list_id=price_list_id,
                delivery_date=data.get('delivery_date'),
                notes=data.get('notes', ''),
                created_by=request.user
            )
            
            # Add items
            items = data.get('items', [])
            for item_data in items:
                SalesOrderService.add_item(
                    order=order,
                    item_id=item_data['item_id'],
                    quantity=item_data['quantity'],
                    override_rate=item_data.get('unit_rate')
                )
            
            return Response({
                'order_id': str(order.id),
                'order_number': order.order_number,
                'status': order.status,
                'total_amount': float(order.total_amount) if hasattr(order, 'total_amount') else 0,
                'message': 'Order created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to create order: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PortalOrderListView(APIView):
    """
    List retailer's orders.
    
    GET: Returns orders for current retailer
    """
    
    def get(self, request):
        """List orders with optional status filter."""
        company = request.company
        
        # Get retailer's party
        party = None
        if hasattr(request.user, 'retailer_mappings'):
            retailer_mapping = request.user.retailer_mappings.filter(
                company=company,
                status='APPROVED'
            ).first()
            if retailer_mapping and retailer_mapping.party:
                party = retailer_mapping.party
        
        if not party:
            return Response({'orders': []})
        
        # Get orders
        qs = SalesOrder.objects.filter(
            company=company,
            customer=party
        ).order_by('-created_at')
        
        # Filter by status if provided
        filter_status = request.query_params.get('status')
        if filter_status:
            qs = qs.filter(status=filter_status)
        
        # Build response
        orders = [{
            'id': str(order.id),
            'order_number': order.order_number,
            'order_date': order.order_date.isoformat() if hasattr(order, 'order_date') else order.created_at.date().isoformat(),
            'delivery_date': order.delivery_date.isoformat() if hasattr(order, 'delivery_date') and order.delivery_date else None,
            'status': order.status,
            'total_amount': float(order.total_amount) if hasattr(order, 'total_amount') else 0,
            'currency': order.currency.code if hasattr(order, 'currency') else 'INR',
            'item_count': order.items.count() if hasattr(order, 'items') else 0
        } for order in qs]
        
        return Response({'orders': orders})


class PortalOrderStatusView(APIView):
    """
    Get order status and details.
    
    GET: Returns order status and tracking info
    """
    
    def get(self, request, order_id):
        """Get order status."""
        company = request.company
        
        try:
            # Get retailer's party for scoping
            party = None
            if hasattr(request.user, 'retailer_mappings'):
                retailer_mapping = request.user.retailer_mappings.filter(
                    company=company,
                    status='APPROVED'
                ).first()
                if retailer_mapping and retailer_mapping.party:
                    party = retailer_mapping.party
            
            if not party:
                return Response(
                    {'error': 'Retailer not linked to party'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get order with party scoping
            order = SalesOrder.objects.select_related('currency').prefetch_related('items__item').get(
                id=order_id,
                company=company,
                customer=party
            )
            
            # Build item details
            items = [{
                'id': str(item.id),
                'item_name': item.item.name if hasattr(item, 'item') else '',
                'item_code': item.item.item_code if hasattr(item, 'item') and hasattr(item.item, 'item_code') else '',
                'quantity': float(item.quantity),
                'unit_rate': float(item.unit_rate) if hasattr(item, 'unit_rate') else 0,
                'amount': float(item.amount) if hasattr(item, 'amount') else 0
            } for item in order.items.all()] if hasattr(order, 'items') else []
            
            return Response({
                'id': str(order.id),
                'order_number': order.order_number,
                'order_date': order.order_date.isoformat() if hasattr(order, 'order_date') else order.created_at.date().isoformat(),
                'delivery_date': order.delivery_date.isoformat() if hasattr(order, 'delivery_date') and order.delivery_date else None,
                'status': order.status,
                'total_amount': float(order.total_amount) if hasattr(order, 'total_amount') else 0,
                'currency': order.currency.code if hasattr(order, 'currency') else 'INR',
                'items': items,
                'notes': order.notes if hasattr(order, 'notes') else ''
            })
            
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class PortalOrderReorderView(APIView):
    """
    Create new order from existing order (reorder).
    
    POST: Duplicate order with same items
    Requires: RETAILER role
    """
    permission_classes = [RolePermission.require(['RETAILER', 'ADMIN', 'SALES'])]
    
    def post(self, request, order_id):
        """Reorder - create new order from existing."""
        company = request.company
        
        try:
            # Get retailer's party
            party = None
            if hasattr(request.user, 'retailer_mappings'):
                retailer_mapping = request.user.retailer_mappings.filter(
                    company=company,
                    status='APPROVED'
                ).first()
                if retailer_mapping and retailer_mapping.party:
                    party = retailer_mapping.party
            
            if not party:
                return Response(
                    {'error': 'Retailer not linked to party'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Get original order
            old_order = SalesOrder.objects.prefetch_related('items').get(
                id=order_id,
                company=company,
                customer=party
            )
            
            # Create new order
            new_order = SalesOrderService.create_order(
                company=company,
                customer_party_id=party.id,
                currency_id=old_order.currency_id if hasattr(old_order, 'currency_id') else None,
                price_list_id=old_order.price_list_id if hasattr(old_order, 'price_list_id') else None,
                delivery_date=request.data.get('delivery_date'),
                notes=f"Reorder of {old_order.order_number}",
                created_by=request.user
            )
            
            # Copy items
            if hasattr(old_order, 'items'):
                for old_item in old_order.items.all():
                    SalesOrderService.add_item(
                        order=new_order,
                        item_id=old_item.item_id if hasattr(old_item, 'item_id') else old_item.item.id,
                        quantity=old_item.quantity,
                        override_rate=old_item.unit_rate if hasattr(old_item, 'unit_rate') else None
                    )
            
            return Response({
                'new_order_id': str(new_order.id),
                'new_order_number': new_order.order_number,
                'original_order_id': str(old_order.id),
                'original_order_number': old_order.order_number,
                'message': 'Order duplicated successfully'
            }, status=status.HTTP_201_CREATED)
            
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Original order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Reorder failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
