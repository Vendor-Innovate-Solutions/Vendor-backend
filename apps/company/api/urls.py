"""
Company API URL Configuration
"""
from django.urls import path
from apps.company.api.views_financial_year import (
    FinancialYearCloseView,
    FinancialYearReopenView,
    FinancialYearListView
)
from apps.company.api.views_company import (
    CompanyListCreateView,
    CompanyDetailView,
    CurrencyListView
)
from apps.company.api.views_setup import (
    CompanyBusinessSettingsView,
    CompanyAddressListCreateView,
    CompanyAddressDetailView,
    CompanySetupStatusView,
    CompanyFeatureView
)
from apps.company.api.views_onboarding import (
    ManufacturerCompanyCreationView,
    CompanyInviteView,
    InviteAcceptView,
    ExternalUserProfileView
)
from apps.company.api.views_connection import (
    GenerateCompanyCodeView,
    JoinByCompanyCodeView,
    RetailerCompanyListView
)

urlpatterns = [
    # Onboarding APIs
    path('onboarding/create-company/', ManufacturerCompanyCreationView.as_view(), name='create-company'),
    
    # Company Connection APIs
    path('connection/generate-code/', GenerateCompanyCodeView.as_view(), name='generate-company-code'),
    
    # Company Management - PHASE 1
    path('', CompanyListCreateView.as_view(), name='company-list'),
    path('create/', CompanyListCreateView.as_view(), name='company-create'),
    path('<uuid:company_id>/', CompanyDetailView.as_view(), name='company-detail'),
    path('currencies/', CurrencyListView.as_view(), name='currency-list'),
    
    # Company Setup - PHASE 2: Business Settings
    path('<uuid:company_id>/business-settings/', CompanyBusinessSettingsView.as_view(), name='company-business-settings'),
    path('<uuid:company_id>/features/', CompanyFeatureView.as_view(), name='company-features'),
    
    # Company Setup - PHASE 3: Addresses
    path('<uuid:company_id>/addresses/', CompanyAddressListCreateView.as_view(), name='company-addresses'),
    path('<uuid:company_id>/addresses/<uuid:address_id>/', CompanyAddressDetailView.as_view(), name='company-address-detail'),
    
    # Setup Status
    path('<uuid:company_id>/setup-status/', CompanySetupStatusView.as_view(), name='company-setup-status'),
    
    # Company invites (external users)
    path('<uuid:company_id>/invite/', CompanyInviteView.as_view(), name='company-invite'),
    
    # Financial Year Management
    path('financial_year/', FinancialYearListView.as_view(), name='financial-year-list'),
    path('financial_year/<uuid:fy_id>/close/', FinancialYearCloseView.as_view(), name='financial-year-close'),
    path('financial_year/<uuid:fy_id>/reopen/', FinancialYearReopenView.as_view(), name='financial-year-reopen'),
]
