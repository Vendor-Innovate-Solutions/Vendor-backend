"""
Workflow App Configuration
"""
from django.apps import AppConfig


class WorkflowConfig(AppConfig):
    """Configuration for workflow app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.workflow'
    label = 'workflow'
    verbose_name = 'Workflow and Approval Management'
