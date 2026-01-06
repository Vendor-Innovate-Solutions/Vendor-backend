"""
API views for Products app.
Provides CRUD operations for Product and Category catalog management.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count

from apps.products.models import Product, Category
from apps.products.api.serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductCreateUpdateSerializer
)


class CategoryListCreateView(APIView):
    """
    List all categories or create a new one.
    
    GET: Returns all categories for the company
    POST: Creates a new category
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all categories with product counts."""
        categories = Category.objects.filter(
            company=request.company
        ).annotate(
            product_count=Count('products')
        ).order_by('display_order', 'name')
        
        serializer = CategorySerializer(categories, many=True)
        return Response({
            'categories': serializer.data,
            'count': categories.count()
        })
    
    def post(self, request):
        """Create a new category."""
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(company=request.company)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailView(APIView):
    """
    Retrieve, update, or delete a category.
    
    GET: Returns category details
    PUT: Updates category
    PATCH: Partially updates category
    DELETE: Deletes category (if no products attached)
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, request, category_id):
        """Get category ensuring company scope."""
        try:
            return Category.objects.annotate(
                product_count=Count('products')
            ).get(id=category_id, company=request.company)
        except Category.DoesNotExist:
            return None
    
    def get(self, request, category_id):
        """Get category details."""
        category = self.get_object(request, category_id)
        if not category:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CategorySerializer(category)
        return Response(serializer.data)
    
    def put(self, request, category_id):
        """Update category."""
        category = self.get_object(request, category_id)
        if not category:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, category_id):
        """Partially update category."""
        category = self.get_object(request, category_id)
        if not category:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, category_id):
        """Delete category if no products attached."""
        category = self.get_object(request, category_id)
        if not category:
            return Response(
                {'error': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if category.products.exists():
            return Response(
                {'error': 'Cannot delete category with products. Move or delete products first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductListCreateView(APIView):
    """
    List all products or create a new one.
    
    GET: Returns products with filtering/search
    POST: Creates a new product
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        List products with filtering.
        
        Query params:
            q: Search in name, brand, description
            category_id: Filter by category UUID
            brand: Filter by brand
            status: Filter by status
            is_portal_visible: Filter by portal visibility
            is_featured: Filter featured products
            limit: Max results (default: 100, max: 500)
        """
        qs = Product.objects.filter(company=request.company).select_related('category')
        
        # Search
        search = request.query_params.get('q', '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(brand__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Filters
        category_id = request.query_params.get('category_id')
        if category_id:
            qs = qs.filter(category_id=category_id)
        
        brand = request.query_params.get('brand')
        if brand:
            qs = qs.filter(brand__icontains=brand)
        
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        is_portal_visible = request.query_params.get('is_portal_visible')
        if is_portal_visible is not None:
            qs = qs.filter(is_portal_visible=is_portal_visible.lower() == 'true')
        
        is_featured = request.query_params.get('is_featured')
        if is_featured is not None:
            qs = qs.filter(is_featured=is_featured.lower() == 'true')
        
        # Limit
        limit = min(int(request.query_params.get('limit', 100)), 500)
        qs = qs[:limit]
        
        serializer = ProductListSerializer(qs, many=True)
        return Response({
            'products': serializer.data,
            'count': len(serializer.data)
        })
    
    def post(self, request):
        """Create a new product."""
        serializer = ProductCreateUpdateSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            product = serializer.save()
            # Return detailed view
            detail_serializer = ProductDetailSerializer(product)
            return Response(detail_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductDetailView(APIView):
    """
    Retrieve, update, or delete a product.
    
    GET: Returns product details with linked stock items
    PUT: Updates product
    PATCH: Partially updates product
    DELETE: Deletes product (soft delete recommended)
    """
    permission_classes = [IsAuthenticated]
    
    def get_object(self, request, product_id):
        """Get product ensuring company scope."""
        try:
            return Product.objects.select_related('category', 'created_by').get(
                id=product_id,
                company=request.company
            )
        except Product.DoesNotExist:
            return None
    
    def get(self, request, product_id):
        """Get product details."""
        product = self.get_object(request, product_id)
        if not product:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProductDetailSerializer(product)
        return Response(serializer.data)
    
    def put(self, request, product_id):
        """Update product."""
        product = self.get_object(request, product_id)
        if not product:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProductCreateUpdateSerializer(
            product,
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            # Return detailed view
            detail_serializer = ProductDetailSerializer(product)
            return Response(detail_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, product_id):
        """Partially update product."""
        product = self.get_object(request, product_id)
        if not product:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ProductCreateUpdateSerializer(
            product,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            # Return detailed view
            detail_serializer = ProductDetailSerializer(product)
            return Response(detail_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, product_id):
        """Delete product."""
        product = self.get_object(request, product_id)
        if not product:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if product has linked stock items
        if product.stockitems.exists():
            return Response(
                {
                    'error': 'Cannot delete product with linked stock items.',
                    'suggestion': 'Set is_portal_visible=False to hide instead.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductSyncStockView(APIView):
    """
    Sync product availability from linked stock items.
    
    POST: Triggers update_stock_from_items() for a product
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, product_id):
        """Sync stock availability."""
        try:
            product = Product.objects.get(id=product_id, company=request.company)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update from stock items
        product.update_stock_from_items()
        
        serializer = ProductDetailSerializer(product)
        return Response({
            'message': 'Stock synced successfully',
            'product': serializer.data
        })
