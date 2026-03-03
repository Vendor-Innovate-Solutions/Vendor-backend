"""
URL patterns for Stripe payment integration.
"""
from django.urls import path
from .views import StripeCreatePaymentIntentView, StripeConfirmPaymentView

urlpatterns = [
    path('stripe/create-payment-intent/', StripeCreatePaymentIntentView.as_view(), name='stripe_create_payment_intent'),
    path('stripe/confirm/', StripeConfirmPaymentView.as_view(), name='stripe_confirm_payment'),
]
