"""
Pricing API URL routing.
"""
from django.urls import path
from apps.pricing.api.views import (
    ItemPricingView,
    BulkItemPricingView
)

urlpatterns = [
    path('items/<uuid:item_id>/', ItemPricingView.as_view(), name='item-pricing'),
    path('items/bulk/', BulkItemPricingView.as_view(), name='bulk-item-pricing'),
]
