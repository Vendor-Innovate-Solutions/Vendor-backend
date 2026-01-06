"""
Stock guards - validation and business rules enforcement.
Prevents negative stock and ensures data integrity.
"""
from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from apps.inventory.models import StockBalance


class NegativeStockError(ValidationError):
    """Raised when attempting to create negative stock."""
    pass


def ensure_stock_available(company, item, quantity, godown):
    """
    Validate that sufficient stock is available before OUT movement.
    
    Args:
        company: Company instance
        item: StockItem instance
        quantity: Decimal quantity to check
        godown: Godown instance
    
    Raises:
        NegativeStockError: If insufficient stock available
    """
    quantity = Decimal(str(quantity))
    
    bal = StockBalance.objects.filter(
        company=company,
        item=item,
        godown=godown
    ).first()
    
    current_qty = bal.quantity if bal else Decimal('0')
    
    if quantity > current_qty:
        raise NegativeStockError(
            f"Insufficient stock for {item.name} at {godown.name}: "
            f"available {current_qty}, required {quantity}"
        )


def ensure_reservation_available(company, item, quantity, godown):
    """
    Check if item can be reserved (enough unreserved stock).
    
    Args:
        company: Company instance
        item: StockItem instance
        quantity: Decimal quantity to reserve
        godown: Godown instance
    
    Raises:
        ValidationError: If insufficient unreserved stock
    """
    from apps.inventory.models import StockReservation
    
    quantity = Decimal(str(quantity))
    
    # Get current balance
    bal = StockBalance.objects.filter(
        company=company,
        item=item,
        godown=godown
    ).first()
    
    current_qty = bal.quantity if bal else Decimal('0')
    
    # Get active reservations
    reserved_qty = StockReservation.objects.filter(
        company=company,
        item=item,
        godown=godown,
        status='ACTIVE'
    ).aggregate(
        total=models.Sum('quantity')
    )['total'] or Decimal('0')
    
    available_qty = current_qty - reserved_qty
    
    if quantity > available_qty:
        raise ValidationError(
            f"Insufficient unreserved stock for {item.name} at {godown.name}: "
            f"available {available_qty} (total: {current_qty}, reserved: {reserved_qty}), "
            f"required {quantity}"
        )


def validate_transfer_params(company, item_id, from_godown_id, to_godown_id, quantity):
    """
    Validate stock transfer parameters.
    
    Args:
        company: Company instance
        item_id: StockItem ID
        from_godown_id: Source Godown ID
        to_godown_id: Destination Godown ID
        quantity: Transfer quantity
    
    Raises:
        ValidationError: If parameters are invalid
    """
    from apps.inventory.models import StockItem, Godown
    
    # Validate quantity
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValidationError("Transfer quantity must be positive")
    
    # Validate godowns are different
    if from_godown_id == to_godown_id:
        raise ValidationError("Source and destination godowns must be different")
    
    # Validate item exists
    try:
        item = StockItem.objects.get(company=company, id=item_id)
    except StockItem.DoesNotExist:
        raise ValidationError(f"Stock item {item_id} not found")
    
    # Validate godowns exist
    try:
        from_godown = Godown.objects.get(company=company, id=from_godown_id)
    except Godown.DoesNotExist:
        raise ValidationError(f"Source godown {from_godown_id} not found")
    
    try:
        to_godown = Godown.objects.get(company=company, id=to_godown_id)
    except Godown.DoesNotExist:
        raise ValidationError(f"Destination godown {to_godown_id} not found")
    
    # Check if godowns are active
    if not from_godown.is_active:
        raise ValidationError(f"Source godown {from_godown.name} is not active")
    
    if not to_godown.is_active:
        raise ValidationError(f"Destination godown {to_godown.name} is not active")
    
    return item, from_godown, to_godown, quantity


def validate_movement_data(company, item, quantity, movement_type, godown=None):
    """
    Validate stock movement data.
    
    Args:
        company: Company instance
        item: StockItem instance
        quantity: Movement quantity
        movement_type: 'IN' or 'OUT'
        godown: Godown instance (optional)
    
    Raises:
        ValidationError: If data is invalid
    """
    quantity = Decimal(str(quantity))
    
    if quantity <= 0:
        raise ValidationError("Movement quantity must be positive")
    
    if movement_type not in ['IN', 'OUT']:
        raise ValidationError("Movement type must be 'IN' or 'OUT'")
    
    if not item.is_active:
        raise ValidationError(f"Item {item.name} is not active")
    
    if godown and not godown.is_active:
        raise ValidationError(f"Godown {godown.name} is not active")
