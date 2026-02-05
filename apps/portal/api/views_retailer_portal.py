"""
Retailer portal APIs for viewing products and placing orders.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from apps.portal.models import RetailerCompanyAccess
from apps.party.models import RetailerUser
from apps.products.models import Product, Category
from apps.inventory.models import StockItem, StockBalance
from apps.orders.models import SalesOrder, OrderItem
from apps.orders.services.sales_order_service import SalesOrderService


class RetailerProductListView(APIView):
    """
    View available products from connected companies.
    
    GET /retailer/products/
    
    Query Parameters:
        - company_id: Filter by specific company
        - category: Filter by category
        - search: Search by name
        - in_stock: Only show in-stock items (boolean)
    
    Response:
    [
        {
            "id": "uuid",
            "name": "Product Name",
            "category": "Category Name",
            "price": "1000.00",
            "available_quantity": 100,
            "unit": "PCS",
            "hsn_code": "1234",
            "company": {
                "id": "uuid",
                "name": "ABC Manufacturing",
                "code": "ABC001"
            },
            "in_stock": true
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List products from connected companies."""
        user = request.user
        
        # Get retailer profile
        try:
            retailer = RetailerUser.objects.get(user=user)
        except RetailerUser.DoesNotExist:
            return Response(
                {"error": "Retailer profile not found. Please complete your profile first."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get approved company connections
        connections = RetailerCompanyAccess.objects.filter(
            retailer=retailer,
            status='APPROVED'
        ).select_related('company').values_list('company_id', flat=True)
        
        if not connections:
            return Response(
                {"message": "No company connections found. Please connect to a company first."},
                status=status.HTTP_200_OK,
                data=[]
            )
        
        # Filter by company if specified
        company_id = request.query_params.get('company_id')
        if company_id:
            if company_id not in [str(c) for c in connections]:
                return Response(
                    {"error": "You are not connected to this company"},
                    status=status.HTTP_403_FORBIDDEN
                )
            company_ids = [company_id]
        else:
            company_ids = connections
        
        # Get products from connected companies
        products = Product.objects.filter(
            company_id__in=company_ids,
            is_portal_visible=True,
            status='available'
        ).select_related('company', 'category').prefetch_related(
            'stockitems', 'stockitems__stock_balances'
        ).order_by('company__name', 'name')
        
        # Search filter
        search = request.query_params.get('search', '').strip()
        if search:
            products = products.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(category__name__icontains=search)
            )
        
        # Category filter
        category = request.query_params.get('category', '').strip()
        if category:
            products = products.filter(category__name__icontains=category)
        
        # In-stock filter
        in_stock_only = request.query_params.get('in_stock') == 'true'
        
        data = []
        for product in products:
            # Use product's available_quantity field (display quantity)
            # Note: This is the portal display field, actual stock tracking is in StockItem
            total_stock = product.available_quantity
            
            # Skip if in_stock filter is on and no stock
            if in_stock_only and total_stock <= 0:
                continue
            
            data.append({
                "id": str(product.id),
                "name": product.name,
                "description": product.description,
                "category": product.category.name if product.category else None,
                "category_id": str(product.category.id) if product.category else None,
                "price": str(product.price),
                "available_quantity": int(total_stock),
                "unit": product.unit,
                "hsn_code": product.hsn_code,
                "brand": product.brand,
                "company": {
                    "id": str(product.company.id),
                    "name": product.company.name,
                    "code": product.company.code
                },
                "in_stock": total_stock > 0,
                "cgst_rate": str(product.cgst_rate),
                "sgst_rate": str(product.sgst_rate),
                "igst_rate": str(product.igst_rate)
            })
        
        return Response(data)


class RetailerCategoryListView(APIView):
    """
    Get product categories from connected companies.
    
    GET /retailer/categories/
    
    Query Parameters:
        - company_id: Filter by specific company
    
    Response:
    [
        {
            "id": "uuid",
            "name": "Category Name",
            "product_count": 10,
            "company": {
                "id": "uuid",
                "name": "Company Name"
            }
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List categories from connected companies."""
        user = request.user
        
        # Get retailer profile
        try:
            retailer = RetailerUser.objects.get(user=user)
        except RetailerUser.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        
        # Get approved connections
        connections = RetailerCompanyAccess.objects.filter(
            retailer=retailer,
            status='APPROVED'
        ).values_list('company_id', flat=True)
        
        if not connections:
            return Response([], status=status.HTTP_200_OK)
        
        # Filter by company if specified
        company_id = request.query_params.get('company_id')
        if company_id:
            company_ids = [company_id]
        else:
            company_ids = connections
        
        # Get categories
        categories = Category.objects.filter(
            company_id__in=company_ids,
            is_active=True
        ).select_related('company').order_by('company__name', 'name')
        
        data = []
        for category in categories:
            product_count = Product.objects.filter(
                category=category,
                is_active=True
            ).count()
            
            data.append({
                "id": str(category.id),
                "name": category.name,
                "description": category.description,
                "product_count": product_count,
                "company": {
                    "id": str(category.company.id),
                    "name": category.company.name
                }
            })
        
        return Response(data)


class RetailerPlaceOrderView(APIView):
    """
    Place an order with a connected company.
    
    POST /retailer/orders/place/
    
    Request:
    {
        "company_id": "uuid",
        "items": [
            {
                "product_id": "uuid",
                "quantity": 10
            }
        ],
        "notes": "Optional order notes",
        "delivery_address": "Delivery address"
    }
    
    Response:
    {
        "message": "Order placed successfully",
        "order": {
            "id": "uuid",
            "order_number": "SO-001",
            "company_name": "ABC Manufacturing",
            "total_amount": "10000.00",
            "status": "PENDING",
            "created_at": "2026-02-01T..."
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        """Place order with company."""
        user = request.user
        
        # Get retailer profile
        try:
            retailer = RetailerUser.objects.get(user=user)
        except RetailerUser.DoesNotExist:
            return Response(
                {"error": "Retailer profile not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate request data
        company_id = request.data.get('company_id')
        items = request.data.get('items', [])
        
        if not company_id:
            return Response(
                {"error": "company_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not items or len(items) == 0:
            return Response(
                {"error": "At least one item is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify connection exists and is approved
        try:
            connection = RetailerCompanyAccess.objects.select_related('company').get(
                retailer=retailer,
                company_id=company_id,
                status='APPROVED'
            )
            company = connection.company
        except RetailerCompanyAccess.DoesNotExist:
            return Response(
                {"error": "You are not connected to this company or connection is not approved"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get retailer's party in this company
        party = retailer.party
        if not party or party.company != company:
            return Response(
                {"error": "Retailer party not found in this company"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create sales order
        try:
            from apps.company.models import Currency
            
            # Get company's base currency
            currency = company.base_currency
            
            # Create order using service (only pass supported parameters)
            order = SalesOrderService.create_order(
                company=company,
                customer_party_id=party.id,
                currency_id=currency.id,
                price_list_id=None,
                order_date=timezone.now().date(),
                created_by=user
            )
            
            # Set additional fields after creation
            order.notes = request.data.get('notes', 'Order from retailer portal')
            order.save()
            
            # Add items
            total_amount = Decimal('0.00')
            order_items = []
            
            for item_data in items:
                product_id = item_data.get('product_id')
                quantity = item_data.get('quantity', 1)
                
                if not product_id or quantity <= 0:
                    continue
                
                # Get product
                try:
                    product = Product.objects.get(
                        id=product_id,
                        company=company,
                        is_portal_visible=True
                    )
                    
                    # Get or create stock item for this product
                    stock_item = product.stockitems.filter(
                        is_active=True,
                        is_stock_item=True
                    ).first()
                    
                    if not stock_item:
                        # Create a stock item for this product
                        from apps.inventory.models import UnitOfMeasure
                        import uuid
                        
                        # Get or create default UOM
                        uom, _ = UnitOfMeasure.objects.get_or_create(
                            symbol=product.unit,
                            defaults={
                                'name': product.unit,
                            }
                        )
                        
                        # Generate unique SKU
                        sku = f"PRD-{str(product.id)[:8].upper()}"
                        
                        stock_item = StockItem.objects.create(
                            company=company,
                            product=product,
                            sku=sku,
                            name=product.name,
                            description=product.description or '',
                            uom=uom,
                            is_active=True,
                            is_stock_item=True
                        )
                    
                    # Add item to order
                    order_item = SalesOrderService.add_item(
                        order=order,
                        item_id=stock_item.id,
                        quantity=Decimal(str(quantity)),
                        override_rate=product.price
                    )
                    
                    order_items.append(order_item)
                    # Calculate line total: quantity * unit_rate * (1 - discount_pct/100)
                    line_total = order_item.quantity * order_item.unit_rate * (Decimal('1') - order_item.discount_pct / Decimal('100'))
                    total_amount += line_total
                    
                except Product.DoesNotExist:
                    continue
            
            if not order_items:
                # No valid items added, delete the order
                order.delete()
                return Response(
                    {"error": "No valid items were added to the order"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                "message": "Order placed successfully",
                "order": {
                    "id": str(order.id),
                    "order_number": order.order_number,
                    "company_name": company.name,
                    "company_id": str(company.id),
                    "total_items": len(order_items),
                    "total_amount": str(total_amount),
                    "status": order.status,
                    "created_at": order.created_at.isoformat(),
                    "notes": order.notes
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": f"Failed to create order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RetailerOrderListView(APIView):
    """
    Get list of orders placed by retailer.
    
    GET /retailer/orders/
    
    Query Parameters:
        - company_id: Filter by company
        - status: Filter by status
    
    Response:
    [
        {
            "id": "uuid",
            "order_number": "SO-001",
            "company_name": "ABC Manufacturing",
            "status": "PENDING",
            "order_date": "2026-02-01",
            "total_amount": "10000.00",
            "items_count": 5
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List retailer's orders."""
        user = request.user
        
        # Get retailer profile
        try:
            retailer = RetailerUser.objects.get(user=user)
            party = retailer.party
        except RetailerUser.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        
        if not party:
            return Response([], status=status.HTTP_200_OK)
        
        # Get orders
        orders = SalesOrder.objects.filter(
            customer=party
        ).select_related('company', 'currency').prefetch_related(
            'items'
        ).order_by('-order_date', '-created_at')
        
        # Filter by company
        company_id = request.query_params.get('company_id')
        if company_id:
            orders = orders.filter(company_id=company_id)
        
        # Filter by status
        order_status = request.query_params.get('status')
        if order_status:
            orders = orders.filter(status=order_status.upper())
        
        data = []
        for order in orders:
            # Calculate total (quantity * unit_rate for each item)
            items = order.items.all()
            total_amount = sum((item.quantity * item.unit_rate) for item in items)
            
            data.append({
                "id": str(order.id),
                "order_number": order.order_number,
                "company_name": order.company.name,
                "company_id": str(order.company.id),
                "status": order.status,
                "order_date": order.order_date.isoformat(),
                "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
                "total_amount": str(total_amount),
                "items_count": len(items),
                "notes": order.notes,
                "created_at": order.created_at.isoformat()
            })
        
        return Response(data)
