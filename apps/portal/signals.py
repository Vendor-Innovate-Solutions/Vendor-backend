"""
Portal signals.
Handles notifications and events for portal orders.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import SalesOrder
from apps.system.models import IntegrationEvent


@receiver(post_save, sender=SalesOrder)
def portal_order_notifications(sender, instance, created, **kwargs):
    """
    Send notifications for portal orders.
    
    When a retailer creates an order, emit integration event
    for external notifications (email, SMS, webhooks, etc.)
    """
    if not created:
        return
    
    # Check if order created by retailer
    if not instance.created_by:
        return
    
    is_retailer = False
    if hasattr(instance.created_by, 'retailer_mappings'):
        retailer_mapping = instance.created_by.retailer_mappings.filter(
            company=instance.company,
            status='APPROVED'
        ).first()
        is_retailer = retailer_mapping is not None
    
    if is_retailer:
        try:
            IntegrationEvent.objects.create(
                company=instance.company,
                event_type='portal.order.created',
                payload={
                    'order_id': str(instance.id),
                    'order_number': instance.order_number,
                    'customer_id': str(instance.customer_id),
                    'customer_name': instance.customer.name if instance.customer else '',
                    'total_amount': float(instance.total_amount) if hasattr(instance, 'total_amount') else 0,
                    'created_by': instance.created_by.email,
                    'created_at': instance.created_at.isoformat()
                },
                source_object_type='SalesOrder',
                source_object_id=instance.id,
                status='PENDING'
            )
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error creating integration event for portal order: {e}")
