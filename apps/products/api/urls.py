"""
URL patterns for Products API.
Provides CRUD endpoints for Product and Category management.
"""
from django.urls import path
from apps.products.api.views import (
    CategoryListCreateView,
    CategoryDetailView,
    ProductListCreateView,
    ProductDetailView,
    ProductSyncStockView
)

urlpatterns = [
    # Category endpoints
    path('categories/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<uuid:category_id>/', CategoryDetailView.as_view(), name='category-detail'),
    
    # Product endpoints
    path('products/', ProductListCreateView.as_view(), name='product-list-create'),
    path('products/<uuid:product_id>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<uuid:product_id>/sync-stock/', ProductSyncStockView.as_view(), name='product-sync-stock'),
]
