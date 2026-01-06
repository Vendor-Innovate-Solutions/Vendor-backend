"""
Workflow Admin
"""
from django.contrib import admin
from apps.workflow.models import Approval, ApprovalRule


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    """Admin for Approval model."""
    list_display = ['target_type', 'target_id', 'status', 'requested_by', 'approved_by', 'created_at']
    list_filter = ['status', 'target_type', 'company']
    search_fields = ['target_id', 'requested_by__username', 'approved_by__username']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ApprovalRule)
class ApprovalRuleAdmin(admin.ModelAdmin):
    """Admin for ApprovalRule model."""
    list_display = ['company', 'target_type', 'approval_required', 'threshold_amount']
    list_filter = ['approval_required', 'company']
