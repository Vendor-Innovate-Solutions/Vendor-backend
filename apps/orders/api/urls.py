"""
Order API URL routing.
Maps endpoints to views for both sales and purchase orders.
"""
from django.urls import path
from apps.orders.api.views_sales import (
    SalesOrderListCreateView, SalesOrderDetailView,
    SalesOrderAddItemView, SalesOrderUpdateItemView,
    SalesOrderRemoveItemView, SalesOrderConfirmView,
    SalesOrderCancelView, SalesOrderDispatchView
)
from apps.orders.api.views_purchase import (
    PurchaseOrderListCreateView, PurchaseOrderDetailView,
    PurchaseOrderAddItemView, PurchaseOrderUpdateItemView,
    PurchaseOrderRemoveItemView, PurchaseOrderConfirmView,
    PurchaseOrderCancelView
)
from apps.orders.api.views_credit_notes import (
    CreditNoteListCreateView, CreditNoteDetailView
)
from apps.orders.api.views_pricelists import (
    PriceListListCreateView, PriceListDetailView,
    PriceListItemManageView
)

urlpatterns = [
    # Sales Order endpoints
    path('sales/', SalesOrderListCreateView.as_view(), name='sales-order-list-create'),
    path('sales/<uuid:order_id>/', SalesOrderDetailView.as_view(), name='sales-order-detail'),
    path('sales/<uuid:order_id>/add_item/', SalesOrderAddItemView.as_view(), name='sales-order-add-item'),
    path('sales/<uuid:order_id>/items/<uuid:item_id>/', SalesOrderUpdateItemView.as_view(), name='sales-order-update-item'),
    path('sales/<uuid:order_id>/items/<uuid:item_id>/remove/', SalesOrderRemoveItemView.as_view(), name='sales-order-remove-item'),
    path('sales/<uuid:order_id>/confirm/', SalesOrderConfirmView.as_view(), name='sales-order-confirm'),
    path('sales/<uuid:order_id>/cancel/', SalesOrderCancelView.as_view(), name='sales-order-cancel'),
    path('sales/<uuid:order_id>/dispatch/', SalesOrderDispatchView.as_view(), name='sales-order-dispatch'),
    
    # Purchase Order endpoints
    path('purchase/', PurchaseOrderListCreateView.as_view(), name='purchase-order-list-create'),
    path('purchase/<uuid:order_id>/', PurchaseOrderDetailView.as_view(), name='purchase-order-detail'),
    path('purchase/<uuid:order_id>/add_item/', PurchaseOrderAddItemView.as_view(), name='purchase-order-add-item'),
    path('purchase/<uuid:order_id>/items/<uuid:item_id>/', PurchaseOrderUpdateItemView.as_view(), name='purchase-order-update-item'),
    path('purchase/<uuid:order_id>/items/<uuid:item_id>/remove/', PurchaseOrderRemoveItemView.as_view(), name='purchase-order-remove-item'),
    path('purchase/<uuid:order_id>/confirm/', PurchaseOrderConfirmView.as_view(), name='purchase-order-confirm'),
    path('purchase/<uuid:order_id>/cancel/', PurchaseOrderCancelView.as_view(), name='purchase-order-cancel'),
    
    # Credit Note endpoints
    path('credit-notes/', CreditNoteListCreateView.as_view(), name='credit-note-list-create'),
    path('credit-notes/<uuid:cn_id>/', CreditNoteDetailView.as_view(), name='credit-note-detail'),
    
    # Price List endpoints
    path('price-lists/', PriceListListCreateView.as_view(), name='price-list-list-create'),
    path('price-lists/<uuid:pl_id>/', PriceListDetailView.as_view(), name='price-list-detail'),
    path('price-lists/<uuid:pl_id>/items/', PriceListItemManageView.as_view(), name='price-list-add-item'),
    path('price-lists/<uuid:pl_id>/items/<uuid:item_id>/', PriceListItemManageView.as_view(), name='price-list-remove-item'),
]
