"""
Voucher Reversal Service

Handles the reversal of posted vouchers for error correction.
Creates reverse entries for both accounting and inventory transactions.
"""
from decimal import Decimal
from typing import Optional
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.voucher.models import Voucher, VoucherLine
from apps.voucher.guards import guard_financial_year_open, guard_voucher_not_reversed, guard_voucher_posted
from apps.accounting.models import LedgerBalance
from apps.inventory.models import StockMovement, StockBalance
from apps.company.models import FinancialYear
from apps.system.models import AuditLog, IntegrationEvent
from core.posting_exceptions import (
    InvalidVoucherStateError,
    ClosedFinancialYearError,
    AlreadyReversedError,
    ValidationError
)

User = get_user_model()


class VoucherReversalService:
    """
    Service for reversing posted vouchers.
    
    Reversal creates a new voucher with opposite entries:
    - Debits become credits and vice versa
    - Stock IN becomes OUT and vice versa (by swapping godowns)
    - All amounts and quantities remain the same
    """
    
    def __init__(self, user: User):
        """
        Initialize the reversal service.
        
        Args:
            user: The user performing the reversal
        """
        self.user = user
    
    @transaction.atomic
    def reverse_voucher(
        self,
        voucher: Voucher,
        reversal_reason: str,
        reversal_date: Optional[timezone.datetime] = None
    ) -> Voucher:
        """
        Reverse a posted voucher.
        
        Creates a new voucher that reverses the original voucher's entries.
        Updates the original voucher's reversal tracking fields.
        
        Args:
            voucher: The voucher to reverse
            reversal_reason: Reason for reversal (required for audit trail)
            reversal_date: Date of reversal (defaults to now)
        
        Returns:
            The newly created reversal voucher
        
        Raises:
            InvalidVoucherStateError: If voucher is not posted
            AlreadyReversedError: If voucher was already reversed
            ClosedFinancialYearError: If financial year is closed
            ValidationError: If reversal_reason is empty
        """
        # Validate inputs
        if not reversal_reason or not reversal_reason.strip():
            raise ValidationError("Reversal reason is required")
        
        reversal_date = reversal_date or timezone.now()
        
        # Validate voucher state
        self._validate_reversal(voucher, reversal_date)
        
        # Create reversal voucher
        reversal_voucher = self._create_reversal_voucher(voucher, reversal_date)
        
        # Reverse ledger entries
        reversed_lines = self._reverse_ledger_entries(voucher, reversal_voucher)
        
        # Update ledger balances
        self._apply_ledger_updates(reversed_lines, reversal_date)
        
        # Reverse stock movements (if any)
        if voucher.stock_movements.exists():
            reversed_movements = self._reverse_stock_movements(voucher, reversal_voucher)
            self._apply_stock_updates(reversed_movements)
        
        # Mark original voucher as reversed
        voucher.status = 'REVERSED'
        voucher.reversed_voucher = reversal_voucher
        voucher.reversed_at = reversal_date
        voucher.reversal_reason = reversal_reason
        voucher.reversal_user = self.user
        voucher.save(update_fields=[
            'status',
            'reversed_voucher',
            'reversed_at',
            'reversal_reason',
            'reversal_user'
        ])
        
        # Create audit trail
        self._create_audit_trail(voucher, reversal_voucher, reversal_reason)
        
        # Emit integration event
        self._emit_integration_event(voucher, reversal_voucher)
        
        return reversal_voucher
    
    def _validate_reversal(self, voucher: Voucher, reversal_date: timezone.datetime):
        """
        Validate that voucher can be reversed.
        
        Args:
            voucher: The voucher to reverse
            reversal_date: The reversal date
        
        Raises:
            InvalidVoucherStateError: If voucher is not posted
            AlreadyReversedError: If voucher was already reversed
            ClosedFinancialYearError: If financial year is closed
        """
        # PHASE 4 COMPLIANCE: Use updated guard functions
        # This ensures FY locking is enforced consistently
        try:
            guard_voucher_posted(voucher)
            guard_voucher_not_reversed(voucher)
            
            # Use the new centralized FY guard from core.services.guards
            from core.services.guards import guard_fy_open
            guard_fy_open(voucher, allow_override=False)
            
        except Exception as e:
            # Convert Django ValidationError to our custom exceptions
            if 'not posted' in str(e).lower() or 'Only POSTED' in str(e):
                raise InvalidVoucherStateError(str(e))
            elif 'already reversed' in str(e).lower():
                raise AlreadyReversedError(str(e))
            elif 'closed' in str(e).lower():
                raise ClosedFinancialYearError(str(e))
            else:
                raise
    
    def _create_reversal_voucher(
        self,
        original: Voucher,
        reversal_date: timezone.datetime
    ) -> Voucher:
        """
        Create a new voucher for the reversal.
        
        Args:
            original: The original voucher being reversed
            reversal_date: The reversal date
        
        Returns:
            The newly created reversal voucher
        """
        reversal = Voucher.objects.create(
            company=original.company,
            voucher_type=original.voucher_type,
            voucher_number=self._generate_reversal_number(original),
            date=reversal_date.date(),
            financial_year=original.financial_year,
            reference_number=f"REV-{original.voucher_number}",
            narration=f"Reversal of {original.voucher_number}: {original.narration or 'N/A'}",
            status='POSTED',  # Reversal voucher is immediately posted
            posted_at=reversal_date
        )
        
        return reversal
    
    def _generate_reversal_number(self, original: Voucher) -> str:
        """
        Generate a unique voucher number for the reversal.
        
        Args:
            original: The original voucher
        
        Returns:
            A unique voucher number
        """
        # Get the last reversal number for this voucher type
        last_reversal = Voucher.objects.filter(
            company=original.company,
            voucher_type=original.voucher_type,
            voucher_number__startswith=f"REV-{original.voucher_type.code}-"
        ).order_by('-voucher_number').first()
        
        if last_reversal:
            # Extract sequence number and increment
            parts = last_reversal.voucher_number.split('-')
            if len(parts) >= 3 and parts[-1].isdigit():
                seq = int(parts[-1]) + 1
            else:
                seq = 1
        else:
            seq = 1
        
        return f"REV-{original.voucher_type.code}-{seq:05d}"
    
    def _reverse_ledger_entries(
        self,
        original: Voucher,
        reversal: Voucher
    ) -> list[VoucherLine]:
        """
        Create reversed ledger entries.
        
        Debits become credits and credits become debits.
        
        Args:
            original: The original voucher
            reversal: The reversal voucher
        
        Returns:
            List of created reversal lines
        """
        reversal_lines = []
        
        for line in original.lines.all():
            # Swap debit and credit
            reversed_entry_type = 'CR' if line.entry_type == 'DR' else 'DR'
            
            reversal_line = VoucherLine.objects.create(
                voucher=reversal,
                line_no=line.line_no,
                ledger=line.ledger,
                amount=line.amount,
                entry_type=reversed_entry_type,  # Swap DR/CR
                cost_center=line.cost_center,
                remarks=f"Reversal: {line.remarks}" if line.remarks else "Reversal"
            )
            reversal_lines.append(reversal_line)
        
        return reversal_lines
    
    def _apply_ledger_updates(
        self,
        lines: list[VoucherLine],
        reversal_date: timezone.datetime
    ):
        """
        Update ledger balances for reversed entries by removing the original transaction's effect.
        
        Since reversal is meant to undo the original transaction, we subtract the original 
        amounts from the balances rather than adding opposite entries.
        
        Args:
            lines: The reversal voucher lines (with swapped DR/CR)
            reversal_date: The reversal date
        """
        from apps.accounting.models import Ledger
        
        # Group by ledger for batch updates
        ledger_updates = {}
        
        for line in lines:
            ledger_id = line.ledger_id
            if ledger_id not in ledger_updates:
                ledger_updates[ledger_id] = {
                    'dr_amount': Decimal('0'),
                    'cr_amount': Decimal('0')
                }
            
            # The reversal line has SWAPPED entry types (DR→CR, CR→DR)
            # So to remove the original effect, we subtract from the original side
            if line.entry_type == 'DR':
                # This was originally CR, so subtract from balance_cr
                ledger_updates[ledger_id]['cr_amount'] -= line.amount
            else:  # CR
                # This was originally DR, so subtract from balance_dr
                ledger_updates[ledger_id]['dr_amount'] -= line.amount
        
        # Apply updates
        for ledger_id, amounts in ledger_updates.items():
            balance, _ = LedgerBalance.objects.select_for_update().get_or_create(
                company=lines[0].voucher.company,
                ledger_id=ledger_id,
                financial_year=lines[0].voucher.financial_year,
                defaults={
                    'balance_dr': Decimal('0'),
                    'balance_cr': Decimal('0')
                }
            )
            
            balance.balance_dr += amounts['dr_amount']  # Will be negative, so subtracts
            balance.balance_cr += amounts['cr_amount']  # Will be negative, so subtracts
            balance.save(update_fields=['balance_dr', 'balance_cr'])
    
    def _reverse_stock_movements(
        self,
        original: Voucher,
        reversal: Voucher
    ) -> list[StockMovement]:
        """
        Create reversed stock movements.
        
        Reverses the direction by swapping from_godown and to_godown.
        
        Args:
            original: The original voucher
            reversal: The reversal voucher
        
        Returns:
            List of created reversal movements
        """
        reversal_movements = []
        
        for movement in original.stock_movements.all():
            # Reverse by swapping from and to godowns
            reversal_movement = StockMovement.objects.create(
                company=original.company,
                item=movement.item,
                from_godown=movement.to_godown,  # Swap: to becomes from
                to_godown=movement.from_godown,  # Swap: from becomes to
                quantity=movement.quantity,      # Same quantity
                rate=movement.rate,
                voucher=reversal,
                movement_date=reversal.date,
                batch=movement.batch
            )
            reversal_movements.append(reversal_movement)
        
        return reversal_movements
    
    def _apply_stock_updates(self, movements: list[StockMovement]):
        """
        Update stock balances for reversed movements.
        
        Args:
            movements: The reversal stock movements
        """
        # Group by stock item and godown
        balance_updates = {}
        
        for movement in movements:
            # Handle outward movement (from_godown)
            if movement.from_godown:
                key = (movement.item_id, movement.from_godown_id)
                if key not in balance_updates:
                    balance_updates[key] = Decimal('0')
                balance_updates[key] -= movement.quantity
            
            # Handle inward movement (to_godown)
            if movement.to_godown:
                key = (movement.item_id, movement.to_godown_id)
                if key not in balance_updates:
                    balance_updates[key] = Decimal('0')
                balance_updates[key] += movement.quantity
        
        # Apply updates
        for (item_id, godown_id), qty_change in balance_updates.items():
            balance, _ = StockBalance.objects.select_for_update().get_or_create(
                company=movements[0].company,
                item_id=item_id,
                godown_id=godown_id,
                batch=None,
                defaults={
                    'quantity_on_hand': Decimal('0'),
                    'quantity_reserved': Decimal('0'),
                    'quantity_allocated': Decimal('0')
                }
            )
            
            balance.quantity_on_hand += qty_change
            balance.last_updated_at = timezone.now()
            balance.save(update_fields=['quantity_on_hand', 'last_updated_at'])
    
    def _create_audit_trail(
        self,
        original: Voucher,
        reversal: Voucher,
        reason: str
    ):
        """
        Create audit log entries for the reversal.
        
        Args:
            original: The original voucher
            reversal: The reversal voucher
            reason: The reversal reason
        """
        AuditLog.objects.create(
            company=original.company,
            actor_user=self.user,
            action_type='REVERSE',
            object_type='Voucher',
            object_id=original.id,
            object_repr=original.voucher_number,
            changes={
                'reversed_voucher_id': str(reversal.id),
                'reversal_reason': reason,
                'reversal_date': timezone.now().isoformat()
            },
            metadata={
                'reversal_voucher_number': reversal.voucher_number
            }
        )
        
        AuditLog.objects.create(
            company=reversal.company,
            actor_user=self.user,
            action_type='CREATE',
            object_type='Voucher',
            object_id=reversal.id,
            object_repr=reversal.voucher_number,
            changes={
                'voucher_number': reversal.voucher_number,
                'reverses': original.voucher_number
            },
            metadata={
                'reversed_voucher_id': str(original.id)
            }
        )
    
    def _emit_integration_event(self, original: Voucher, reversal: Voucher):
        """
        Emit integration event for external systems.
        
        Args:
            original: The original voucher
            reversal: The reversal voucher
        """
        IntegrationEvent.objects.create(
            company=original.company,
            event_type='voucher.reversed',
            payload={
                'original_voucher': {
                    'id': str(original.id),
                    'voucher_number': original.voucher_number
                },
                'reversal_voucher': {
                    'id': str(reversal.id),
                    'voucher_number': reversal.voucher_number
                },
                'reversal_reason': original.reversal_reason,
                'reversed_by': self.user.username,
                'reversed_at': original.reversed_at.isoformat()
            },
            source_object_type='Voucher',
            source_object_id=original.id
        )
