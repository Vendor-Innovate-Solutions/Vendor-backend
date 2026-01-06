"""
Stock transfer service - handles inter-godown stock movements.
Ensures atomicity and data consistency for stock transfers.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.inventory.services.guards import (
    ensure_stock_available,
    validate_transfer_params
)
from apps.inventory.models import StockMovement, StockItem, Godown


class StockTransferService:
    """Service for handling stock transfers between godowns."""
    
    @staticmethod
    @transaction.atomic
    def transfer(company, item_id, from_godown_id, to_godown_id, qty, reason="", rate=None, batch=None):
        """
        Transfer stock from one godown to another.
        
        Creates two StockMovement records:
        1. OUT movement from source godown
        2. IN movement to destination godown
        
        Args:
            company: Company instance
            item_id: StockItem ID
            from_godown_id: Source Godown ID
            to_godown_id: Destination Godown ID
            qty: Transfer quantity (Decimal)
            reason: Transfer reason/notes (optional)
            rate: Valuation rate (optional, uses item's opening_rate if not provided)
            batch: Batch number (optional)
        
        Returns:
            tuple: (out_movement, in_movement) - The created StockMovement instances
        
        Raises:
            ValidationError: If validation fails
            NegativeStockError: If insufficient stock
        """
        # Validate parameters
        item, from_godown, to_godown, qty = validate_transfer_params(
            company, item_id, from_godown_id, to_godown_id, qty
        )
        
        qty = Decimal(str(qty))
        
        # Check stock availability (negative stock guard)
        ensure_stock_available(company, item, qty, from_godown)
        
        # Use item's opening rate if rate not provided
        if rate is None:
            rate = item.opening_rate or Decimal('0')
        else:
            rate = Decimal(str(rate))
        
        transfer_date = timezone.now().date()
        
        # Create OUT movement
        out_movement = StockMovement.objects.create(
            company=company,
            item=item,
            quantity=qty,
            movement_type='OUT',
            from_godown=from_godown,
            to_godown=to_godown,
            rate=rate,
            reason=f"Transfer OUT to {to_godown.name} → {reason}".strip(),
            date=transfer_date,
            batch=batch
        )
        
        # Create IN movement
        in_movement = StockMovement.objects.create(
            company=company,
            item=item,
            quantity=qty,
            movement_type='IN',
            from_godown=from_godown,
            to_godown=to_godown,
            rate=rate,
            reason=f"Transfer IN from {from_godown.name} → {reason}".strip(),
            date=transfer_date,
            batch=batch
        )
        
        return out_movement, in_movement
    
    @staticmethod
    @transaction.atomic
    def create_movement(company, item_id, godown_id, quantity, movement_type, 
                       rate=None, reason="", batch=None, reference_type=None, reference_id=None):
        """
        Create a single stock movement (IN or OUT).
        
        Args:
            company: Company instance
            item_id: StockItem ID
            godown_id: Godown ID
            quantity: Movement quantity
            movement_type: 'IN' or 'OUT'
            rate: Valuation rate (optional)
            reason: Movement reason (optional)
            batch: Batch number (optional)
            reference_type: Reference document type (optional, e.g., 'PURCHASE_ORDER')
            reference_id: Reference document ID (optional)
        
        Returns:
            StockMovement instance
        
        Raises:
            ValidationError: If validation fails
            NegativeStockError: If OUT movement with insufficient stock
        """
        from apps.inventory.services.guards import validate_movement_data
        
        # Get item and godown
        try:
            item = StockItem.objects.get(company=company, id=item_id)
        except StockItem.DoesNotExist:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Stock item {item_id} not found")
        
        try:
            godown = Godown.objects.get(company=company, id=godown_id)
        except Godown.DoesNotExist:
            from django.core.exceptions import ValidationError
            raise ValidationError(f"Godown {godown_id} not found")
        
        quantity = Decimal(str(quantity))
        
        # Validate movement data
        validate_movement_data(company, item, quantity, movement_type, godown)
        
        # For OUT movements, check stock availability
        if movement_type == 'OUT':
            ensure_stock_available(company, item, quantity, godown)
        
        # Use item's opening rate if not provided
        if rate is None:
            rate = item.opening_rate or Decimal('0')
        else:
            rate = Decimal(str(rate))
        
        # Determine from/to godown based on movement type
        from_godown = godown if movement_type == 'OUT' else None
        to_godown = godown if movement_type == 'IN' else None
        
        # Create movement
        movement = StockMovement.objects.create(
            company=company,
            item=item,
            quantity=quantity,
            movement_type=movement_type,
            from_godown=from_godown,
            to_godown=to_godown,
            rate=rate,
            reason=reason,
            date=timezone.now().date(),
            batch=batch,
            reference_type=reference_type,
            reference_id=reference_id
        )
        
        return movement
    
    @staticmethod
    def get_transfer_history(company, item=None, godown=None, start_date=None, end_date=None):
        """
        Get transfer history with filters.
        
        Args:
            company: Company instance
            item: StockItem instance (optional)
            godown: Godown instance (optional)
            start_date: Filter from date (optional)
            end_date: Filter to date (optional)
        
        Returns:
            QuerySet of StockMovement for transfers
        """
        from django.db.models import Q
        
        # Transfers have both from_godown and to_godown
        qs = StockMovement.objects.filter(
            company=company,
            from_godown__isnull=False,
            to_godown__isnull=False
        )
        
        if item:
            qs = qs.filter(item=item)
        
        if godown:
            qs = qs.filter(Q(from_godown=godown) | Q(to_godown=godown))
        
        if start_date:
            qs = qs.filter(date__gte=start_date)
        
        if end_date:
            qs = qs.filter(date__lte=end_date)
        
        return qs.select_related('item', 'from_godown', 'to_godown').order_by('-date', '-created_at')
