"""
URL patterns for Security API.
Provides endpoints for key exchange and secure data transfer.
"""
from django.urls import path
from core.security.api import (
    KeyExchangeInitiateView,
    KeyExchangeCompleteView,
    SecureDataSendView,
    SecureDataReceiveView,
    SecurePaymentDataView
)

urlpatterns = [
    # Key Exchange endpoints
    path('key-exchange/initiate/', KeyExchangeInitiateView.as_view(), name='key-exchange-initiate'),
    path('key-exchange/complete/', KeyExchangeCompleteView.as_view(), name='key-exchange-complete'),
    
    # Secure Data Transfer endpoints
    path('secure-data/send/', SecureDataSendView.as_view(), name='secure-data-send'),
    path('secure-data/receive/', SecureDataReceiveView.as_view(), name='secure-data-receive'),
    
    # Secure Payment endpoint
    path('secure-payment/', SecurePaymentDataView.as_view(), name='secure-payment'),
]
