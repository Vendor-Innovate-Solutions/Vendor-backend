"""
GST Integration App Configuration
"""
from django.apps import AppConfig


class GstConfig(AppConfig):
    """Configuration for GST integration app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations.gst'
    label = 'gst'
    verbose_name = 'GST and E-Invoice Integration'
    
    def ready(self):
        """Import signals when app is ready."""
        import integrations.gst.signals  # noqa
