"""
Inventory API URL routing.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.inventory.api.views import (
    StockItemViewSet, GodownViewSet,
    StockBalanceView, StockBalanceListView,
    StockMovementView, StockTransferView,
    StockReservationView
)

router = DefaultRouter()
router.register('items', StockItemViewSet, basename='stock-items')
router.register('godowns', GodownViewSet, basename='godowns')

urlpatterns = [
    # Stock balance endpoints
    path('balance/', StockBalanceView.as_view(), name='stock-balance'),
    path('balances/', StockBalanceListView.as_view(), name='stock-balance-list'),
    
    # Stock movement endpoints
    path('movements/', StockMovementView.as_view(), name='stock-movements'),
    
    # Stock transfer endpoints
    path('transfers/', StockTransferView.as_view(), name='stock-transfers'),
    
    # Reservation endpoints
    path('reservations/', StockReservationView.as_view(), name='stock-reservations'),
]

urlpatterns += router.urls
