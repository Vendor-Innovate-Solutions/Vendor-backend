"""
Centralized posting validation utilities.

All posting operations (vouchers, invoices, payments) should use these
validators to ensure data integrity and double-entry compliance.
"""
from decimal import Decimal
from typing import List, Dict
from django.core.exceptions import ValidationError


class PostingLine:
    """
    Represents a single posting line for validation.
    
    Attributes:
        ledger_id: Ledger ID
        entry_type: 'DR' or 'CR'
        amount: Decimal amount
    """
    def __init__(self, ledger_id: int, entry_type: str, amount: Decimal):
        self.ledger_id = ledger_id
        self.entry_type = entry_type
        self.amount = amount


def validate_double_entry(lines: List[PostingLine]) -> None:
    """
    Validate that posting lines follow double-entry accounting rules.
    
    Rules:
    1. Total debits must equal total credits
    2. Must have at least 2 lines (one DR, one CR)
    3. All amounts must be positive
    4. Entry types must be 'DR' or 'CR'
    
    Args:
        lines: List of PostingLine objects
    
    Raises:
        ValidationError: If validation fails
    """
    if not lines:
        raise ValidationError("Posting must have at least one line")
    
    if len(lines) < 2:
        raise ValidationError(
            "Double-entry posting requires at least 2 lines (one DR, one CR)"
        )
    
    total_dr = Decimal('0.00')
    total_cr = Decimal('0.00')
    has_debit = False
    has_credit = False
    
    for line in lines:
        # Validate entry type
        if line.entry_type not in ('DR', 'CR'):
            raise ValidationError(
                f"Invalid entry type: {line.entry_type}. Must be 'DR' or 'CR'"
            )
        
        # Validate amount is positive
        if line.amount <= 0:
            raise ValidationError(
                f"Posting line amounts must be positive. Got: {line.amount}"
            )
        
        # Accumulate totals
        if line.entry_type == 'DR':
            total_dr += line.amount
            has_debit = True
        else:  # CR
            total_cr += line.amount
            has_credit = True
    
    # Check we have both DR and CR
    if not has_debit:
        raise ValidationError("Posting must have at least one debit entry")
    
    if not has_credit:
        raise ValidationError("Posting must have at least one credit entry")
    
    # Check totals match (allowing for small rounding differences)
    difference = abs(total_dr - total_cr)
    if difference > Decimal('0.01'):  # Allow 1 paisa tolerance
        raise ValidationError(
            f"Debits ({total_dr}) must equal credits ({total_cr}). "
            f"Difference: {difference}"
        )


def validate_financial_year_open(financial_year) -> None:
    """
    Validate that financial year is open for posting.
    
    Args:
        financial_year: FinancialYear instance
    
    Raises:
        ValidationError: If financial year is closed
    """
    if financial_year.is_closed:
        raise ValidationError(
            f"Financial year '{financial_year.name}' is closed. "
            "Cannot post transactions."
        )


def validate_voucher_postable(voucher) -> None:
    """
    Validate that voucher can be posted.
    
    Args:
        voucher: Voucher instance
    
    Raises:
        ValidationError: If voucher cannot be posted
    """
    if voucher.is_posted:
        raise ValidationError(
            f"Voucher {voucher.voucher_number} is already posted"
        )
    
    if voucher.reversed_at is not None:
        raise ValidationError(
            f"Voucher {voucher.voucher_number} has been reversed. "
            "Cannot post a reversed voucher."
        )
    
    # Check financial year is open
    validate_financial_year_open(voucher.financial_year)


def validate_voucher_reversible(voucher) -> None:
    """
    Validate that voucher can be reversed.
    
    Args:
        voucher: Voucher instance
    
    Raises:
        ValidationError: If voucher cannot be reversed
    """
    if not voucher.is_posted:
        raise ValidationError(
            f"Voucher {voucher.voucher_number} is not posted. "
            "Only posted vouchers can be reversed."
        )
    
    if voucher.reversed_at is not None:
        raise ValidationError(
            f"Voucher {voucher.voucher_number} has already been reversed"
        )
    
    # Check financial year is open
    validate_financial_year_open(voucher.financial_year)


def validate_stock_movement(
    item_id: int,
    from_godown_id: int,
    to_godown_id: int,
    quantity: Decimal
) -> None:
    """
    Validate stock movement parameters.
    
    Args:
        item_id: Item ID
        from_godown_id: Source godown ID (None for inward)
        to_godown_id: Destination godown ID (None for outward)
        quantity: Movement quantity
    
    Raises:
        ValidationError: If validation fails
    """
    if quantity <= 0:
        raise ValidationError("Stock movement quantity must be positive")
    
    if from_godown_id is None and to_godown_id is None:
        raise ValidationError(
            "Stock movement must have either from_godown or to_godown"
        )
    
    if from_godown_id and to_godown_id and from_godown_id == to_godown_id:
        raise ValidationError(
            "Stock movement from_godown and to_godown cannot be the same"
        )


def calculate_posting_summary(lines: List[PostingLine]) -> Dict:
    """
    Calculate summary statistics for a posting.
    
    Args:
        lines: List of PostingLine objects
    
    Returns:
        Dict with total_dr, total_cr, line_count, is_balanced
    """
    total_dr = Decimal('0.00')
    total_cr = Decimal('0.00')
    
    for line in lines:
        if line.entry_type == 'DR':
            total_dr += line.amount
        else:
            total_cr += line.amount
    
    difference = abs(total_dr - total_cr)
    is_balanced = difference <= Decimal('0.01')
    
    return {
        'total_dr': total_dr,
        'total_cr': total_cr,
        'line_count': len(lines),
        'is_balanced': is_balanced,
        'difference': difference,
    }
