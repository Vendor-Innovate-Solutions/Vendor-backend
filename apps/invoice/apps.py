from django.apps import AppConfig


class InvoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.invoice'
    
    def ready(self):
        """Import signals when app is ready."""
        import apps.invoice.signals
