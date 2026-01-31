"""
Party API URL Configuration
"""
from django.urls import path
from apps.party.api.views import (
    PartyCreditStatusView,
    PartyCanOrderView,
    PartyListView
)

urlpatterns = [
    # Party listing - support both /party/ and /party/parties/
    path('', PartyListView.as_view(), name='party-list'),
    path('parties/', PartyListView.as_view(), name='party-parties-list'),
    
    # Credit control
    path('<uuid:party_id>/credit_status/', PartyCreditStatusView.as_view(), name='party-credit-status'),
    path('<uuid:party_id>/can_order/', PartyCanOrderView.as_view(), name='party-can-order'),
]
