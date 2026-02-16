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
from apps.party.models import Party
from apps.products.models import Product, Category
from apps.inventory.models import StockItem, StockBalance
from apps.orders.models import SalesOrder, OrderItem
from apps.orders.services.sales_order_service import SalesOrderService


def _approved_connections_for_user(user):
    """Return approved retailer-company links for a user across all companies."""
    return RetailerCompanyAccess.objects.select_related(
        'company', 'retailer', 'retailer__party'
    ).filter(
        retailer__user=user,
        status='APPROVED'
    )


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

        # Get approved company connections across all retailer mappings for this user
        connected_company_ids = list(
            _approved_connections_for_user(user).values_list('company_id', flat=True).distinct()
        )

        if not connected_company_ids:
            return Response(
                {"message": "No company connections found. Please connect to a company first."},
                status=status.HTTP_200_OK,
                data=[]
            )
        
        # Filter by company if specified
        company_id = request.query_params.get('company_id')
        if company_id:
            if company_id not in [str(c) for c in connected_company_ids]:
                return Response(
                    {"error": "You are not connected to this company"},
                    status=status.HTTP_403_FORBIDDEN
                )
            company_ids = [company_id]
        else:
            company_ids = connected_company_ids
        
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

        # Get approved company connections across all retailer mappings for this user
        connected_company_ids = list(
            _approved_connections_for_user(user).values_list('company_id', flat=True).distinct()
        )

        if not connected_company_ids:
            return Response([], status=status.HTTP_200_OK)
        
        # Filter by company if specified
        company_id = request.query_params.get('company_id')
        if company_id:
            company_ids = [company_id]
        else:
            company_ids = connected_company_ids
        
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
        
        # Verify approved connection for this user + company
        connection = _approved_connections_for_user(user).filter(
            company_id=company_id
        ).first()

        if not connection:
            return Response(
                {"error": "You are not connected to this company or connection is not approved"},
                status=status.HTTP_403_FORBIDDEN
            )

        company = connection.company
        party = connection.retailer.party
        if not party or party.company != company:
            # Backfill missing party mapping for legacy/partially migrated retailer records.
            party = Party.objects.filter(company=company, email=user.email).first()
            if not party:
                party = Party.objects.create(
                    company=company,
                    name=user.get_full_name() or user.email,
                    party_type='CUSTOMER',
                    email=user.email,
                    phone=user.phone or '',
                    is_retailer=True
                )
            connection.retailer.party = party
            connection.retailer.save(update_fields=['party'])
        
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

        # Collect all approved retailer parties for this user
        party_ids = list(
            _approved_connections_for_user(user).exclude(
                retailer__party__isnull=True
            ).values_list('retailer__party_id', flat=True).distinct()
        )

        if not party_ids:
            return Response([], status=status.HTTP_200_OK)

        # Get orders
        orders = SalesOrder.objects.filter(
            customer_id__in=party_ids
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

class RetailerInvoiceListView(APIView):
    """
    Get list of invoices for retailer.
    
    GET /portal/my-invoices/
    
    Query Parameters:
        - company_id: Filter by company
        - status: Filter by status (DRAFT, POSTED, PAID, etc.)
    
    Response:
    [
        {
            "id": "uuid",
            "invoice_number": "INV-000001",
            "company_name": "ABC Manufacturing",
            "status": "POSTED",
            "invoice_date": "2026-02-01",
            "due_date": "2026-02-15",
            "subtotal": "10000.00",
            "tax_amount": "1800.00",
            "grand_total": "11800.00",
            "amount_received": "0.00",
            "outstanding_amount": "11800.00"
        }
    ]
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List retailer's invoices."""
        from apps.invoice.models import Invoice
        
        user = request.user

        # Collect all approved retailer parties for this user
        party_ids = list(
            _approved_connections_for_user(user).exclude(
                retailer__party__isnull=True
            ).values_list('retailer__party_id', flat=True).distinct()
        )

        if not party_ids:
            return Response([], status=status.HTTP_200_OK)

        # Get invoices for this party
        invoices = Invoice.objects.filter(
            party_id__in=party_ids
        ).select_related('company', 'currency').order_by('-invoice_date', '-created_at')
        
        # Filter by company
        company_id = request.query_params.get('company_id')
        if company_id:
            invoices = invoices.filter(company_id=company_id)
        
        # Filter by status
        invoice_status = request.query_params.get('status')
        if invoice_status:
            invoices = invoices.filter(status=invoice_status.upper())
        
        data = []
        for invoice in invoices:
            outstanding = invoice.grand_total - invoice.amount_received
            
            data.append({
                "id": str(invoice.id),
                "invoice_number": invoice.invoice_number,
                "company_name": invoice.company.name,
                "company_id": str(invoice.company.id),
                "status": invoice.status,
                "invoice_date": invoice.invoice_date.isoformat(),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "subtotal": str(invoice.subtotal),
                "tax_amount": str(invoice.tax_amount),
                "grand_total": str(invoice.grand_total),
                "amount_received": str(invoice.amount_received),
                "outstanding_amount": str(outstanding),
                "order_number": invoice.sales_order.order_number if invoice.sales_order else None,
                "created_at": invoice.created_at.isoformat()
            })
        
        return Response(data)


class RetailerInvoiceDetailView(APIView):
    """
    API endpoint for retailers to view a specific invoice with line items.
    GET /portal/my-invoices/<invoice_id>/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, invoice_id):
        """Get invoice detail with line items."""
        from apps.invoice.models import Invoice, InvoiceLine
        
        user = request.user

        # Collect all approved retailer parties for this user
        party_ids = list(
            _approved_connections_for_user(user).exclude(
                retailer__party__isnull=True
            ).values_list('retailer__party_id', flat=True).distinct()
        )

        if not party_ids:
            return Response({"error": "Retailer profile not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get the invoice only if it belongs to one of the user's approved retailer parties
        try:
            invoice = Invoice.objects.select_related(
                'company', 'party', 'currency', 'sales_order'
            ).get(id=invoice_id, party_id__in=party_ids)
        except Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Get line items - use correct field names: 'item' and 'uom'
        lines = InvoiceLine.objects.filter(invoice=invoice).select_related('item', 'uom')
        
        line_items = []
        for line in lines:
            # Get product name from StockItem
            product_name = line.item.name if line.item else line.description
            hsn_code = line.item.hsn_code if line.item and hasattr(line.item, 'hsn_code') else None
            
            line_items.append({
                "id": str(line.id),
                "product_name": product_name,
                "description": line.description or product_name,
                "hsn_code": hsn_code,
                "quantity": str(line.quantity),
                "unit": line.uom.name if line.uom else None,
                "unit_rate": str(line.unit_rate),
                "discount_percent": str(line.discount_pct),
                "discount_amount": "0.00",  # Calculate if needed
                "taxable_value": str(line.line_total),  # Line total before tax
                "cgst_rate": "0",
                "cgst_amount": "0",
                "sgst_rate": "0",
                "sgst_amount": "0",
                "igst_rate": "0",
                "igst_amount": "0",
                "tax_amount": str(line.tax_amount),
                "line_total": str(line.line_total + line.tax_amount),
            })
        
        outstanding = invoice.grand_total - invoice.amount_received
        
        data = {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "invoice_type": invoice.invoice_type,
            "status": invoice.status,
            "invoice_date": invoice.invoice_date.isoformat(),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            
            # Company details
            "company": {
                "id": str(invoice.company.id),
                "name": invoice.company.name,
                "gstin": invoice.company.gstin if hasattr(invoice.company, 'gstin') else None,
                "address": invoice.company.address if hasattr(invoice.company, 'address') else None,
            },
            
            # Party details
            "party": {
                "id": str(invoice.party.id),
                "name": invoice.party.name,
                "gstin": invoice.party.gstin if hasattr(invoice.party, 'gstin') else None,
                "address": invoice.party.address if hasattr(invoice.party, 'address') else None,
            },
            
            # Line items
            "items": line_items,
            
            # Totals
            "subtotal": str(invoice.subtotal),
            "discount_total": str(invoice.discount_total) if hasattr(invoice, 'discount_total') else "0.00",
            "tax_amount": str(invoice.tax_amount),
            "grand_total": str(invoice.grand_total),
            "amount_received": str(invoice.amount_received),
            "outstanding_amount": str(outstanding),
            
            # Order reference
            "sales_order": {
                "id": str(invoice.sales_order.id),
                "order_number": invoice.sales_order.order_number,
            } if invoice.sales_order else None,
            
            "notes": invoice.notes if hasattr(invoice, 'notes') else None,
            "created_at": invoice.created_at.isoformat(),
        }
        
        return Response(data)
