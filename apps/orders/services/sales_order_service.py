"""
Sales Order Service - Aligned with ERP Architecture

Supports:
- RetailerUser & CompanyUser roles
- StockBalance cache instead of temporary reservation records
- Credit limit enforcement
- Price list rules
- Company access rules (retailer approval)
- Multi-company isolation
- Idempotent, concurrency-safe operations
- Audit trail compliance
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.models import SalesOrder, OrderItem
from apps.inventory.models import StockItem, StockBalance, PriceList, ItemPrice
from apps.party.models import Party
from apps.accounting.models import LedgerBalance
from apps.company.models import Sequence, Company
from apps.portal.models import RetailerCompanyAccess
from core.services.posting import AlreadyPosted


# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def _next_sequence_number(company: Company, key: str = "sales_order") -> str:
    """
    Generate next sequence number for sales orders.
    
    Uses ERP-wide sequencing with company isolation and row-level locking.
    
    Args:
        company: Company instance
        key: Sequence key (default: "sales_order")
        
    Returns:
        Formatted order number (e.g., "SO-000001")
    """
    # Get or create sequence
    seq, created = Sequence.objects.select_for_update().get_or_create(
        company=company,
        key=key,
        defaults={
            'last_value': 0,
            'prefix': 'SO'
        }
    )
    
    # Increment and save
    seq.last_value += 1
    seq.save(update_fields=['last_value', 'updated_at'])
    
    # Format with padding
    return f"{seq.prefix}-{seq.last_value:06d}"


def _get_item_price(
    item: StockItem,
    currency,
    price_list: Optional[PriceList] = None
) -> Decimal:
    """
    Resolve item price from price list.
    
    Always checks price list first. Raises error if no price found.
    
    Args:
        item: StockItem instance
        currency: Currency instance
        price_list: Optional PriceList instance
        
    Returns:
        Item rate as Decimal
        
    Raises:
        ValidationError: If no price found
    """
    # Build query
    qs = ItemPrice.objects.filter(item=item)
    
    if price_list:
        qs = qs.filter(price_list=price_list)
    
    # Get most recent valid price
    today = timezone.now().date()
    qs = qs.filter(valid_from__lte=today)
    qs = qs.filter(
        models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=today)
    )
    
    price = qs.order_by('-valid_from', '-created_at').first()
    
    if not price:
        raise ValidationError(
            f"No price found for item '{item.name}' "
            f"in price list '{price_list.name if price_list else 'default'}'"
        )
    
    return price.rate


def _check_company_access(company: Company, party: Party) -> None:
    """
    Validate retailer has approved access to place orders with company.
    
    Internal users (employees) are always allowed.
    Retailer users must have APPROVED status.
    
    Args:
        company: Company instance
        party: Party instance
        
    Raises:
        ValidationError: If access not approved
    """
    # Skip check for internal parties
    if party.party_type == 'EMPLOYEE':
        return
    
    # For retailer parties, check approval
    if party.is_retailer:
        # Check if retailer user has approved access
        from apps.party.models import RetailerUser
        
        retailer_user = RetailerUser.objects.filter(
            party=party,
            company=company
        ).first()
        if not retailer_user:
            raise ValidationError(
                f"Party '{party.name}' is not registered as a retailer"
            )
        
        access = RetailerCompanyAccess.objects.filter(
            retailer=retailer_user,
            company=company,
            status='APPROVED'
        ).exists()
        
        if not access:
            raise ValidationError(
                f"Party '{party.name}' is not approved to place orders "
                f"with company '{company.name}'"
            )


def _check_credit_limit(
    company: Company,
    customer_party: Party,
    order_total: Decimal
) -> None:
    """
    Validate customer has not exceeded credit limit.
    
    PHASE 5 UPDATE: Now uses invoice outstanding instead of ledger balance.
    This is more accurate as it only considers unpaid invoices.
    
    Args:
        company: Company instance
        customer_party: Party instance
        order_total: Order amount as Decimal
        
    Raises:
        ValidationError: If credit limit exceeded
    """
    if not customer_party.credit_limit:
        return  # No credit limit set
    
    # PHASE 5: Use new credit service for accurate outstanding calculation
    from apps.party.services.credit import get_outstanding_for_party, check_credit_limit
    
    try:
        check_credit_limit(customer_party, order_total)
    except ValidationError:
        # Re-raise with additional context
        outstanding = get_outstanding_for_party(customer_party)
        raise ValidationError(
            f"Credit limit exceeded. "
            f"Limit: ₹{customer_party.credit_limit}, "
            f"Outstanding: ₹{outstanding}, "
            f"New Order: ₹{order_total}, "
            f"Total Exposure: ₹{outstanding + order_total}"
        )


def _check_stock_availability(
    company: Company,
    item: StockItem,
    required_qty: Decimal
) -> None:
    """
    Validate sufficient stock available.
    
    For portal products, checks Product.available_quantity field directly.
    Falls back to StockBalance aggregation for non-portal items.
    
    Args:
        company: Company instance
        item: StockItem instance
        required_qty: Required quantity as Decimal
        
    Raises:
        ValidationError: If insufficient stock
    """
    from django.db.models import Sum
    
    # Check if item has an associated product (portal item)
    if hasattr(item, 'product') and item.product:
        # Use product's available_quantity field (portal display value)
        total_stock = Decimal(str(item.product.available_quantity))
    else:
        # Aggregate stock across all godowns for this item from StockBalance
        total_stock = StockBalance.objects.filter(
            company=company,
            item=item
        ).aggregate(
            total=Sum('quantity_on_hand')
        )['total'] or Decimal('0')
    
    if total_stock < required_qty:
        raise ValidationError(
            f"Insufficient stock for item '{item.name}'. "
            f"Required: {required_qty}, Available: {total_stock}"
        )


# ========================================================================
# SALES ORDER SERVICE
# ========================================================================

class SalesOrderService:
    """
    Sales Order Service - handles order creation, modification, and lifecycle.
    
    Features:
    - Multi-company isolated
    - Retailer approval checks
    - Credit limit enforcement
    - Stock availability validation
    - Price list resolution
    - Idempotent sequence generation
    - Concurrency-safe with transactions
    """
    
    @staticmethod
    @transaction.atomic
    def create_order(
        company: Company,
        customer_party_id: int,
        currency_id: int,
        price_list_id: Optional[int] = None,
        created_by=None,
        order_date=None
    ) -> SalesOrder:
        """
        Create a new sales order in DRAFT status.
        
        Args:
            company: Company instance
            customer_party_id: Customer party ID
            currency_id: Currency ID
            price_list_id: Optional price list ID
            created_by: User creating the order
            order_date: Order date (defaults to today)
            
        Returns:
            Created SalesOrder instance
            
        Raises:
            ValidationError: If validation fails
            Party.DoesNotExist: If customer not found
        """
        # Get and validate customer
        customer = Party.objects.get(
            company=company,
            id=customer_party_id,
            is_active=True
        )
        
        # Validate customer is actually a customer
        if customer.party_type not in ['CUSTOMER', 'BOTH']:
            raise ValidationError(
                f"Party '{customer.name}' is not a customer"
            )
        
        # Check retailer approval if applicable
        _check_company_access(company, customer)
        
        # Generate order number
        order_number = _next_sequence_number(company, "sales_order")
        
        # Create order
        order = SalesOrder.objects.create(
            company=company,
            customer=customer,
            currency_id=currency_id,
            price_list_id=price_list_id,
            order_number=order_number,
            status='DRAFT',
            order_date=order_date or timezone.now().date(),
            created_by=created_by
        )
        
        return order
    
    @staticmethod
    @transaction.atomic
    def add_item(
        order: SalesOrder,
        item_id: int,
        quantity: Decimal,
        override_rate: Optional[Decimal] = None
    ) -> OrderItem:
        """
        Add item to sales order.
        
        Args:
            order: SalesOrder instance
            item_id: StockItem ID
            quantity: Quantity to order
            override_rate: Optional manual rate override
            
        Returns:
            Created OrderItem instance
            
        Raises:
            ValidationError: If order not in DRAFT or validation fails
            StockItem.DoesNotExist: If item not found
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Only DRAFT orders can be modified"
            )
        
        # Get and validate item
        item = StockItem.objects.get(
            company=order.company,
            id=item_id,
            is_active=True
        )
        
        # Resolve price
        if override_rate is not None:
            rate = override_rate
        else:
            rate = _get_item_price(item, order.currency, order.price_list)
        
        # Calculate next line number
        max_line = order.items.aggregate(
            models.Max('line_no')
        )['line_no__max'] or 0
        
        # Create order item
        order_item = OrderItem.objects.create(
            company=order.company,
            sales_order=order,
            item=item,
            line_no=max_line + 1,
            quantity=quantity,
            uom=item.uom,
            unit_rate=rate
        )
        
        return order_item
    
    @staticmethod
    @transaction.atomic
    def update_item(
        order: SalesOrder,
        item_line_id: int,
        quantity: Optional[Decimal] = None,
        override_rate: Optional[Decimal] = None
    ) -> OrderItem:
        """
        Update existing order item.
        
        Args:
            order: SalesOrder instance
            item_line_id: OrderItem ID to update
            quantity: New quantity (if provided)
            override_rate: New rate (if provided)
            
        Returns:
            Updated OrderItem instance
            
        Raises:
            ValidationError: If order not in DRAFT
            OrderItem.DoesNotExist: If item not found
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Only DRAFT orders can be modified"
            )
        
        # Get order item
        line = OrderItem.objects.get(
            id=item_line_id,
            sales_order=order
        )
        
        # Update fields
        update_fields = []
        
        if quantity is not None:
            line.quantity = quantity
            update_fields.append('quantity')
        
        if override_rate is not None:
            line.unit_rate = override_rate
            update_fields.append('unit_rate')
        elif quantity is not None:
            # Re-fetch price if quantity changed but no override
            rate = _get_item_price(line.item, order.currency, order.price_list)
            line.unit_rate = rate
            update_fields.append('unit_rate')
        
        if update_fields:
            update_fields.append('updated_at')
            line.save(update_fields=update_fields)
        
        return line
    
    @staticmethod
    @transaction.atomic
    def remove_item(
        order: SalesOrder,
        item_line_id: int
    ) -> None:
        """
        Remove item from sales order.
        
        Args:
            order: SalesOrder instance
            item_line_id: OrderItem ID to remove
            
        Raises:
            ValidationError: If order not in DRAFT
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Only DRAFT orders can be modified"
            )
        
        OrderItem.objects.filter(
            id=item_line_id,
            sales_order=order
        ).delete()
    
    @staticmethod
    @transaction.atomic
    def confirm_order(
        order: SalesOrder,
        validate_stock: bool = True,
        enforce_credit: bool = True
    ) -> SalesOrder:
        """
        Confirm sales order - validates stock and credit.
        
        Args:
            order: SalesOrder instance
            validate_stock: Whether to check stock availability
            enforce_credit: Whether to enforce credit limits
            
        Returns:
            Updated SalesOrder instance
            
        Raises:
            ValidationError: If validation fails
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Order must be DRAFT to confirm"
            )
        
        # Check has items
        if not order.items.exists():
            raise ValidationError(
                "Order must contain at least one item"
            )
        
        # Validate stock availability
        if validate_stock:
            for line in order.items.all():
                _check_stock_availability(
                    order.company,
                    line.item,
                    line.quantity
                )
        
        # Validate credit limit
        if enforce_credit:
            # Calculate order total
            subtotal = sum(
                line.quantity * line.unit_rate
                for line in order.items.all()
            )
            
            _check_credit_limit(
                order.company,
                order.customer,
                subtotal
            )
        
        # Update status
        order.status = 'CONFIRMED'
        order.confirmed_at = timezone.now()
        order.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(
        order: SalesOrder,
        reason: str
    ) -> SalesOrder:
        """
        Cancel sales order.
        
        Args:
            order: SalesOrder instance
            reason: Cancellation reason
            
        Returns:
            Updated SalesOrder instance
            
        Raises:
            AlreadyPosted: If order already posted
        """
        if order.status == 'POSTED':
            raise AlreadyPosted(
                "Cannot cancel a posted order"
            )
        
        order.status = 'CANCELLED'
        order.cancellation_reason = reason
        order.cancelled_at = timezone.now()
        order.save(update_fields=[
            'status',
            'cancellation_reason',
            'cancelled_at',
            'updated_at'
        ])
        
        return order
    
    @staticmethod
    @transaction.atomic
    def mark_posted(order: SalesOrder) -> SalesOrder:
        """
        Mark order as posted (called by invoice posting service).
        
        Args:
            order: SalesOrder instance
            
        Returns:
            Updated SalesOrder instance
            
        Raises:
            ValidationError: If order not confirmed
        """
        if order.status != 'CONFIRMED':
            raise ValidationError(
                "Order must be CONFIRMED to post"
            )
        
        order.status = 'POSTED'
        order.posted_at = timezone.now()
        order.save(update_fields=['status', 'posted_at', 'updated_at'])
        
        return order
