"""
Inventory API views.
RESTful API endpoints for stock management.
"""
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError

from core.drf.viewsets import CompanyScopedViewSet
from core.drf.permissions import RolePermission

from apps.inventory import selectors
from apps.inventory.api.serializers import (
    StockItemSerializer, StockItemListSerializer,
    StockMovementSerializer, StockMovementCreateSerializer,
    StockReservationSerializer, StockBalanceSerializer,
    StockTransferSerializer, StockSummarySerializer,
    GodownSerializer
)
from apps.inventory.services.transfers import StockTransferService
from apps.inventory.services.guards import NegativeStockError
from apps.inventory.models import StockItem, StockMovement, StockReservation, Godown


class StockItemViewSet(CompanyScopedViewSet):
    """
    ViewSet for StockItem CRUD operations.
    
    list: Get all stock items for the company
    retrieve: Get a single stock item
    create: Create a new stock item
    update: Update a stock item
    destroy: Delete a stock item
    """
    queryset = StockItem.objects.all()
    serializer_class = StockItemSerializer
    
    def get_serializer_class(self):
        """Use lightweight serializer for list action."""
        if self.action == 'list':
            return StockItemListSerializer
        return StockItemSerializer
    
    def get_queryset(self):
        """Filter queryset with optional parameters."""
        qs = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        
        # Filter by product
        product_id = self.request.query_params.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        
        # Search by name or SKU
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(sku__icontains=search)
        
        return qs.select_related('company', 'product', 'uom')
    
    @action(detail=True, methods=['get'])
    def stock_summary(self, request, pk=None):
        """Get stock summary across all godowns for this item."""
        item = self.get_object()
        company = self.get_company()
        
        summary = selectors.get_item_stock_summary(company, item)
        serializer = StockSummarySerializer(summary)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def movements(self, request, pk=None):
        """Get movement history for this item."""
        item = self.get_object()
        company = self.get_company()
        
        # Get optional date filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        movement_type = request.query_params.get('movement_type')
        
        movements = selectors.list_stock_movements(
            company, item=item,
            movement_type=movement_type,
            start_date=start_date,
            end_date=end_date
        )
        
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


class GodownViewSet(CompanyScopedViewSet):
    """
    ViewSet for Godown (warehouse/location) CRUD operations.
    """
    queryset = Godown.objects.all()
    serializer_class = GodownSerializer
    
    def get_queryset(self):
        """Filter queryset with optional parameters."""
        qs = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        
        # Filter by godown type
        godown_type = self.request.query_params.get('godown_type')
        if godown_type:
            qs = qs.filter(godown_type=godown_type)
        
        return qs


