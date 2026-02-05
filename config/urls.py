"""
URL configuration for Vendor ERP Backend.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from core.auth.views import (
    LoginView, RefreshView, LogoutView, SwitchCompanyView, MeView,
    LoginOTPRequestView, LoginOTPVerifyView
)


def redirect_view(request):
    """Simple root redirect."""
    return HttpResponse("Vendor ERP Backend API")


urlpatterns = [
    path('', redirect_view),
    path('admin/', admin.site.urls),
    
    # Authentication endpoints
    path('auth/login/', LoginView.as_view(), name='auth_login'),
    path('auth/refresh/', RefreshView.as_view(), name='auth_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('auth/switch-company/', SwitchCompanyView.as_view(), name='auth_switch_company'),
    path('auth/me/', MeView.as_view(), name='auth_me'),
    
    # OTP-based Login endpoints (2-Factor Authentication)
    path('auth/login/request-otp/', LoginOTPRequestView.as_view(), name='auth_login_request_otp'),
    path('auth/login/verify-otp/', LoginOTPVerifyView.as_view(), name='auth_login_verify_otp'),
    
    # App API endpoints
    path('api/', include('api.urls')),
]
