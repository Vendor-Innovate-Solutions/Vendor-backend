"""
Accounting API URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounting.api.views import (
    LedgerViewSet, AccountGroupViewSet, FinancialYearViewSet,
    TrialBalanceView, ProfitLossView, BalanceSheetView
)

# Create router for ViewSets
router = DefaultRouter()
router.register('ledgers', LedgerViewSet, basename='ledgers')
router.register('groups', AccountGroupViewSet, basename='account-groups')
router.register('financial-years', FinancialYearViewSet, basename='financial-years')

# Financial reports URLs
reports_urlpatterns = [
    path('trial-balance/', TrialBalanceView.as_view(), name='trial-balance'),
    path('pl/', ProfitLossView.as_view(), name='profit-loss'),
    path('bs/', BalanceSheetView.as_view(), name='balance-sheet'),
]

urlpatterns = [
    path('reports/', include(reports_urlpatterns)),
]

# Add router URLs
urlpatterns += router.urls
