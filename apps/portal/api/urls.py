"""
Portal API URL routing.
Handles retailer registration, catalog, orders, and company discovery.
"""
from django.urls import path
from apps.portal.api.views_retailer import (
    RetailerRegisterView,
    RetailerCompleteProfileView,
    RetailerApproveView,
    RetailerRejectView,
    RetailerListView,
    CompanyDiscoveryView
)
from apps.portal.api.views_items import (
    PortalItemListView,
    PortalItemDetailView
)
from apps.portal.api.views_orders import (
    PortalOrderCreateView,
    PortalOrderListView,
    PortalOrderStatusView,
    PortalOrderReorderView
)
from apps.portal.api.views_retailer_portal import (
    RetailerProductListView,
    RetailerCategoryListView,
    RetailerPlaceOrderView,
    RetailerOrderListView
)
from apps.company.api.views_connection import (
    JoinByCompanyCodeView,
    RetailerCompanyListView
)

urlpatterns = [
    # Retailer onboarding (authenticated - user already registered via /users/register/)
    path('register/', RetailerRegisterView.as_view(), name='retailer-register'),
    path('complete-profile/', RetailerCompleteProfileView.as_view(), name='retailer-complete-profile'),
    path('companies/discover/', CompanyDiscoveryView.as_view(), name='company-discovery'),
    
    # Retailer company connection
    path('join-by-company-code/', JoinByCompanyCodeView.as_view(), name='retailer-join-by-code'),
    path('companies/', RetailerCompanyListView.as_view(), name='retailer-companies-list'),
    
    # Retailer management (admin)
    path('retailers/', RetailerListView.as_view(), name='retailer-list'),
    path('retailers/<uuid:retailer_id>/approve/', RetailerApproveView.as_view(), name='retailer-approve'),
    path('retailers/<uuid:retailer_id>/reject/', RetailerRejectView.as_view(), name='retailer-reject'),
    
    # Catalog (authenticated retailers)
    path('items/', PortalItemListView.as_view(), name='portal-items'),
    path('items/<uuid:item_id>/', PortalItemDetailView.as_view(), name='portal-item-detail'),
    
    # Orders (authenticated retailers)
    path('orders/', PortalOrderListView.as_view(), name='portal-orders-list'),
    path('orders/create/', PortalOrderCreateView.as_view(), name='portal-order-create'),
    path('orders/<uuid:order_id>/', PortalOrderStatusView.as_view(), name='portal-order-status'),
    path('orders/<uuid:order_id>/reorder/', PortalOrderReorderView.as_view(), name='portal-order-reorder'),
    
    # Retailer Portal - Product browsing and ordering
    path('products/', RetailerProductListView.as_view(), name='retailer-products'),
    path('categories/', RetailerCategoryListView.as_view(), name='retailer-categories'),
    path('orders/place/', RetailerPlaceOrderView.as_view(), name='retailer-place-order'),
    path('my-orders/', RetailerOrderListView.as_view(), name='retailer-my-orders'),
]
