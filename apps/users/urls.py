"""
URL configuration for Users app.
"""
from django.urls import path
from apps.users.api import (
    UserRegistrationView,
    SendPhoneOTPView,
    VerifyPhoneOTPView,
    UserDetailView,
    RoleSelectionView,
    UserContextView
)

urlpatterns = [
    # Authentication
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('send-phone-otp/', SendPhoneOTPView.as_view(), name='send_phone_otp'),
    path('verify-phone-otp/', VerifyPhoneOTPView.as_view(), name='verify_phone_otp'),
    
    # User info
    path('me/', UserDetailView.as_view(), name='user_detail'),
    path('me/context/', UserContextView.as_view(), name='user_context'),
    
    # Onboarding
    path('select-role/', RoleSelectionView.as_view(), name='select_role'),
]
