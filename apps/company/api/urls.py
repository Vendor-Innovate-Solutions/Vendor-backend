"""
Company API URL Configuration
"""
from django.urls import path
from apps.company.api.views_financial_year import (
    FinancialYearCloseView,
    FinancialYearReopenView,
    FinancialYearListView
)

urlpatterns = [
    # Financial Year Management
    path('financial_year/', FinancialYearListView.as_view(), name='financial-year-list'),
    path('financial_year/<uuid:fy_id>/close/', FinancialYearCloseView.as_view(), name='financial-year-close'),
    path('financial_year/<uuid:fy_id>/reopen/', FinancialYearReopenView.as_view(), name='financial-year-reopen'),
]
