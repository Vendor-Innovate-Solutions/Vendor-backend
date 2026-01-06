"""
Purchase Order API views.
RESTful endpoints for purchase order management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count

from core.drf.permissions import RolePermission
from apps.orders.services.purchase_order_service import PurchaseOrderService
from apps.orders.api.serializers import (
    PurchaseOrderSerializer, PurchaseOrderListSerializer,
    CreatePurchaseOrderSerializer, AddOrderItemSerializer,
    UpdateOrderItemSerializer, CancelOrderSerializer,
    OrderItemSerializer
)
from apps.orders.models import PurchaseOrder, OrderItem


class PurchaseOrderListCreateView(APIView):
    """
    List all purchase orders or create a new one.
    
    GET: List purchase orders
    POST: Create new purchase order
    """
    
    def get(self, request):
        """List purchase orders with optional filters."""
        company = request.company
        
        # Get queryset
        qs = PurchaseOrder.objects.filter(company=company).select_related(
            'supplier', 'currency'
        ).annotate(
            item_count=Count('orderitem')
        )
        
        # Filter by status
        order_status = request.query_params.get('status')
        if order_status:
            qs = qs.filter(status=order_status)
        
        # Filter by supplier
        supplier_id = request.query_params.get('supplier')
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        
        # Filter by date range
        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(order_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(order_date__lte=end_date)
        
        # Order by date
        qs = qs.order_by('-order_date', '-created_at')
        
        serializer = PurchaseOrderListSerializer(qs, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new purchase order."""
        company = request.company
        serializer = CreatePurchaseOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = PurchaseOrderService.create_order(
                company=company,
                supplier_party_id=serializer.validated_data['supplier_id'],
                currency_id=serializer.validated_data['currency_id'],
                price_list_id=serializer.validated_data.get('price_list_id'),
                order_date=serializer.validated_data.get('order_date'),
                due_date=serializer.validated_data.get('due_date'),
                shipping_address=serializer.validated_data.get('shipping_address', ''),
                billing_address=serializer.validated_data.get('billing_address', ''),
                payment_terms=serializer.validated_data.get('payment_terms', ''),
                notes=serializer.validated_data.get('notes', ''),
                created_by=request.user
            )
            
            response_serializer = PurchaseOrderSerializer(order)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderDetailView(APIView):
    """
    Get, update, or delete a purchase order.
    
    GET: Get order details
    PATCH: Update order
    DELETE: Delete order (if draft)
    """
    
    def get(self, request, order_id):
        """Get purchase order details."""
        company = request.company
        
        try:
            order = PurchaseOrder.objects.select_related(
                'supplier', 'currency', 'price_list'
            ).prefetch_related('orderitem_set__item').get(
                company=company,
                id=order_id
            )
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = PurchaseOrderSerializer(order)
        return Response(serializer.data)
    
    def patch(self, request, order_id):
        """Update purchase order fields."""
        company = request.company
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if order.status not in ['DRAFT', 'PENDING']:
            return Response(
                {'error': f'Cannot update {order.status} order'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update allowed fields
        allowed_fields = ['due_date', 'shipping_address', 'billing_address', 'payment_terms', 'notes']
        for field in allowed_fields:
            if field in request.data:
                setattr(order, field, request.data[field])
        
        order.save()
        
        serializer = PurchaseOrderSerializer(order)
        return Response(serializer.data)
    
    def delete(self, request, order_id):
        """Delete a draft order."""
        company = request.company
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if order.status != 'DRAFT':
            return Response(
                {'error': 'Can only delete draft orders'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PurchaseOrderAddItemView(APIView):
    """Add an item to a purchase order."""
    
    def post(self, request, order_id):
        """Add item to order."""
        company = request.company
        serializer = AddOrderItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            line = PurchaseOrderService.add_item(
                order,
                serializer.validated_data['item_id'],
                serializer.validated_data['quantity'],
                override_rate=serializer.validated_data.get('override_rate'),
                uom_id=serializer.validated_data.get('uom_id'),
                discount_percent=serializer.validated_data.get('discount_percent'),
                notes=serializer.validated_data.get('notes', '')
            )
            
            response_serializer = OrderItemSerializer(line)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderUpdateItemView(APIView):
    """Update an order item."""
    
    def patch(self, request, order_id, item_id):
        """Update order item."""
        company = request.company
        serializer = UpdateOrderItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
            order_item = OrderItem.objects.get(
                order_content_type=order.get_content_type(),
                order_object_id=order.id,
                id=item_id
            )
        except (PurchaseOrder.DoesNotExist, OrderItem.DoesNotExist):
            return Response(
                {'error': 'Order or item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            updated_item = PurchaseOrderService.update_item(
                order_item,
                quantity=serializer.validated_data.get('quantity'),
                unit_rate=serializer.validated_data.get('unit_rate'),
                discount_percent=serializer.validated_data.get('discount_percent'),
                notes=serializer.validated_data.get('notes')
            )
            
            response_serializer = OrderItemSerializer(updated_item)
            return Response(response_serializer.data)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderRemoveItemView(APIView):
    """Remove an item from a purchase order."""
    
    def delete(self, request, order_id, item_id):
        """Remove item from order."""
        company = request.company
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
            order_item = OrderItem.objects.get(
                order_content_type=order.get_content_type(),
                order_object_id=order.id,
                id=item_id
            )
        except (PurchaseOrder.DoesNotExist, OrderItem.DoesNotExist):
            return Response(
                {'error': 'Order or item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            PurchaseOrderService.remove_item(order_item)
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderConfirmView(APIView):
    """Confirm a purchase order."""
    permission_classes = [RolePermission.require(['ADMIN', 'PURCHASE_MANAGER'])]
    
    def post(self, request, order_id):
        """Confirm order."""
        company = request.company
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            order = PurchaseOrderService.confirm_order(order)
            serializer = PurchaseOrderSerializer(order)
            
            return Response({
                'order': serializer.data,
                'message': 'Purchase order confirmed'
            })
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PurchaseOrderCancelView(APIView):
    """Cancel a purchase order."""
    permission_classes = [RolePermission.require(['ADMIN', 'PURCHASE_MANAGER'])]
    
    def post(self, request, order_id):
        """Cancel order."""
        company = request.company
        serializer = CancelOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = PurchaseOrder.objects.get(company=company, id=order_id)
        except PurchaseOrder.DoesNotExist:
            return Response(
                {'error': 'Purchase order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            order = PurchaseOrderService.cancel_order(
                order,
                reason=serializer.validated_data.get('reason', '')
            )
            
            response_serializer = PurchaseOrderSerializer(order)
            return Response({
                'order': response_serializer.data,
                'message': 'Purchase order cancelled'
            })
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
