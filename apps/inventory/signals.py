"""
Signal handlers for inventory operations.
Auto-updates StockBalance when StockMovement is created.
"""
from decimal import Decimal
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import StockMovement, StockBalance


@receiver(post_save, sender=StockMovement)
def update_stock_balance(sender, instance, created, **kwargs):
    """
    Update StockBalance after a StockMovement is created.
    
    This signal ensures that stock balances are automatically
    maintained when movements occur.
    
    Rules:
    - IN movements increase stock
    - OUT movements decrease stock
    - Balances are tracked per company, item, godown, and batch
    
    Args:
        sender: StockMovement model class
        instance: The StockMovement instance
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    if not created:
        # Only process new movements
        return
    
    # Determine which godown to update based on movement type
    if instance.movement_type == 'IN':
        target_godown = instance.to_godown
    elif instance.movement_type == 'OUT':
        target_godown = instance.from_godown
    else:
        # Unknown movement type, skip
        return
    
    if not target_godown:
        # No godown specified, skip
        return
    
    # Get or create stock balance
    balance, _ = StockBalance.objects.get_or_create(
        company=instance.company,
        item=instance.item,
        godown=target_godown,
        batch=instance.batch or '',
        defaults={
            'quantity': Decimal('0')
        }
    )
    
    # Calculate quantity change based on movement type
    qty_change = instance.quantity
    if instance.movement_type == 'OUT':
        qty_change = -qty_change
    
    # Update balance
    balance.quantity += qty_change
    balance.save(update_fields=['quantity', 'updated_at'])


@receiver(post_save, sender=StockMovement)
def log_stock_movement(sender, instance, created, **kwargs):
    """
    Optional: Log stock movements for audit trail.
    
    This is a placeholder for future implementation of:
    - Audit logging
    - Notifications
    - Analytics tracking
    - Cache invalidation
    
    Args:
        sender: StockMovement model class
        instance: The StockMovement instance
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments
    """
    if not created:
        return
    
    # TODO: Implement audit logging
    # Example pseudo-code:
    # from apps.system.models import AuditLog
    # AuditLog.objects.create(
    #     company=instance.company,
    #     model='StockMovement',
    #     object_id=instance.id,
    #     action='CREATE',
    #     changes={
    #         'item': instance.item.name,
    #         'type': instance.movement_type,
    #         'quantity': str(instance.quantity),
    #         'godown': instance.to_godown.name if instance.to_godown else instance.from_godown.name
    #     }
    # )
    
    # TODO: Send notifications for critical stock levels
    # if instance.movement_type == 'OUT':
    #     check_reorder_level(instance.item, instance.from_godown)
    
    pass


# Additional signal ideas for future implementation:

# @receiver(post_save, sender=StockItem)
# def initialize_stock_balance(sender, instance, created, **kwargs):
#     """Initialize stock balance when item is created with opening stock."""
#     if created and instance.opening_stock > 0:
#         # Create initial balance entry
#         pass

# @receiver(pre_delete, sender=StockMovement)
# def prevent_movement_deletion(sender, instance, **kwargs):
#     """Prevent deletion of stock movements for audit integrity."""
#     raise ValidationError("Stock movements cannot be deleted. Use reversals instead.")