class StockBalanceView(APIView):
    """
    Get current stock balance for an item.
    
    Query Parameters:
    - item: Item ID (required)
    - godown: Godown ID (optional)
    - batch: Batch number (optional)
    """
    
    def get(self, request):
        company = request.company
        item_id = request.query_params.get('item')
        godown_id = request.query_params.get('godown')
        batch = request.query_params.get('batch')
        
        if not item_id:
            return Response(
                {'error': 'item parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            item = selectors.get_item(company, item_id)
        except StockItem.DoesNotExist:
            return Response(
                {'error': 'Item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get godown if specified
        godown = None
        if godown_id:
            try:
                godown = Godown.objects.get(company=company, id=godown_id)
            except Godown.DoesNotExist:
                return Response(
                    {'error': 'Godown not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get balance
        bal = selectors.current_stock(company, item, godown, batch)
        
        if bal:
            serializer = StockBalanceSerializer(bal)
            return Response(serializer.data)
        else:
            return Response({
                'item': item.name,
                'item_id': item.id,
                'godown': godown.name if godown else 'All',
                'quantity': 0,
                'message': 'No stock balance found'
            })


class StockBalanceListView(APIView):
    """
    List all stock balances with optional filters.
    
    Query Parameters:
    - item: Item ID (optional)
    - godown: Godown ID (optional)
    - min_quantity: Minimum quantity filter (optional)
    """
    
    def get(self, request):
        company = request.company
        
        item_id = request.query_params.get('item')
        godown_id = request.query_params.get('godown')
        min_quantity = request.query_params.get('min_quantity')
        
        # Get optional filters
        item = None
        if item_id:
            try:
                item = selectors.get_item(company, item_id)
            except StockItem.DoesNotExist:
                return Response(
                    {'error': 'Item not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        godown = None
        if godown_id:
            try:
                godown = Godown.objects.get(company=company, id=godown_id)
            except Godown.DoesNotExist:
                return Response(
                    {'error': 'Godown not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # List balances
        balances = selectors.list_stock_balances(
            company, item=item, godown=godown, min_quantity=min_quantity
        )
        
        serializer = StockBalanceSerializer(balances, many=True)
        return Response(serializer.data)


class StockMovementView(APIView):
    """
    Create and list stock movements.
    
    POST: Create a new stock movement (IN or OUT)
    GET: List stock movements with optional filters
    """
    permission_classes = [RolePermission.require(['ADMIN', 'INVENTORY_MANAGER'])]
    
    def post(self, request):
        """Create a new stock movement."""
        company = request.company
        serializer = StockMovementCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            movement = StockTransferService.create_movement(
                company=company,
                item_id=data['item_id'],
                godown_id=data['godown_id'],
                quantity=data['quantity'],
                movement_type=data['movement_type'],
                rate=data.get('rate'),
                reason=data.get('reason', ''),
                batch=data.get('batch'),
                reference_type=data.get('reference_type'),
                reference_id=data.get('reference_id')
            )
            
            response_serializer = StockMovementSerializer(movement)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            
        except (DjangoValidationError, NegativeStockError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get(self, request):
        """List stock movements with filters."""
        company = request.company
        
        item_id = request.query_params.get('item')
        godown_id = request.query_params.get('godown')
        movement_type = request.query_params.get('movement_type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Get optional filters
        item = None
        if item_id:
            try:
                item = selectors.get_item(company, item_id)
            except StockItem.DoesNotExist:
                return Response(
                    {'error': 'Item not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        godown = None
        if godown_id:
            try:
                godown = Godown.objects.get(company=company, id=godown_id)
            except Godown.DoesNotExist:
                return Response(
                    {'error': 'Godown not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # List movements
        movements = selectors.list_stock_movements(
            company, item=item, godown=godown,
            movement_type=movement_type,
            start_date=start_date, end_date=end_date
        )
        
        serializer = StockMovementSerializer(movements, many=True)
        return Response(serializer.data)


class StockTransferView(APIView):
    """
    Handle stock transfers between godowns.
    
    POST: Create a new stock transfer
    GET: List transfer history
    """
    permission_classes = [RolePermission.require(['ADMIN', 'INVENTORY_MANAGER'])]
    
    def post(self, request):
        """Create a stock transfer."""
        company = request.company
        serializer = StockTransferSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        try:
            out_movement, in_movement = StockTransferService.transfer(
                company=company,
                item_id=data['item_id'],
                from_godown_id=data['from_godown_id'],
                to_godown_id=data['to_godown_id'],
                qty=data['quantity'],
                rate=data.get('rate'),
                reason=data.get('reason', ''),
                batch=data.get('batch')
            )
            
            return Response({
                'status': 'ok',
                'message': 'Stock transfer completed successfully',
                'out_movement': StockMovementSerializer(out_movement).data,
                'in_movement': StockMovementSerializer(in_movement).data
            }, status=status.HTTP_201_CREATED)
            
        except (DjangoValidationError, NegativeStockError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get(self, request):
        """List transfer history."""
        company = request.company
        
        item_id = request.query_params.get('item')
        godown_id = request.query_params.get('godown')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Get optional filters
        item = None
        if item_id:
            try:
                item = selectors.get_item(company, item_id)
            except StockItem.DoesNotExist:
                return Response(
                    {'error': 'Item not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        godown = None
        if godown_id:
            try:
                godown = Godown.objects.get(company=company, id=godown_id)
            except Godown.DoesNotExist:
                return Response(
                    {'error': 'Godown not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get transfer history
        transfers = StockTransferService.get_transfer_history(
            company, item=item, godown=godown,
            start_date=start_date, end_date=end_date
        )
        
        serializer = StockMovementSerializer(transfers, many=True)
        return Response(serializer.data)


class StockReservationView(APIView):
    """
    Manage stock reservations.
    
    GET: List reservations
    POST: Create a new reservation
    """
    
    def get(self, request):
        """List stock reservations."""
        company = request.company
        
        item_id = request.query_params.get('item')
        reservation_status = request.query_params.get('status')
        
        # Get optional filter
        item = None
        if item_id:
            try:
                item = selectors.get_item(company, item_id)
            except StockItem.DoesNotExist:
                return Response(
                    {'error': 'Item not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        reservations = selectors.list_reservations(
            company, item=item, status=reservation_status
        )
        
        serializer = StockReservationSerializer(reservations, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new reservation."""
        company = request.company
        serializer = StockReservationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate stock availability
        try:
            from apps.inventory.services.guards import ensure_reservation_available
            
            item = selectors.get_item(company, serializer.validated_data['item'].id)
            godown = serializer.validated_data.get('godown')
            quantity = serializer.validated_data['quantity']
            
            if godown:
                ensure_reservation_available(company, item, quantity, godown)
            
            # Save reservation
            reservation = serializer.save(company=company)
            
            return Response(
                StockReservationSerializer(reservation).data,
                status=status.HTTP_201_CREATED
            )
            
        except DjangoValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
