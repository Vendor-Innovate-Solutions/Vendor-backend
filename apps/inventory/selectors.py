"""
Inventory selectors - read-only data access layer.
Provides safe, company-scoped queries for stock items and balances.
"""
from apps.inventory.models import StockItem, StockBalance, StockMovement, StockReservation


def list_items(company, is_active=True):
    """
    Get all stock items for a company.
    
    Args:
        company: Company instance
        is_active: Filter by active status (default: True)
    
    Returns:
        QuerySet of StockItem
    """
    qs = StockItem.objects.filter(company=company)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs.select_related('company', 'product', 'uom')


def get_item(company, item_id):
    """
    Get a single stock item.
    
    Args:
        company: Company instance
        item_id: StockItem ID
    
    Returns:
        StockItem instance
    
    Raises:
        StockItem.DoesNotExist: If item not found or doesn't belong to company
    """
    return StockItem.objects.select_related('company', 'product', 'uom').get(
        company=company,
        id=item_id
    )


def current_stock(company, item, godown=None, batch=None):
    """
    Get current stock balance for an item.
    
    Args:
        company: Company instance
        item: StockItem instance
        godown: Godown instance (optional)
        batch: Batch number string (optional)
    
    Returns:
        StockBalance instance or None if no balance exists
    """
    qs = StockBalance.objects.filter(company=company, item=item)
    
    if godown:
        qs = qs.filter(godown=godown)
    if batch:
        qs = qs.filter(batch=batch)
    
    return qs.first()


def list_stock_balances(company, item=None, godown=None, min_quantity=None):
    """
    List all stock balances with optional filters.
    
    Args:
        company: Company instance
        item: StockItem instance (optional)
        godown: Godown instance (optional)
        min_quantity: Minimum quantity filter (optional)
    
    Returns:
        QuerySet of StockBalance
    """
    qs = StockBalance.objects.filter(company=company)
    
    if item:
        qs = qs.filter(item=item)
    if godown:
        qs = qs.filter(godown=godown)
    if min_quantity is not None:
        qs = qs.filter(quantity__gte=min_quantity)
    
    return qs.select_related('item', 'godown')


def list_stock_movements(company, item=None, godown=None, movement_type=None, start_date=None, end_date=None):
    """
    List stock movements with optional filters.
    
    Args:
        company: Company instance
        item: StockItem instance (optional)
        godown: Godown instance (optional)
        movement_type: 'IN' or 'OUT' (optional)
        start_date: Filter from date (optional)
        end_date: Filter to date (optional)
    
    Returns:
        QuerySet of StockMovement
    """
    qs = StockMovement.objects.filter(company=company)
    
    if item:
        qs = qs.filter(item=item)
    if godown:
        qs = qs.filter(from_godown=godown) | qs.filter(to_godown=godown)
    if movement_type:
        qs = qs.filter(movement_type=movement_type)
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    
    return qs.select_related('item', 'from_godown', 'to_godown').order_by('-date', '-created_at')


def list_reservations(company, item=None, status=None):
    """
    List stock reservations with optional filters.
    
    Args:
        company: Company instance
        item: StockItem instance (optional)
        status: Reservation status (optional)
    
    Returns:
        QuerySet of StockReservation
    """
    qs = StockReservation.objects.filter(company=company)
    
    if item:
        qs = qs.filter(item=item)
    if status:
        qs = qs.filter(status=status)
    
    return qs.select_related('item', 'godown').order_by('-created_at')


def get_item_stock_summary(company, item):
    """
    Get summary of stock across all godowns for an item.
    
    Args:
        company: Company instance
        item: StockItem instance
    
    Returns:
        dict with total quantity and breakdown by godown
    """
    balances = StockBalance.objects.filter(
        company=company,
        item=item
    ).select_related('godown')
    
    total = sum(b.quantity for b in balances)
    by_godown = [
        {
            'godown_id': b.godown_id,
            'godown_name': b.godown.name if b.godown else 'N/A',
            'quantity': b.quantity
        }
        for b in balances
    ]
    
    return {
        'item_id': item.id,
        'item_name': item.name,
        'total_quantity': total,
        'by_godown': by_godown
    }
