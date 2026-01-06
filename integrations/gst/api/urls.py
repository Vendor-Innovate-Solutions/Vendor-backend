"""
GST API URL Configuration
"""
from django.urls import path
from integrations.gst.api.views import (
    GSTR1GenerateView,
    GSTR3BGenerateView,
    GSTReturnPeriodView,
    GSTReturnListView
)

urlpatterns = [
    # Generate GST returns
    path('gstr1/generate/', GSTR1GenerateView.as_view(), name='gstr1-generate'),
    path('gstr3b/generate/', GSTR3BGenerateView.as_view(), name='gstr3b-generate'),
    
    # Retrieve GST returns
    path('returns/', GSTReturnListView.as_view(), name='gst-returns-list'),
    path('returns/<str:period>/', GSTReturnPeriodView.as_view(), name='gst-returns-period'),
]
