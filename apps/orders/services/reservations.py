"""
Stock reservation service for orders.
Handles reservation and release of stock for sales orders using StockBalance.quantity_reserved.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.models import SalesOrder, OrderItem
from apps.inventory.models import StockBalance, Godown


@transaction.atomic
def reserve_sales_order_stock(order):
    """
    Reserve stock for all items in a sales order.
    Updates StockBalance.quantity_reserved field.
    
    Args:
        order: SalesOrder instance
    
    Returns:
        List of updated StockBalance instances
    """
    # Get all order items
    items = OrderItem.objects.filter(
        company=order.company,
        sales_order=order
    ).select_related('item')
    
    reservations = []
    
    # Get default godown for the company (or first available)
    default_godown = Godown.objects.filter(company=order.company, is_active=True).first()
    if not default_godown:
        raise ValidationError("No active godown found for stock reservation")
    
    for order_item in items:
        # Get or create stock balance for this item
        balance, created = StockBalance.objects.select_for_update().get_or_create(
            company=order.company,
            item=order_item.item,
            godown=default_godown,
            batch=None,  # No batch tracking for simple reservations
            defaults={
                'quantity_on_hand': Decimal('0'),
                'quantity_reserved': Decimal('0'),
                'quantity_allocated': Decimal('0')
            }
        )
        
        # Check if sufficient stock available
        available = balance.quantity_on_hand - balance.quantity_reserved - balance.quantity_allocated
        if available < order_item.quantity:
            raise ValidationError(
                f"Insufficient stock for {order_item.item.name}. "
                f"Available: {available}, Required: {order_item.quantity}"
            )
        
        # Reserve the stock
        balance.quantity_reserved += order_item.quantity
        balance.save(update_fields=['quantity_reserved', 'updated_at'])
        
        reservations.append(balance)
    
    return reservations


@transaction.atomic
def release_sales_order_stock(order):
    """
    Release all stock reservations for a sales order.
    Decreases StockBalance.quantity_reserved field.
    
    Args:
        order: SalesOrder instance
    
    Returns:
        Number of stock balances updated
    """
    # Get all order items
    items = OrderItem.objects.filter(
        company=order.company,
        sales_order=order
    ).select_related('item')
    
    count = 0
    
    # Get default godown
    default_godown = Godown.objects.filter(company=order.company, is_active=True).first()
    if not default_godown:
        return 0
    
    for order_item in items:
        # Get stock balance
        try:
            balance = StockBalance.objects.select_for_update().get(
                company=order.company,
                item=order_item.item,
                godown=default_godown,
                batch=None
            )
            
            # Release the reserved quantity
            balance.quantity_reserved = max(
                Decimal('0'),
                balance.quantity_reserved - order_item.quantity
            )
            balance.save(update_fields=['quantity_reserved', 'updated_at'])
            count += 1
            
        except StockBalance.DoesNotExist:
            # No balance to release from
            pass
    
    return count


def get_sales_order_reservations(order):
    """
    Get all stock balances with reservations for a sales order.
    
    Args:
        order: SalesOrder instance
    
    Returns:
        QuerySet of StockBalance with reserved quantities
    """
    # Get all order items
    items = OrderItem.objects.filter(
        company=order.company,
        sales_order=order
    ).values_list('item_id', flat=True)
    
    # Get balances for these items with reservations
    return StockBalance.objects.filter(
        company=order.company,
        item_id__in=items,
        quantity_reserved__gt=0
    ).select_related('item', 'godown')

