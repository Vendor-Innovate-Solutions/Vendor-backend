"""
Company API URL Configuration
"""
from django.urls import path
from apps.company.api.views_financial_year import (
    FinancialYearCloseView,
    FinancialYearReopenView,
    FinancialYearListView
)
from apps.company.api.views_company import CompanyDiscoveryView

urlpatterns = [
    # Company Discovery (Public)
    path('discover/', CompanyDiscoveryView.as_view(), name='company-discover'),
    
    # Financial Year Management
    path('financial_year/', FinancialYearListView.as_view(), name='financial-year-list'),
    path('financial_year/<uuid:fy_id>/close/', FinancialYearCloseView.as_view(), name='financial-year-close'),
    path('financial_year/<uuid:fy_id>/reopen/', FinancialYearReopenView.as_view(), name='financial-year-reopen'),
]
