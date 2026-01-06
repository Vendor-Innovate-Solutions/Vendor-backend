"""
Order signals.
Handles stock reservations and releases based on order status changes.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import SalesOrder
from apps.orders.services.reservations import (
    reserve_sales_order_stock,
    release_sales_order_stock
)


@receiver(post_save, sender=SalesOrder)
def sales_order_status_handler(sender, instance, created, **kwargs):
    """
    Handle sales order status changes.
    
    - When confirmed: Reserve stock
    - When cancelled: Release reservations
    
    Note: The service layer also handles this, so these signals act as
    a backup guard layer or can be disabled to avoid double action.
    """
    if created:
        # Don't do anything on creation
        return
    
    # Check if status was updated
    if not kwargs.get('update_fields') or 'status' not in kwargs.get('update_fields', []):
        # For safety, also check current status
        pass
    
    # Reserve stock on confirmation
    if instance.status == 'CONFIRMED':
        try:
            reserve_sales_order_stock(instance)
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error reserving stock for order {instance.order_number}: {e}")
    
    # Release stock on cancellation
    if instance.status == 'CANCELLED':
        try:
            release_sales_order_stock(instance)
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error releasing stock for order {instance.order_number}: {e}")


# Note: Purchase orders don't need stock reservations
# Stock IN happens when goods are received (via receipt/invoice)
