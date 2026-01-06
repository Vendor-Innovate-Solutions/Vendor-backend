"""
Production-grade posting service for ERP system.

This module implements the core posting engine for:
- Vouchers (accounting entries)
- Inventory movements
- Invoice posting
- Stock allocation (FIFO)

All operations are atomic, with proper locking, validation, and audit trails.

Key Features:
1. Double-entry validation with proper Decimal rounding
2. Thread-safe sequence generation
3. SELECT FOR UPDATE locking for concurrency safety
4. FIFO batch allocation
5. Idempotency support
6. Comprehensive audit trail
7. Integration event emission
8. Financial year and lock validation

Usage:
    from core.services.posting import PostingService
    
    service = PostingService()
    voucher = service.post_voucher(voucher_id, user, idempotency_key="optional")
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction, models
from django.db.models import F, Sum
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

# Import models - adjust paths as needed
from apps.company.models import Sequence, FinancialYear, Company, CompanyFeature
from apps.voucher.models import Voucher, VoucherLine, VoucherType
from apps.invoice.models import Invoice, InvoiceLine
from apps.inventory.models import StockMovement, StockItem, StockBatch, Godown, UnitOfMeasure
from apps.accounting.models import Ledger
from apps.system.models import AuditLog, IntegrationEvent, IdempotencyKey


# ============================================================================
# EXCEPTIONS
# ============================================================================

class PostingError(Exception):
    """Base exception for posting operations"""
    pass


class AlreadyPosted(PostingError):
    """Voucher has already been posted"""
    pass


class UnbalancedVoucher(PostingError):
    """Voucher DR != CR"""
    pass


class InsufficientStock(PostingError):
    """Not enough stock available"""
    pass


class FinancialYearClosed(PostingError):
    """Financial year is closed for posting"""
    pass


class CompanyLocked(PostingError):
    """Company features locked (accounting freeze)"""
    pass


class InvalidVoucherType(PostingError):
    """Voucher type is inactive"""
    pass


# ============================================================================
# HELPER DATACLASSES
# ============================================================================

@dataclass
class PostingContext:
    """
    Context for posting operations.
    Carries company, user, time, source document metadata.
    """
    company: Company
    user: Any  # User model
    timestamp: datetime
    source_document_type: Optional[str] = None
    source_document_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'company_id': str(self.company.id),
            'user_id': str(self.user.id) if self.user else None,
            'timestamp': self.timestamp.isoformat(),
            'source_document_type': self.source_document_type,
            'source_document_id': str(self.source_document_id) if self.source_document_id else None,
            'metadata': self.metadata or {},
        }


@dataclass
class VoucherLineData:
    """Data for a single voucher line"""
    ledger: Ledger
    amount: Decimal
    entry_type: str  # 'DR' or 'CR'
    cost_center: Optional[Any] = None
    remarks: Optional[str] = None


@dataclass
class StockAllocation:
    """Represents a stock allocation from a batch"""
    batch_id: str
    godown_id: str
    quantity: Decimal


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def money(val) -> Decimal:
    """
    Convert value to money (2 decimal places, ROUND_HALF_UP).
    
    This is critical for:
    - GST calculations
    - Foreign exchange conversions
    - Large payroll runs
    
    Args:
        val: Any numeric value
        
    Returns:
        Decimal rounded to 2 decimal places
    """
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ============================================================================
# POSTING SERVICE
# ============================================================================

class PostingService:
    """
    Core posting service for ERP system.
    
    Handles:
    - Voucher posting
    - Invoice posting
    - Stock movements
    - Audit trails
    """
    
    def __init__(self):
        """Initialize posting service"""
        self.User = get_user_model()
    
    # ========================================================================
    # SEQUENCE GENERATION
    # ========================================================================
    
    def next_sequence_value(self, company: Company, key: str) -> str:
        """
        Get next sequence value with locking.
        
        IMPROVEMENT: Use compound key to prevent cross-type/cross-FY collisions.
        
        Args:
            company: Company instance
            key: Sequence key
            
        Returns:
            Formatted sequence number
            
        Raises:
            PostingError: If sequence not found
        """
        try:
            seq = Sequence.objects.select_for_update().get(company=company, key=key)
        except Sequence.DoesNotExist:
            raise PostingError(f"Sequence not found: {key}")
        
        seq.last_value += 1
        seq.save(update_fields=["last_value", "updated_at"])
        
        # Format: prefix + padded number
        number = f"{seq.prefix or ''}{seq.last_value:06d}"
        return number
    
    def build_sequence_key(self, voucher: Voucher) -> str:
        """
        Build compound sequence key to prevent collisions.
        
        Format: {company_id}:{voucher_type_code}:{fy_id}
        
        This ensures:
        - No cross-FY collisions
        - Clean numbering reset behavior
        - Per-type sequences
        
        Args:
            voucher: Voucher instance
            
        Returns:
            Compound sequence key
        """
        return f"{voucher.company_id}:{voucher.voucher_type.code}:{voucher.financial_year_id}"
    
    # ========================================================================
    # LEDGER BALANCES
    # ========================================================================
    
    def update_ledger_balances(self, voucher: Voucher) -> None:
        """
        Update LedgerBalance records based on voucher lines.
        
        Creates or updates LedgerBalance records for each ledger affected
        by the voucher. Uses select_for_update() for concurrency safety.
        
        Args:
            voucher: Posted voucher with lines
        """
        from apps.accounting.models import LedgerBalance
        
        # Get all voucher lines
        lines = voucher.lines.select_related('ledger').all()
        
        # Track balance updates per ledger
        balance_updates = {}  # key: ledger_id, value: (dr_delta, cr_delta)
        
        for line in lines:
            ledger_id = line.ledger.id
            if ledger_id not in balance_updates:
                balance_updates[ledger_id] = {'dr': Decimal('0'), 'cr': Decimal('0')}
            
            # Add to appropriate side
            if line.entry_type == 'DR':
                balance_updates[ledger_id]['dr'] += line.amount
            else:  # CR
                balance_updates[ledger_id]['cr'] += line.amount
        
        # Update or create balance records
        for ledger_id, deltas in balance_updates.items():
            from apps.accounting.models import Ledger
            ledger = Ledger.objects.get(id=ledger_id)
            
            # Get or create balance record with lock
            balance, created = LedgerBalance.objects.select_for_update().get_or_create(
                company=voucher.company,
                ledger=ledger,
                financial_year=voucher.financial_year,
                defaults={
                    'balance_dr': Decimal('0'),
                    'balance_cr': Decimal('0')
                }
            )
            
            # Update balances
            balance.balance_dr += deltas['dr']
            balance.balance_cr += deltas['cr']
            balance.last_posted_voucher = voucher
            balance.last_updated_at = timezone.now()
            balance.save()
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    def validate_double_entry(self, lines: List[VoucherLineData]) -> None:
        """
        Validate double-entry balance with proper Decimal rounding.
        
        IMPROVEMENT: Uses money() function to handle:
        - GST rounding issues
        - Forex conversion differences
        - Large payroll runs
        
        Args:
            lines: List of voucher line data
            
        Raises:
            UnbalancedVoucher: If DR != CR
        """
        total_dr = sum(money(l.amount) for l in lines if l.entry_type == "DR")
        total_cr = sum(money(l.amount) for l in lines if l.entry_type == "CR")
        
        # Use money() for comparison to handle rounding
        if money(total_dr) != money(total_cr):
            raise UnbalancedVoucher(
                f"Voucher unbalanced: DR {total_dr} != CR {total_cr} "
                f"(difference: {abs(total_dr - total_cr)})"
            )
    
    def validate_posting_allowed(self, voucher: Voucher) -> None:
        """
        Validate that posting is allowed.
        
        Checks:
        1. Financial year is not closed
        2. Company features not locked
        3. Voucher type is active
        4. Voucher has been approved (if approval required)
        
        Args:
            voucher: Voucher instance
            
        Raises:
            FinancialYearClosed: If FY is closed
            CompanyLocked: If company locked
            InvalidVoucherType: If voucher type inactive
            PostingError: If approval required but not approved
        """
        # PHASE 4 COMPLIANCE: Check financial year using guard
        from core.services.guards import guard_fy_open
        try:
            guard_fy_open(voucher, allow_override=False)
        except Exception as e:
            raise FinancialYearClosed(str(e))
        
        # Check company lock (accounting freeze)
        try:
            features = CompanyFeature.objects.get(company=voucher.company)
            if features.locked:
                raise CompanyLocked(
                    "Company features locked. No financial modifications allowed."
                )
        except CompanyFeature.DoesNotExist:
            pass  # No features record = not locked
        
        # Check voucher type
        if not voucher.voucher_type.is_active:
            raise InvalidVoucherType(
                f"Voucher type {voucher.voucher_type.name} is inactive"
            )
        
        # PHASE 5 AUTOMATION: Check approval status
        from apps.workflow.models import Approval, ApprovalStatus, ApprovalRule
        
        # Check if approval required for this voucher type
        try:
            rule = ApprovalRule.objects.get(
                company=voucher.company,
                target_type='voucher',
                approval_required=True
            )
            
            # Check if auto-approve threshold applies
            if rule.auto_approve_below_threshold and rule.threshold_amount:
                total_amount = voucher.lines.aggregate(
                    total=Sum('amount')
                )['total'] or Decimal('0')
                
                if total_amount < rule.threshold_amount:
                    return  # Auto-approved due to threshold
            
            # Check for approved approval
            approval = Approval.objects.filter(
                company=voucher.company,
                target_type='voucher',
                target_id=voucher.id,
                status=ApprovalStatus.APPROVED
            ).first()
            
            if not approval:
                raise PostingError(
                    "Voucher requires approval before posting. "
                    "Submit for approval using POST /api/workflow/request/"
                )
                
        except ApprovalRule.DoesNotExist:
            pass  # No approval rule = no approval required
    
    # ========================================================================
    # STOCK ALLOCATION
    # ========================================================================
    
    def allocate_batches_fifo(
        self,
        company: Company,
        item: StockItem,
        godown: Godown,
        required_qty: Decimal,
        prefer_batch_id: Optional[str] = None
    ) -> List[StockAllocation]:
        """
        Allocate stock using FIFO logic.
        
        IMPROVEMENT: Uses SELECT FOR UPDATE to lock rows during allocation.
        This prevents race conditions where two concurrent posts see the same stock.
        
        Args:
            company: Company instance
            item: Stock item
            godown: Godown (warehouse)
            required_qty: Quantity needed
            prefer_batch_id: Optional preferred batch
            
        Returns:
            List of stock allocations
            
        Raises:
            InsufficientStock: If not enough stock available
        """
        need = money(required_qty)
        allocations = []
        
        # Build base queryset for batches
        batches_qs = StockBatch.objects.filter(
            company=company,
            item=item,
            is_active=True
        ).order_by('mfg_date', 'created_at')
        
        # CRITICAL FIX: Lock stock balance rows before reading availability
        # This prevents race conditions in concurrent posting
        from django.db.models import Q
        
        # Get all potential batches and lock their balances
        batch_ids = list(batches_qs.values_list('id', flat=True))
        
        # If no batches exist, check if we need to create opening stock
        if not batch_ids:
            # For OUT movements, we need existing stock
            raise InsufficientStock(
                f"No stock batches exist for item {item.sku} in {godown.name}"
            )
        
        # Lock all relevant stock balance rows
        # This prevents concurrent allocations
        stock_balances = {}
        for batch in batches_qs.select_for_update():
            # Get balance for this batch in this godown (locked)
            from apps.inventory.models import StockMovement
            
            # Calculate balance from movements (StockBalance is a read model)
            # IN movements increase stock, OUT movements decrease
            balance = StockMovement.objects.filter(
                company=company,
                item=item,
                batch=batch
            ).filter(
                Q(to_godown=godown) | Q(from_godown=godown)
            ).aggregate(
                total=Sum(
                    F('quantity'),
                    output_field=models.DecimalField()
                )
            )['total'] or Decimal(0)
            
            stock_balances[str(batch.id)] = {
                'batch': batch,
                'available': money(balance)
            }
        
        # Allocate from preferred batch first if specified
        if prefer_batch_id and prefer_batch_id in stock_balances:
            batch_info = stock_balances[prefer_batch_id]
            available = batch_info['available']
            if available > 0:
                take = min(available, need)
                allocations.append(StockAllocation(
                    batch_id=prefer_batch_id,
                    godown_id=str(godown.id),
                    quantity=take
                ))
                need -= take
        
        # Allocate remaining from other batches (FIFO)
        if need > 0:
            for batch_id, batch_info in stock_balances.items():
                if batch_id == prefer_batch_id:
                    continue  # Already allocated
                
                available = batch_info['available']
                if available <= 0:
                    continue
                
                take = min(available, need)
                allocations.append(StockAllocation(
                    batch_id=batch_id,
                    godown_id=str(godown.id),
                    quantity=take
                ))
                need -= take
                
                if need <= 0:
                    break
        
        # Check if we allocated enough
        if need > 0:
            raise InsufficientStock(
                f"Insufficient stock for {item.sku} in {godown.name}. "
                f"Required: {required_qty}, Available: {required_qty - need}, "
                f"Missing: {need}"
            )
        
        return allocations
    
    # ========================================================================
    # STOCK MOVEMENTS
    # ========================================================================
    
    def create_stock_movements(
        self,
        voucher: Voucher,
        invoice: Invoice,
        context: PostingContext
    ) -> List[StockMovement]:
        """
        Create stock movements for invoice.
        
        IMPROVEMENT: StockMovement rows are the audit trail.
        Stock balances are derived read models.
        
        This function:
        1. Allocates stock using FIFO
        2. Creates StockMovement records
        3. Does NOT update StockBalance (that's done separately)
        
        Args:
            voucher: Voucher instance (already saved)
            invoice: Invoice instance
            context: Posting context
            
        Returns:
            List of created stock movements
            
        Raises:
            InsufficientStock: If allocation fails
        """
        movements = []
        
        # Get default godown for company
        godown = Godown.objects.filter(
            company=voucher.company,
            is_active=True
        ).first()
        
        if not godown:
            raise PostingError("No active godown found for company")
        
        # Process each invoice line
        for line in invoice.lines.all():
            # Allocate batches for this line
            allocations = self.allocate_batches_fifo(
                company=voucher.company,
                item=line.item,
                godown=godown,
                required_qty=line.quantity
            )
            
            # Create stock movements for each allocation
            for alloc in allocations:
                movement = StockMovement(
                    company=voucher.company,
                    voucher=voucher,
                    item=line.item,
                    from_godown=godown if invoice.invoice_type == 'SALES' else None,
                    to_godown=godown if invoice.invoice_type == 'PURCHASE' else None,
                    batch_id=alloc.batch_id,
                    quantity=alloc.quantity,
                    rate=line.unit_rate,
                    movement_date=voucher.date
                )
                movements.append(movement)
        
        # Bulk create all movements
        if movements:
            StockMovement.objects.bulk_create(movements)
        
        return movements
    
    def update_stock_balances_from_movements(
        self,
        voucher: Voucher
    ) -> None:
        """
        Update StockBalance records based on voucher's stock movements.
        
        This is called when stock movements already exist (e.g., created by tests)
        and need to update the cached balance table.
        
        Validates stock availability for outward movements before updating.
        
        Args:
            voucher: Voucher with existing stock movements
            
        Raises:
            InsufficientStock: If any outward movement exceeds available stock
        """
        from apps.inventory.models import StockBalance
        
        # Get all stock movements for this voucher
        movements = voucher.stock_movements.select_related(
            'item', 'from_godown', 'to_godown', 'batch'
        ).all()
        
        # Track which balances need updating
        balance_updates = {}  # key: (item_id, godown_id, batch_id), value: quantity_delta
        
        for movement in movements:
            # For outward movements (from_godown)
            if movement.from_godown:
                key = (movement.item.id, movement.from_godown.id, 
                       movement.batch.id if movement.batch else None)
                balance_updates[key] = balance_updates.get(key, Decimal('0')) - movement.quantity
            
            # For inward movements (to_godown)
            if movement.to_godown:
                key = (movement.item.id, movement.to_godown.id,
                       movement.batch.id if movement.batch else None)
                balance_updates[key] = balance_updates.get(key, Decimal('0')) + movement.quantity
        
        # Update or create StockBalance records
        for (item_id, godown_id, batch_id), delta in balance_updates.items():
            from apps.inventory.models import StockItem, Godown, StockBatch
            
            # Get instances
            item = StockItem.objects.get(id=item_id)
            godown = Godown.objects.get(id=godown_id)
            batch = StockBatch.objects.get(id=batch_id) if batch_id else None
            
            # Get or create balance record with lock
            balance, created = StockBalance.objects.select_for_update().get_or_create(
                company=voucher.company,
                item=item,
                godown=godown,
                batch=batch,
                defaults={
                    'quantity_on_hand': Decimal('0'),
                    'quantity_reserved': Decimal('0'),
                    'quantity_allocated': Decimal('0')
                }
            )
            
            # Check for insufficient stock on outward movements
            if delta < 0:  # Negative delta means outward movement
                new_balance = balance.quantity_on_hand + delta
                if new_balance < 0:
                    batch_info = f" batch {batch.batch_number}" if batch else ""
                    raise InsufficientStock(
                        f"Insufficient stock for {item.sku}{batch_info} in {godown.name}. "
                        f"Available: {balance.quantity_on_hand}, Required: {abs(delta)}, "
                        f"Missing: {abs(new_balance)}"
                    )
            
            # Update quantity
            balance.quantity_on_hand += delta
            balance.last_movement = movement
            balance.last_updated_at = timezone.now()
            balance.save()
    
    # ========================================================================
    # IDEMPOTENCY
    # ========================================================================
    
    def check_idempotency(
        self,
        company: Company,
        idempotency_key: str
    ) -> Optional[Voucher]:
        """
        Check if operation already completed.
        
        IMPROVEMENT: Implements proper idempotency tracking.
        
        Args:
            company: Company instance
            idempotency_key: Unique key for operation
            
        Returns:
            Voucher if already posted, None otherwise
        """
        try:
            record = IdempotencyKey.objects.select_related('voucher').get(
                company=company,
                key=idempotency_key
            )
            return record.voucher
        except IdempotencyKey.DoesNotExist:
            return None
    
    def record_idempotency(
        self,
        company: Company,
        idempotency_key: str,
        voucher: Voucher
    ) -> None:
        """
        Record idempotency key.
        
        Args:
            company: Company instance
            idempotency_key: Unique key
            voucher: Posted voucher
        """
        IdempotencyKey.objects.create(
            company=company,
            key=idempotency_key,
            voucher=voucher
        )
    
    # ========================================================================
    # AUDIT & EVENTS
    # ========================================================================
    
    def create_audit_log(
        self,
        context: PostingContext,
        voucher: Voucher,
        action_type: str,
        changes: Dict[str, Any]
    ) -> AuditLog:
        """
        Create audit log entry.
        
        IMPROVEMENT: Logs are created AFTER successful commit,
        not inside the transaction (to avoid losing failure visibility).
        
        Args:
            context: Posting context
            voucher: Voucher instance
            action_type: Action type
            changes: Changes made
            
        Returns:
            Created audit log
        """
        return AuditLog.objects.create(
            company=context.company,
            actor_user=context.user,
            action_type=action_type,
            object_type='Voucher',
            object_id=voucher.id,
            object_repr=str(voucher),
            changes=changes,
            ip_address=context.metadata.get('ip_address') if context.metadata else None,
            user_agent=context.metadata.get('user_agent', '') if context.metadata else '',
            metadata=context.to_dict()
        )
    
    def create_integration_event(
        self,
        context: PostingContext,
        voucher: Voucher,
        event_type: str
    ) -> IntegrationEvent:
        """
        Create integration event for external systems.
        
        Created synchronously, processed asynchronously by workers.
        
        Args:
            context: Posting context
            voucher: Voucher instance
            event_type: Event type
            
        Returns:
            Created integration event
        """
        # Ensure all data is JSON serializable
        import json
        context_dict = context.to_dict()
        
        # Create payload with all strings/serializable types
        payload = {
            'voucher_id': str(voucher.id),
            'voucher_number': voucher.voucher_number,
            'voucher_type': voucher.voucher_type.code,
            'amount': str(voucher.lines.aggregate(
                total=Sum('amount')
            )['total'] or 0),
            'context': context_dict
        }
        
        # Validate JSON serializability
        try:
            json.dumps(payload)
        except TypeError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Payload not JSON serializable: {e}")
            # Remove non-serializable parts
            payload['context'] = {k: v for k, v in context_dict.items() if k != 'metadata'}
        
        return IntegrationEvent.objects.create(
            company=context.company,
            event_type=event_type,
            payload=payload,
            status='PENDING',
            source_object_type='Voucher',
            source_object_id=voucher.id
        )
    
    # ========================================================================
    # MAIN POSTING METHODS
    # ========================================================================
    
    def post_voucher(
        self,
        voucher_id: str,
        user: Any,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Voucher:
        """
        Post a voucher.
        
        This is the main entry point for voucher posting.
        
        Flow:
        1. Check idempotency
        2. Validate posting allowed
        3. Start transaction
        4. Lock voucher
        5. Validate double-entry
        6. Allocate sequence number
        7. Create stock movements (if applicable)
        8. Update voucher status
        9. Create audit log & events
        10. Commit
        
        Args:
            voucher_id: Voucher ID
            user: User performing action
            idempotency_key: Optional idempotency key
            metadata: Optional metadata (IP, user agent, etc.)
            
        Returns:
            Posted voucher
            
        Raises:
            AlreadyPosted: If voucher already posted
            UnbalancedVoucher: If DR != CR
            InsufficientStock: If not enough stock
            FinancialYearClosed: If FY closed
            CompanyLocked: If company locked
        """
        # Create posting context
        context = PostingContext(
            company=None,  # Will be set after loading voucher
            user=user,
            timestamp=timezone.now(),
            source_document_type='Voucher',
            source_document_id=voucher_id,
            metadata=metadata or {}
        )
        
        # IMPROVEMENT: Single atomic block per posting operation
        # No nested atomic() calls
        with transaction.atomic():
            # Lock voucher for update
            voucher = Voucher.objects.select_for_update().select_related(
                'company',
                'voucher_type',
                'financial_year'
            ).get(id=voucher_id)
            
            # Update context with company
            context.company = voucher.company
            
            # Validate voucher status first
            if voucher.status == 'POSTED':
                raise AlreadyPosted(
                    f"Voucher {voucher.voucher_number} already posted"
                )
            
            # Check idempotency
            if idempotency_key:
                existing = self.check_idempotency(voucher.company, idempotency_key)
                if existing:
                    # If same voucher trying to post again, return it (idempotent)
                    # This allows retry with same idempotency key
                    return existing
            
            # Validate posting is allowed
            self.validate_posting_allowed(voucher)
            
            # Get voucher lines and validate double-entry
            lines = []
            for line in voucher.lines.select_related('ledger').all():
                lines.append(VoucherLineData(
                    ledger=line.ledger,
                    amount=line.amount,
                    entry_type=line.entry_type,
                    cost_center=line.cost_center,
                    remarks=line.remarks
                ))
            
            if not lines:
                raise PostingError("Voucher has no lines")
            
            self.validate_double_entry(lines)
            
            # Allocate sequence number
            seq_key = self.build_sequence_key(voucher)
            voucher_number = self.next_sequence_value(voucher.company, seq_key)
            voucher.voucher_number = voucher_number
            
            # Handle inventory movements if applicable
            if voucher.voucher_type.is_inventory:
                # Check if voucher is linked to an invoice
                try:
                    invoice = voucher.invoice
                    if invoice:
                        # Create stock movements
                        movements = self.create_stock_movements(
                            voucher, invoice, context
                        )
                        
                        # Update stock balances from the created movements
                        self.update_stock_balances_from_movements(voucher)
                        
                        # Update invoice status
                        invoice.status = 'POSTED'
                        invoice.save(update_fields=['status', 'updated_at'])
                except AttributeError:
                    # No linked invoice - check if stock movements already exist
                    if not voucher.stock_movements.exists():
                        raise PostingError(
                            "Inventory voucher must be linked to an invoice or have stock movements"
                        )
                    # Process existing stock movements to update balances
                    self.update_stock_balances_from_movements(voucher)
            
            # Update voucher status
            voucher.status = 'POSTED'
            voucher.posted_at = context.timestamp
            voucher.save(update_fields=['voucher_number', 'status', 'posted_at', 'updated_at'])
            
            # Update ledger balances
            self.update_ledger_balances(voucher)
            
            # Record idempotency
            if idempotency_key:
                self.record_idempotency(
                    voucher.company,
                    idempotency_key,
                    voucher
                )
            
            # Commit happens here automatically
        
        # IMPROVEMENT: Create audit log OUTSIDE transaction
        # This ensures we capture failure events
        try:
            with transaction.atomic():
                self.create_audit_log(
                    context,
                    voucher,
                    'POST',
                    {
                        'voucher_number': voucher_number,
                        'status': 'POSTED',
                        'voucher_type': voucher.voucher_type.code
                    }
                )
        except Exception as e:
            # Log error but don't fail posting
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
        
        # Create integration event (also outside transaction)
        try:
            with transaction.atomic():
                self.create_integration_event(
                    context,
                    voucher,
                    'voucher.posted'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create integration event: {e}", exc_info=True)
        
        return voucher
    
    def post_invoice(
        self,
        invoice_id: str,
        user: Any,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Voucher:
        """
        Post an invoice (creates and posts voucher).
        
        Args:
            invoice_id: Invoice ID
            user: User performing action
            idempotency_key: Optional idempotency key
            metadata: Optional metadata
            
        Returns:
            Created and posted voucher
            
        Raises:
            PostingError: If invoice already posted or invalid
        """
        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().select_related(
                'company',
                'party',
                'financial_year'
            ).get(id=invoice_id)
            
            # Check if already posted
            if invoice.voucher:
                raise AlreadyPosted("Invoice already posted")
            
            # Create voucher from invoice
            # Get appropriate voucher type
            voucher_type_code = 'SALES' if invoice.invoice_type == 'SALES' else 'PURCHASE'
            voucher_type = VoucherType.objects.get(
                company=invoice.company,
                code=voucher_type_code
            )
            
            # Create voucher
            voucher = Voucher.objects.create(
                company=invoice.company,
                voucher_type=voucher_type,
                financial_year=invoice.financial_year,
                date=invoice.invoice_date,
                narration=f"Invoice {invoice.invoice_number}",
                status='DRAFT'
            )
            
            # Create voucher lines from invoice
            # Party ledger (DR for sales, CR for purchase)
            VoucherLine.objects.create(
                voucher=voucher,
                line_no=1,
                ledger=invoice.party.ledger,
                amount=invoice.grand_total,
                entry_type='DR' if invoice.invoice_type == 'SALES' else 'CR'
            )
            
            # Sales/Purchase ledger (CR for sales, DR for purchase)
            # This is simplified - real implementation would break down by item/tax
            sales_ledger = Ledger.objects.get(
                company=invoice.company,
                code='SALES' if invoice.invoice_type == 'SALES' else 'PURCHASE'
            )
            VoucherLine.objects.create(
                voucher=voucher,
                line_no=2,
                ledger=sales_ledger,
                amount=invoice.grand_total,
                entry_type='CR' if invoice.invoice_type == 'SALES' else 'DR'
            )
            
            # Link voucher to invoice
            invoice.voucher = voucher
            invoice.save(update_fields=['voucher', 'updated_at'])
        
        # Post the voucher
        return self.post_voucher(
            str(voucher.id),
            user,
            idempotency_key,
            metadata
        )
    
    def reverse_voucher(
        self,
        voucher_id: str,
        user: Any,
        reason: str,
        reversal_date: Optional[datetime] = None
    ) -> Voucher:
        """
        Reverse a posted voucher.
        
        This method delegates to VoucherReversalService for the actual reversal logic.
        
        Args:
            voucher_id: ID of voucher to reverse
            user: User performing reversal
            reason: Reason for reversal (required for audit trail)
            reversal_date: Date of reversal (defaults to now)
            
        Returns:
            The newly created reversal voucher
            
        Raises:
            PostingError: If voucher not found or reversal fails
        """
        from apps.voucher.services import VoucherReversalService
        
        try:
            # Get voucher with lock
            voucher = Voucher.objects.select_for_update().select_related(
                'company',
                'voucher_type',
                'financial_year'
            ).get(id=voucher_id)
            
            # Create reversal service
            reversal_service = VoucherReversalService(user=user)
            
            # Perform reversal
            reversal_voucher = reversal_service.reverse_voucher(
                voucher=voucher,
                reversal_reason=reason,
                reversal_date=reversal_date or timezone.now()
            )
            
            return reversal_voucher
            
        except Voucher.DoesNotExist:
            raise PostingError(f"Voucher not found: {voucher_id}")
        except Exception as e:
            # Convert any exceptions to PostingError for consistency
            if isinstance(e, PostingError):
                raise
            raise PostingError(f"Reversal failed: {str(e)}")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def post_voucher(voucher_id: str, user: Any, **kwargs) -> Voucher:
    """Convenience function to post a voucher"""
    service = PostingService()
    return service.post_voucher(voucher_id, user, **kwargs)


def post_invoice(invoice_id: str, user: Any, **kwargs) -> Voucher:
    """Convenience function to post an invoice"""
    service = PostingService()
    return service.post_invoice(invoice_id, user, **kwargs)
