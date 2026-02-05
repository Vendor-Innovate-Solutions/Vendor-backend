"""
Sales Order API views.
RESTful endpoints for sales order management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count

from core.drf.permissions import RolePermission
from apps.orders.services.sales_order_service import SalesOrderService
from apps.orders.api.serializers import (
    SalesOrderSerializer, SalesOrderListSerializer,
    CreateSalesOrderSerializer, AddOrderItemSerializer,
    UpdateOrderItemSerializer, CancelOrderSerializer,
    OrderItemSerializer
)
from apps.orders.models import SalesOrder, OrderItem


class SalesOrderListCreateView(APIView):
    """
    List all sales orders or create a new one.
    
    GET: List sales orders
    POST: Create new sales order
    """
    
    def get(self, request):
        """List sales orders with optional filters."""
        company = request.company
        
        # Get queryset
        qs = SalesOrder.objects.filter(company=company).select_related(
            'customer', 'currency'
        ).annotate(
            item_count=Count('items')
        )
        
        # Filter by status
        order_status = request.query_params.get('status')
        if order_status:
            qs = qs.filter(status=order_status)
        
        # Filter by customer
        customer_id = request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        
        # Filter by date range
        start_date = request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(order_date__gte=start_date)
        
        end_date = request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(order_date__lte=end_date)
        
        # Order by date
        qs = qs.order_by('-order_date', '-created_at')
        
        serializer = SalesOrderListSerializer(qs, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new sales order."""
        company = request.company
        serializer = CreateSalesOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = SalesOrderService.create_order(
                company=company,
                customer_party_id=serializer.validated_data['customer_id'],
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
            
            response_serializer = SalesOrderSerializer(order)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SalesOrderDetailView(APIView):
    """
    Get, update, or delete a sales order.
    
    GET: Get order details
    PATCH: Update order
    DELETE: Delete order (if draft)
    """
    
    def get(self, request, order_id):
        """Get sales order details."""
        company = request.company
        
        try:
            order = SalesOrder.objects.select_related(
                'customer', 'currency', 'price_list'
            ).prefetch_related('orderitem_set__item').get(
                company=company,
                id=order_id
            )
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = SalesOrderSerializer(order)
        return Response(serializer.data)
    
    def patch(self, request, order_id):
        """Update sales order fields."""
        company = request.company
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
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
        
        serializer = SalesOrderSerializer(order)
        return Response(serializer.data)
    
    def delete(self, request, order_id):
        """Delete a draft order."""
        company = request.company
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if order.status != 'DRAFT':
            return Response(
                {'error': 'Can only delete draft orders'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SalesOrderAddItemView(APIView):
    """Add an item to a sales order."""
    
    def post(self, request, order_id):
        """Add item to order."""
        company = request.company
        serializer = AddOrderItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            line = SalesOrderService.add_item(
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


class SalesOrderUpdateItemView(APIView):
    """Update an order item."""
    
    def patch(self, request, order_id, item_id):
        """Update order item."""
        company = request.company
        serializer = UpdateOrderItemSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
            order_item = OrderItem.objects.get(
                order_content_type=order.get_content_type(),
                order_object_id=order.id,
                id=item_id
            )
        except (SalesOrder.DoesNotExist, OrderItem.DoesNotExist):
            return Response(
                {'error': 'Order or item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            updated_item = SalesOrderService.update_item(
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


class SalesOrderRemoveItemView(APIView):
    """Remove an item from a sales order."""
    
    def delete(self, request, order_id, item_id):
        """Remove item from order."""
        company = request.company
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
            order_item = OrderItem.objects.get(
                order_content_type=order.get_content_type(),
                order_object_id=order.id,
                id=item_id
            )
        except (SalesOrder.DoesNotExist, OrderItem.DoesNotExist):
            return Response(
                {'error': 'Order or item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            SalesOrderService.remove_item(order_item)
            return Response(status=status.HTTP_204_NO_CONTENT)
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SalesOrderConfirmView(APIView):
    """Confirm a sales order and reserve stock."""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, order_id):
        """Confirm order."""
        company = request.company
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            order = SalesOrderService.confirm_order(order, validate_stock=True, enforce_credit=True)
            serializer = SalesOrderSerializer(order)
            
            return Response({
                'order': serializer.data,
                'message': 'Order confirmed successfully'
            })
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class SalesOrderCancelView(APIView):
    """Cancel a sales order and release reservations."""
    permission_classes = [RolePermission.require(['ADMIN', 'SALES_MANAGER'])]
    
    def post(self, request, order_id):
        """Cancel order."""
        company = request.company
        serializer = CancelOrderSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            order = SalesOrder.objects.get(company=company, id=order_id)
        except SalesOrder.DoesNotExist:
            return Response(
                {'error': 'Sales order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            order = SalesOrderService.cancel_order(
                order,
                reason=serializer.validated_data.get('reason', '')
            )
            
            response_serializer = SalesOrderSerializer(order)
            return Response({
                'order': response_serializer.data,
                'message': 'Order cancelled and reservations released'
            })
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
