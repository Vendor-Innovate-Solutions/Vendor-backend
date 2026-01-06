"""
System models for ERP audit and integration.
Models: AuditLog, IntegrationEvent, IdempotencyKey
"""
from django.db import models
from django.conf import settings
from core.models import BaseModel, CompanyScopedModel


class ActionType(models.TextChoices):
    """Enum for audit action types"""
    CREATE = 'CREATE', 'Created'
    UPDATE = 'UPDATE', 'Updated'
    DELETE = 'DELETE', 'Deleted'
    LOGIN = 'LOGIN', 'Login'
    LOGOUT = 'LOGOUT', 'Logout'
    EXPORT = 'EXPORT', 'Exported'
    IMPORT = 'IMPORT', 'Imported'
    APPROVE = 'APPROVE', 'Approved'
    REJECT = 'REJECT', 'Rejected'
    POST = 'POST', 'Posted'
    CANCEL = 'CANCEL', 'Cancelled'


class AuditLog(BaseModel):
    """
    Comprehensive audit trail.
    Tracks all critical actions in the system.
    """
    company = models.ForeignKey(
        "company.Company",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs'
    )
    
    # Actor (who performed the action)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs'
    )
    
    # Action details
    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices
    )
    
    # Target object (what was acted upon)
    object_type = models.CharField(
        max_length=100,
        help_text="Model name (e.g., 'Invoice', 'Voucher')"
    )
    object_id = models.UUIDField(
        help_text="UUID of the object"
    )
    object_repr = models.CharField(
        max_length=255,
        blank=True,
        help_text="String representation of object"
    )
    
    # Change tracking
    changes = models.JSONField(
        default=dict,
        help_text="JSON diff of changes (before/after)"
    )
    
    # Context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context data"
    )

    class Meta:
        verbose_name_plural = "Audit Logs"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['actor_user', 'created_at']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['action_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.action_type} - {self.object_type} {self.object_id} by {self.actor_user}"


class IntegrationStatus(models.TextChoices):
    """Enum for integration event status"""
    PENDING = 'PENDING', 'Pending'
    PROCESSING = 'PROCESSING', 'Processing'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'
    RETRY = 'RETRY', 'Retry Scheduled'


class IntegrationEvent(CompanyScopedModel):
    """
    Outbound integration event queue.
    Tracks events to be sent to external systems.
    Supports retry mechanism for failed events.
    """
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Type of event (e.g., 'invoice.created', 'order.updated')"
    )
    
    # Event data
    payload = models.JSONField(
        help_text="Event payload to send to external system"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=IntegrationStatus.choices,
        default=IntegrationStatus.PENDING
    )
    
    # Retry mechanism
    attempts = models.PositiveIntegerField(
        default=0,
        help_text="Number of processing attempts"
    )
    max_attempts = models.PositiveIntegerField(
        default=3,
        help_text="Maximum retry attempts before marking as failed"
    )
    
    last_attempt_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last processing attempt"
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled time for next retry"
    )
    
    # Result tracking
    response = models.JSONField(
        null=True,
        blank=True,
        help_text="Response from external system"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    
    # Metadata
    source_object_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source model that triggered this event"
    )
    source_object_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID of source object"
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when successfully processed"
    )

    class Meta:
        verbose_name_plural = "Integration Events"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', 'next_retry_at']),
            models.Index(fields=['company', 'event_type']),
            models.Index(fields=['status', 'next_retry_at']),
            models.Index(fields=['source_object_type', 'source_object_id']),
            models.Index(fields=['company', 'created_at']),
            models.Index(fields=['company', 'source_object_id']),  # For retry workers
        ]

    def __str__(self):
        return f"{self.event_type} - {self.status} (attempts: {self.attempts}/{self.max_attempts})"


class IdempotencyKey(BaseModel):
    """
    Tracks idempotency keys for API operations.
    
    Prevents duplicate posting from retries/webhooks.
    Critical for:
    - API retries
    - Webhook deliveries
    - External integrations
    
    Usage:
        Before posting, check if key exists.
        If exists, return existing voucher.
        If not, create key record inside transaction.
    """
    key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Unique idempotency key from client"
    )
    voucher = models.OneToOneField(
        'voucher.Voucher',
        on_delete=models.PROTECT,
        related_name='idempotency_record',
        help_text="Voucher created for this key"
    )
    company = models.ForeignKey(
        'company.Company',
        on_delete=models.PROTECT,
        related_name='idempotency_keys'
    )
    
    class Meta:
        verbose_name_plural = "Idempotency Keys"
        indexes = [
            models.Index(fields=['company', 'key']),
            models.Index(fields=['company', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.key} → {self.voucher.voucher_number}"
