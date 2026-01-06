"""
Purchase Order Service - ERP-Aligned Procurement

Supports:
- Supplier/vendor purchase orders
- GRN (Goods Receipt Note) workflow
- Partial receipts (PARTIAL_RECEIVED status)
- No stock reservation (procurement side)
- Optional vendor approval workflow
- Multi-company isolation
- Idempotent sequence generation
- Transaction-safe operations
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.orders.models import PurchaseOrder, OrderItem
from apps.inventory.models import StockItem, PriceList, ItemPrice
from apps.party.models import Party
from apps.company.models import Sequence, Company
from apps.portal.models import RetailerCompanyAccess
from core.services.posting import AlreadyPosted


# ========================================================================
# HELPER FUNCTIONS
# ========================================================================

def _next_po_number(company: Company) -> str:
    """
    Generate next purchase order number with company isolation.
    
    Args:
        company: Company instance
        
    Returns:
        Formatted PO number (e.g., "PO-000001")
    """
    # Get or create sequence
    seq, created = Sequence.objects.select_for_update().get_or_create(
        company=company,
        key="purchase_order",
        defaults={
            'last_value': 0,
            'prefix': 'PO'
        }
    )
    
    # Increment and save
    seq.last_value += 1
    seq.save(update_fields=['last_value', 'updated_at'])
    
    # Format number with padding
    return f"{seq.prefix}-{seq.last_value:06d}"


def _get_cost_price(
    item: StockItem,
    currency,
    price_list: Optional[PriceList] = None
) -> Decimal:
    """
    Resolve procurement/cost price for item.
    
    Procurement pricing logic:
    1. Contract/negotiated price list (vendor specific)
    2. Latest cost price
    
    Args:
        item: StockItem instance
        currency: Currency instance
        price_list: Optional PriceList instance
        
    Returns:
        Cost rate as Decimal
        
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
            f"No procurement price defined for '{item.name}'"
        )
    
    return price.rate


def _check_vendor_access(company: Company, vendor_party: Party) -> None:
    """
    Optional vendor approval validation.
    
    Mirrors retailer/company access logic on sales side.
    - CompanyUser always allowed
    - Vendor must be approved to sell to this company (optional rule)
    
    This aligns with manufacturer-distributor marketplace workflows.
    Disable if not needed by commenting out the validation.
    
    Args:
        company: Company instance
        vendor_party: Party instance
        
    Raises:
        ValidationError: If vendor not approved (when enabled)
    """
    # If vendor is internal user party → always allowed
    if vendor_party.party_type == 'EMPLOYEE':
        return
    
    # Optional: enforce vendor approval workflow
    # This aligns with manufacturer-distributor marketplace workflows
    # Disable if not needed by commenting the check below
    
    # Uncomment to enable vendor approval requirement:
    # access_exists = RetailerCompanyAccess.objects.filter(
    #     retailer__party=vendor_party,
    #     company=company,
    #     status='APPROVED'
    # ).exists()
    # 
    # if not access_exists:
    #     raise ValidationError(
    #         f"Vendor '{vendor_party.name}' is not approved for procurement "
    #         f"with company '{company.name}'"
    #     )
    
    # Default: allow without approval
    pass


# ========================================================================
# PURCHASE ORDER SERVICE
# ========================================================================

