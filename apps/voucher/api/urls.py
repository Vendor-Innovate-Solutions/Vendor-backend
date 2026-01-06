"""
Payment and Voucher API URL routing.
Maps endpoints to views for payment operations and voucher reversal.
"""
from django.urls import path
from apps.voucher.api.views import (
    PaymentCreateView,
    PaymentListView,
    PaymentDetailView,
    PaymentAllocateView,
    PaymentRemoveAllocationView,
    PaymentPostVoucherView,
    VoucherReversalView
)

urlpatterns = [
    # Payment CRUD
    path('create/', PaymentCreateView.as_view(), name='payment-create'),
    path('', PaymentListView.as_view(), name='payment-list'),
    path('<uuid:payment_id>/', PaymentDetailView.as_view(), name='payment-detail'),
    
    # Allocation
    path('<uuid:payment_id>/allocate/', PaymentAllocateView.as_view(), name='payment-allocate'),
    path('<uuid:payment_id>/lines/<uuid:line_id>/', PaymentRemoveAllocationView.as_view(), name='payment-remove-allocation'),
    
    # Posting
    path('<uuid:payment_id>/post_voucher/', PaymentPostVoucherView.as_view(), name='payment-post'),
    
    # Voucher Reversal
    path('vouchers/<uuid:voucher_id>/reverse/', VoucherReversalView.as_view(), name='voucher-reverse'),
]
