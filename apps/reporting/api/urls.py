"""
Reporting API URLs.
"""

from django.urls import path
from apps.reporting.api.views import (
    AgingReportView,
    AgingSummaryView,
    OverduePartiesView
)

urlpatterns = [
    # Aging Reports
    path('aging/', AgingReportView.as_view(), name='aging_report'),
    path('aging/summary/', AgingSummaryView.as_view(), name='aging_summary'),
    path('overdue/', OverduePartiesView.as_view(), name='overdue_parties'),
]
