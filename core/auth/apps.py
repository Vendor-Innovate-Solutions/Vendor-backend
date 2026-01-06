from django.apps import AppConfig


class AuthConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.auth'
    label = 'core_auth'
    
    def ready(self):
        """Import signals when app is ready."""
        import core.auth.signals  # noqa: F401
