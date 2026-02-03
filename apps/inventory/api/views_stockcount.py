"""
Stock count API views for manufacturer portal.
Provides inventory overview and stock counting functionality.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Q, F
from django.db import transaction

from apps.inventory.models import StockItem, StockBalance, Godown
from apps.products.models import Product
from apps.company.models import CompanyUser


class StockCountListView(APIView):
    """
    List all stock items with their current quantities.
    
    GET /inventory/stockcount/
    
    Query Parameters:
        - search: Search by SKU or name
        - category: Filter by product category
        - godown: Filter by godown/warehouse
        - low_stock: Show only low stock items (boolean)
    
    Response:
    [
        {
            "id": "uuid",
            "sku": "PROD001",
            "name": "Product Name",
            "category": "Category Name",
            "current_stock": 100,
            "uom": "PCS",
            "godowns": [
                {
                    "godown_name": "Warehouse A",
                    "quantity": 100
                }
            ],
            "product_details": {
                "price": "1000.00",
                "available_quantity": 100
            }
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List stock items with quantities."""
        # Get user's company - use filter().first() to handle multiple records
        company_user = CompanyUser.objects.select_related('company').filter(
            user=request.user,
            is_active=True,
            is_default=True
        ).first()
        
        if not company_user:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        company = company_user.company
        
        # Base queryset
        stock_items = StockItem.objects.filter(
            company=company,
            is_active=True,
            is_stock_item=True
        ).select_related('uom', 'product', 'product__category').prefetch_related(
            'stock_balances', 'stock_balances__godown'
        ).order_by('name')
        
        # Search filter
        search = request.query_params.get('search', '').strip()
        if search:
            stock_items = stock_items.filter(
                Q(sku__icontains=search) | Q(name__icontains=search)
            )
        
        # Category filter (via product)
        category = request.query_params.get('category', '').strip()
        if category:
            stock_items = stock_items.filter(product__category__name__icontains=category)
        
        # Godown filter
        godown_id = request.query_params.get('godown')
        if godown_id:
            stock_items = stock_items.filter(stock_balances__godown_id=godown_id)
        
        # Build response
        data = []
        for item in stock_items:
            # Get stock balances per godown
            balances = item.stock_balances.all()
            total_stock = sum(b.quantity for b in balances)
            
            godown_data = []
            for balance in balances:
                if balance.quantity > 0:  # Only show godowns with stock
                    godown_data.append({
                        "godown_id": str(balance.godown.id) if balance.godown else None,
                        "godown_name": balance.godown.name if balance.godown else "Default",
                        "quantity": float(balance.quantity)
                    })
            
            # Get product details if linked
            product_details = None
            if item.product:
                product_details = {
                    "id": str(item.product.id),
                    "name": item.product.name,
                    "price": str(item.product.price),
                    "available_quantity": item.product.available_quantity,
                    "category": item.product.category.name if item.product.category else None,
                    "hsn_code": item.product.hsn_code
                }
            
            # Low stock filter
            low_stock_only = request.query_params.get('low_stock') == 'true'
            if low_stock_only and total_stock > 10:  # Threshold can be configurable
                continue
            
            data.append({
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "description": item.description,
                "current_stock": float(total_stock),
                "uom": item.uom.symbol if item.uom else "PCS",
                "uom_name": item.uom.name if item.uom else "Pieces",
                "godowns": godown_data,
                "product_details": product_details,
                "is_active": item.is_active
            })
        
        return Response(data)


class StockCountByProductView(APIView):
    """
    Get stock count aggregated by products (for portal view).
    
    GET /inventory/stockcount/by-product/
    
    Response:
    [
        {
            "product_id": "uuid",
            "product_name": "Product Name",
            "category": "Category Name",
            "total_quantity": 100,
            "price": "1000.00",
            "unit": "PCS",
            "hsn_code": "1234",
            "stock_items": [
                {
                    "sku": "PROD001",
                    "quantity": 100
                }
            ]
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get stock grouped by products."""
        # Get user's company - use filter().first() to handle multiple records
        company_user = CompanyUser.objects.select_related('company').filter(
            user=request.user,
            is_active=True,
            is_default=True
        ).first()
        
        if not company_user:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        company = company_user.company
        
        # Get all products with stock items (exclude discontinued products)
        products = Product.objects.filter(
            company=company
        ).exclude(
            status='discontinued'
        ).select_related('category').prefetch_related(
            'stockitems', 'stockitems__stock_balances'
        ).order_by('name')
        
        # Search filter
        search = request.query_params.get('search', '').strip()
        if search:
            products = products.filter(
                Q(name__icontains=search) | 
                Q(category__name__icontains=search)
            )
        
        # Category filter
        category = request.query_params.get('category', '').strip()
        if category:
            products = products.filter(category__name__icontains=category)
        
        data = []
        for product in products:
            # Calculate total stock from all stock items
            total_quantity = 0
            stock_items_data = []
            
            for stock_item in product.stockitems.filter(is_active=True, is_stock_item=True):
                item_quantity = sum(
                    b.quantity for b in stock_item.stock_balances.all()
                )
                total_quantity += item_quantity
                
                if item_quantity > 0:
                    stock_items_data.append({
                        "sku": stock_item.sku,
                        "name": stock_item.name,
                        "quantity": float(item_quantity),
                        "uom": stock_item.uom.symbol if stock_item.uom else "PCS"
                    })
            
            data.append({
                "product_id": str(product.id),
                "product_name": product.name,
                "category": product.category.name if product.category else None,
                "category_id": str(product.category.id) if product.category else None,
                "total_quantity": float(total_quantity) if total_quantity > 0 else float(product.available_quantity),
                "available_quantity": product.available_quantity,
                "total_shipped": product.total_shipped,
                "total_required_quantity": product.total_required_quantity,
                "price": str(product.price),
                "unit": product.unit,
                "hsn_code": product.hsn_code,
                "brand": product.brand,
                "stock_items": stock_items_data
            })
        
        return Response(data)


class GodownListView(APIView):
    """
    List all godowns/warehouses.
    
    GET /inventory/godowns/
    
    Response:
    [
        {
            "id": "uuid",
            "name": "Warehouse A",
            "code": "WH-A",
            "location": "Location details",
            "is_active": true
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all godowns."""
        # Get user's company
        try:
            company_user = CompanyUser.objects.select_related('company').get(
                user=request.user,
                is_active=True,
                is_default=True
            )
            company = company_user.company
        except CompanyUser.DoesNotExist:
            return Response(
                {"error": "No active company found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        godowns = Godown.objects.filter(
            company=company,
            is_active=True
        ).order_by('name')
        
        data = [{
            "id": str(g.id),
            "name": g.name,
            "code": g.code,
            "is_active": g.is_active
        } for g in godowns]
        
        return Response(data)