class PurchaseOrderService:
    """
    Purchase Order Service - handles procurement order lifecycle.
    
    Features:
    - Multi-company isolated
    - Optional vendor approval
    - GRN workflow support (PARTIAL_RECEIVED status)
    - No stock reservation (procurement doesn't check stock)
    - Price list resolution for costs
    - Idempotent sequence generation
    - Concurrency-safe with transactions
    
    Flow:
    DRAFT → CONFIRMED → GRN creates StockMovement(IN) → 
    PARTIAL_RECEIVED (optional) → POSTED
    """
    
    @staticmethod
    @transaction.atomic
    def create_order(
        company: Company,
        supplier_party_id: int,
        currency_id: int,
        price_list_id: Optional[int] = None,
        created_by=None,
        order_date=None,
        expected_date=None
    ) -> PurchaseOrder:
        """
        Create new purchase order in DRAFT status.
        
        Args:
            company: Company instance
            supplier_party_id: Supplier party ID
            currency_id: Currency ID
            price_list_id: Optional price list ID
            created_by: User creating the order
            order_date: Order date (defaults to today)
            expected_date: Expected delivery date
            
        Returns:
            Created PurchaseOrder instance
            
        Raises:
            ValidationError: If validation fails
            Party.DoesNotExist: If supplier not found
        """
        # Get and validate supplier
        supplier = Party.objects.get(
            company=company,
            id=supplier_party_id,
            is_active=True
        )
        
        # Validate supplier is actually a supplier
        if supplier.party_type not in ['SUPPLIER', 'BOTH']:
            raise ValidationError(
                f"Party '{supplier.name}' is not a supplier"
            )
        
        # Check vendor approval if enabled
        _check_vendor_access(company, supplier)
        
        # Generate PO number
        po_number = _next_po_number(company)
        
        # Create order
        order = PurchaseOrder.objects.create(
            company=company,
            supplier=supplier,
            currency_id=currency_id,
            price_list_id=price_list_id,
            order_number=po_number,
            status='DRAFT',
            order_date=order_date or timezone.now().date(),
            expected_date=expected_date,
            created_by=created_by
        )
        
        return order
    
    @staticmethod
    @transaction.atomic
    def add_item(
        order: PurchaseOrder,
        item_id: int,
        quantity: Decimal,
        override_rate: Optional[Decimal] = None
    ) -> OrderItem:
        """
        Add item to purchase order.
        
        Args:
            order: PurchaseOrder instance
            item_id: StockItem ID
            quantity: Quantity to order
            override_rate: Optional manual rate override
            
        Returns:
            Created OrderItem instance
            
        Raises:
            ValidationError: If order not in DRAFT
            StockItem.DoesNotExist: If item not found
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Only DRAFT purchase orders can be modified"
            )
        
        # Get and validate item
        item = StockItem.objects.get(
            company=order.company,
            id=item_id,
            is_active=True
        )
        
        # Resolve cost price
        if override_rate is not None:
            rate = override_rate
        else:
            rate = _get_cost_price(item, order.currency, order.price_list)
        
        # Calculate next line number
        max_line = order.items.aggregate(
            models.Max('line_no')
        )['line_no__max'] or 0
        
        # Create order item
        order_item = OrderItem.objects.create(
            company=order.company,
            purchase_order=order,
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
        order: PurchaseOrder,
        item_line_id: int,
        quantity: Optional[Decimal] = None,
        override_rate: Optional[Decimal] = None
    ) -> OrderItem:
        """
        Update existing purchase order item.
        
        Args:
            order: PurchaseOrder instance
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
                "Only DRAFT purchase orders can be modified"
            )
        
        # Get order item
        line = OrderItem.objects.get(
            id=item_line_id,
            purchase_order=order
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
            rate = _get_cost_price(line.item, order.currency, order.price_list)
            line.unit_rate = rate
            update_fields.append('unit_rate')
        
        if update_fields:
            update_fields.append('updated_at')
            line.save(update_fields=update_fields)
        
        return line
    
    @staticmethod
    @transaction.atomic
    def remove_item(
        order: PurchaseOrder,
        item_line_id: int
    ) -> None:
        """
        Remove item from purchase order.
        
        Args:
            order: PurchaseOrder instance
            item_line_id: OrderItem ID to remove
            
        Raises:
            ValidationError: If order not in DRAFT
        """
        if order.status != 'DRAFT':
            raise ValidationError(
                "Only DRAFT purchase orders can be modified"
            )
        
        OrderItem.objects.filter(
            id=item_line_id,
            purchase_order=order
        ).delete()
    
    @staticmethod
    @transaction.atomic
    def confirm_order(order: PurchaseOrder) -> PurchaseOrder:
        """
        Confirm purchase order.
        
        CONFIRMED status means:
        - PO approved internally
        - Vendor PO can be sent
        - Ready for GRN → StockMovement(IN)
        - Cannot change lines
        
        Args:
            order: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
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
                "Purchase order must contain at least one item"
            )
        
        # Update status
        order.status = 'CONFIRMED'
        order.confirmed_at = timezone.now()
        order.save(update_fields=['status', 'confirmed_at', 'updated_at'])
        
        return order
    
    @staticmethod
    @transaction.atomic
    def mark_partial_received(order: PurchaseOrder) -> PurchaseOrder:
        """
        Mark order as partially received.
        
        Called by GRN service when part of the order is received.
        GRN service handles:
        - Validates quantities
        - Creates StockMovement(IN)
        - Updates StockBalance
        - Updates ledger
        
        Args:
            order: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            ValidationError: If order not in correct status
        """
        if order.status not in ('CONFIRMED', 'PARTIAL_RECEIVED'):
            raise ValidationError(
                "Order must be CONFIRMED or PARTIAL_RECEIVED to mark as partially received"
            )
        
        order.status = 'PARTIAL_RECEIVED'
        order.save(update_fields=['status', 'updated_at'])
        
        return order
    
    @staticmethod
    @transaction.atomic
    def mark_posted(order: PurchaseOrder) -> PurchaseOrder:
        """
        Mark order as posted (full receipt and accounting entry).
        
        POSTED status means:
        - After full GRN or Purchase Invoice posted
        - All items received
        - Accounting entries created
        
        Args:
            order: PurchaseOrder instance
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            ValidationError: If order not in correct status
        """
        if order.status not in ('CONFIRMED', 'PARTIAL_RECEIVED'):
            raise ValidationError(
                "Order must be CONFIRMED or PARTIAL_RECEIVED to post"
            )
        
        order.status = 'POSTED'
        order.posted_at = timezone.now()
        order.save(update_fields=['status', 'posted_at', 'updated_at'])
        
        return order
    
    @staticmethod
    @transaction.atomic
    def cancel_order(
        order: PurchaseOrder,
        reason: str
    ) -> PurchaseOrder:
        """
        Cancel purchase order.
        
        Args:
            order: PurchaseOrder instance
            reason: Cancellation reason
            
        Returns:
            Updated PurchaseOrder instance
            
        Raises:
            AlreadyPosted: If order already posted
        """
        if order.status == 'POSTED':
            raise AlreadyPosted(
                "Cannot cancel a posted purchase order"
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
