"""
Celery tasks for async processing.

This module handles:
1. Integration event processing (webhooks, Kafka, etc.)
2. Email notifications
3. Report generation
4. Background cleanup jobs

PHASE 5 - Event Bus Implementation:
- Process integration events with retry logic
- Exponential backoff: 30s, 60s, 120s, 300s, 600s
- Webhook HTTP POST delivery
- Kafka topic publishing (placeholder)

Usage:
    from apps.system.tasks import process_integration_event
    
    # Trigger async processing
    process_integration_event.delay(event_id)
"""

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import requests
import json
from typing import Optional, Dict, Any

logger = get_task_logger(__name__)


# ============================================================================
# INTEGRATION EVENT PROCESSING
# ============================================================================

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,  # Start with 30 seconds
    autoretry_for=(requests.exceptions.RequestException, ConnectionError, TimeoutError),
)
def process_integration_event(self, event_id: str) -> Dict[str, Any]:
    """
    Process an integration event with retry logic.
    
    This task:
    1. Fetches the IntegrationEvent record
    2. Determines delivery method (webhook, kafka, etc.)
    3. Attempts delivery
    4. Updates event status
    5. Retries on failure with exponential backoff
    
    Args:
        event_id: UUID of the IntegrationEvent
        
    Returns:
        Dict with status, delivery method, and response
        
    Raises:
        Retryable exceptions will trigger automatic retry
    """
    from apps.system.models import IntegrationEvent
    
    try:
        event = IntegrationEvent.objects.select_for_update().get(id=event_id)
    except IntegrationEvent.DoesNotExist:
        logger.error(f"IntegrationEvent {event_id} not found")
        return {"status": "error", "message": "Event not found"}
    
    logger.info(
        f"Processing event {event.id} - Type: {event.event_type}, "
        f"Attempt: {self.request.retries + 1}/5"
    )
    
    try:
        # Determine delivery method based on company configuration
        delivery_method = _get_delivery_method(event.company)
        
        if delivery_method == 'webhook':
            result = _deliver_via_webhook(event)
        elif delivery_method == 'kafka':
            result = _deliver_via_kafka(event)
        else:
            logger.warning(f"No delivery method configured for company {event.company.id}")
            result = {"status": "skipped", "reason": "No delivery method configured"}
        
        # Update event status
        with transaction.atomic():
            event.processed_at = timezone.now()
            event.retry_count = self.request.retries
            event.last_error = None
            event.save(update_fields=['processed_at', 'retry_count', 'last_error'])
        
        logger.info(f"Event {event.id} processed successfully via {delivery_method}")
        return result
        
    except Exception as e:
        # Log error and update event
        error_msg = str(e)
        logger.error(f"Error processing event {event.id}: {error_msg}")
        
        with transaction.atomic():
            event.retry_count = self.request.retries + 1
            event.last_error = error_msg
            event.save(update_fields=['retry_count', 'last_error'])
        
        # Calculate exponential backoff
        # Retries: 30s, 60s, 120s, 300s, 600s
        backoff_seconds = min(30 * (2 ** self.request.retries), 600)
        
        # Raise for retry
        raise self.retry(exc=e, countdown=backoff_seconds)


def _get_delivery_method(company) -> str:
    """
    Determine delivery method for company.
    
    In production, this would check company settings or configuration table.
    For now, returns 'webhook' as default.
    
    Args:
        company: Company instance
        
    Returns:
        'webhook', 'kafka', or 'none'
    """
    # TODO: Check company.integration_settings or CompanyFeature
    # For now, default to webhook
    return 'webhook'


def _deliver_via_webhook(event) -> Dict[str, Any]:
    """
    Deliver event via HTTP webhook.
    
    Args:
        event: IntegrationEvent instance
        
    Returns:
        Dict with status and response details
        
    Raises:
        requests.RequestException: On HTTP errors
    """
    from apps.company.models import CompanyFeature
    
    # Get webhook URL from company settings
    try:
        features = CompanyFeature.objects.get(company=event.company)
        webhook_url = getattr(features, 'webhook_url', None)
        
        if not webhook_url:
            logger.warning(f"No webhook URL configured for company {event.company.id}")
            return {"status": "skipped", "reason": "No webhook URL"}
    except CompanyFeature.DoesNotExist:
        logger.warning(f"No CompanyFeature found for {event.company.id}")
        return {"status": "skipped", "reason": "No company features"}
    
    # Prepare payload
    payload = {
        "event_id": str(event.id),
        "event_type": event.event_type,
        "created_at": event.created_at.isoformat(),
        "company_id": str(event.company.id),
        "data": event.payload
    }
    
    # Send POST request
    headers = {
        'Content-Type': 'application/json',
        'X-Event-Type': event.event_type,
        'X-Event-ID': str(event.id),
    }
    
    response = requests.post(
        webhook_url,
        json=payload,
        headers=headers,
        timeout=30
    )
    
    response.raise_for_status()  # Raise for 4xx/5xx errors
    
    return {
        "status": "delivered",
        "method": "webhook",
        "url": webhook_url,
        "status_code": response.status_code,
        "response": response.text[:500]  # First 500 chars
    }


