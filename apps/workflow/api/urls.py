"""
Workflow API URL Configuration
"""
from django.urls import path
from apps.workflow.api.views import (
    AvailableEmployeesView,
    AssignOrderToEmployeeView,
    ApprovalRequestView,
    ApprovalApproveView,
    ApprovalRejectView,
    ApprovalListView,
    ApprovalStatusView
)

urlpatterns = [
    # Employee management
    path('employees/available/', AvailableEmployeesView.as_view(), name='available-employees'),
    path('orders/<uuid:order_id>/assign/', AssignOrderToEmployeeView.as_view(), name='assign-order-employee'),
    
    # Submit approval request
    path('request/', ApprovalRequestView.as_view(), name='approval-request'),
    
    # Approve/reject
    path('approve/<str:target_type>/<uuid:target_id>/', ApprovalApproveView.as_view(), name='approval-approve'),
    path('reject/<str:target_type>/<uuid:target_id>/', ApprovalRejectView.as_view(), name='approval-reject'),
    
    # List and status
    path('approvals/', ApprovalListView.as_view(), name='approval-list'),
    path('status/<str:target_type>/<uuid:target_id>/', ApprovalStatusView.as_view(), name='approval-status'),
]
