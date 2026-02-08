"""
Tally Import App Configuration
"""
from django.apps import AppConfig


class TallyImportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system.tally_import'
    label = 'tally_import'
    verbose_name = 'Tally Import'