def _deliver_via_kafka(event) -> Dict[str, Any]:
    """
    Deliver event via Kafka topic.
    
    PLACEHOLDER: Implement Kafka producer when needed.
    
    Args:
        event: IntegrationEvent instance
        
    Returns:
        Dict with status
    """
    logger.info(f"Kafka delivery not yet implemented for event {event.id}")
    
    # TODO: Implement Kafka producer
    # from kafka import KafkaProducer
    # producer = KafkaProducer(...)
    # producer.send(topic, key=..., value=...)
    
    return {
        "status": "not_implemented",
        "method": "kafka",
        "message": "Kafka integration coming soon"
    }


# ============================================================================
# AGING REPORT GENERATION (Scheduled Daily)
# ============================================================================

@shared_task
def generate_aging_reports() -> Dict[str, Any]:
    """
    Generate aging reports for all active companies.
    
    This task should run daily (via Celery Beat) to cache aging data.
    Reduces computation time for real-time API calls.
    
    Returns:
        Dict with count of companies processed and any errors
    """
    from apps.company.models import Company
    from apps.reporting.services.aging import generate_and_cache_aging
    
    companies = Company.objects.filter(is_active=True)
    success_count = 0
    error_count = 0
    errors = []
    
    for company in companies:
        try:
            logger.info(f"Generating aging report for company {company.id}")
            generate_and_cache_aging(company)
            success_count += 1
        except Exception as e:
            logger.error(f"Error generating aging for company {company.id}: {e}")
            error_count += 1
            errors.append({
                "company_id": str(company.id),
                "error": str(e)
            })
    
    result = {
        "total": companies.count(),
        "success": success_count,
        "errors": error_count,
        "error_details": errors
    }
    
    logger.info(f"Aging report generation complete: {result}")
    return result


# ============================================================================
# EMAIL NOTIFICATIONS
# ============================================================================

@shared_task
def send_overdue_reminders() -> Dict[str, Any]:
    """
    Send email reminders for overdue invoices.
    
    This task should run daily to remind customers about payment.
    
    Returns:
        Dict with count of emails sent
    """
    from apps.invoice.models import Invoice
    from apps.party.services.credit import get_overdue_amount
    from core.utils.email import send_email
    from datetime import timedelta
    
    logger.info("Starting overdue reminder task")
    
    # Get all posted invoices that are overdue
    overdue_invoices = Invoice.objects.filter(
        status__in=['POSTED', 'PARTIALLY_PAID'],
        due_date__lt=timezone.now().date()
    ).select_related('party', 'company')
    
    emails_sent = 0
    errors = []
    
    for invoice in overdue_invoices:
        try:
            # Calculate days overdue
            days_overdue = (timezone.now().date() - invoice.due_date).days
            
            # Send reminder at 7, 15, 30, 60, 90 days
            if days_overdue not in [7, 15, 30, 60, 90]:
                continue
            
            # Calculate outstanding
            outstanding = get_overdue_amount(invoice.party, invoice.company)
            
            # Send email
            context = {
                'invoice': invoice,
                'days_overdue': days_overdue,
                'outstanding': outstanding
            }
            
            send_email(
                to=invoice.party.email,
                subject=f"Payment Reminder: Invoice {invoice.invoice_number} Overdue",
                template='emails/overdue_reminder.html',
                context=context
            )
            
            emails_sent += 1
            logger.info(f"Sent reminder for invoice {invoice.id} to {invoice.party.email}")
            
        except Exception as e:
            logger.error(f"Error sending reminder for invoice {invoice.id}: {e}")
            errors.append({
                "invoice_id": str(invoice.id),
                "error": str(e)
            })
    
    result = {
        "emails_sent": emails_sent,
        "errors": len(errors),
        "error_details": errors
    }
    
    logger.info(f"Overdue reminder task complete: {result}")
    return result


# ============================================================================
# BACKGROUND CLEANUP
# ============================================================================

@shared_task
def cleanup_old_audit_logs(days: int = 365) -> Dict[str, int]:
    """
    Delete audit logs older than specified days.
    
    Keeps database size manageable while retaining recent audit trail.
    
    Args:
        days: Delete logs older than this many days (default: 365)
        
    Returns:
        Dict with count of deleted records
    """
    from apps.system.models import AuditLog
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    
    deleted_count, _ = AuditLog.objects.filter(
        timestamp__lt=cutoff_date
    ).delete()
    
    logger.info(f"Deleted {deleted_count} audit logs older than {days} days")
    
    return {
        "deleted": deleted_count,
        "cutoff_date": cutoff_date.isoformat()
    }
