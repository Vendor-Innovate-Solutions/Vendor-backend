"""
Invoice signals.
Handles invoice state updates and integrations with orders and payments.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal

from apps.invoice.models import Invoice


@receiver(post_save, sender=Invoice)
def update_order_invoice_status(sender, instance, created, **kwargs):
    """
    Update sales/purchase order status when invoice is posted.
    
    When invoice status changes to POSTED:
    - Mark the related order as INVOICED or PARTIAL_INVOICED
    """
    if created:
        # Don't process on creation
        return
    
    # Check if status was updated to POSTED
    if instance.status == 'POSTED':
        # Update sales order if exists
        if instance.sales_order:
            try:
                from apps.orders.services.sales_order_service import SalesOrderService
                # Mark order as invoiced or partially invoiced
                if hasattr(SalesOrderService, 'mark_posted'):
                    SalesOrderService.mark_posted(instance.sales_order)
                else:
                    # Fallback: update status directly
                    if instance.sales_order.status == 'CONFIRMED':
                        instance.sales_order.status = 'INVOICED'
                        instance.sales_order.invoiced_at = instance.updated_at
                        instance.sales_order.save(update_fields=['status', 'invoiced_at'])
            except Exception as e:
                # Log error but don't fail the save
                print(f"Error updating sales order status: {e}")
        
        # Update purchase order if exists
        if instance.purchase_order:
            try:
                # Update purchase order status
                if instance.purchase_order.status == 'CONFIRMED':
                    instance.purchase_order.status = 'INVOICED'
                    instance.purchase_order.save(update_fields=['status'])
            except Exception as e:
                # Log error but don't fail the save
                print(f"Error updating purchase order status: {e}")
