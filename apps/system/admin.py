from django.contrib import admin
from .models import AuditLog, IntegrationEvent, IdempotencyKey

admin.site.register(AuditLog)
admin.site.register(IntegrationEvent)
admin.site.register(IdempotencyKey)
