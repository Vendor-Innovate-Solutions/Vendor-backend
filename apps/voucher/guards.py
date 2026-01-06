"""
Voucher guard functions.
Business rule enforcement for voucher operations.
"""
from django.core.exceptions import ValidationError


def guard_financial_year_open(voucher, allow_override=False):
    """
    Ensure financial year is open before allowing modifications.
    
    Prevents voucher modifications (especially reversals) after year close
    unless explicitly overridden by authorized users.
    
    Args:
        voucher: Voucher instance to check
        allow_override: If True, skip the check (for ADMIN override)
        
    Raises:
        ValidationError: If financial year is closed and override not allowed
    """
    fy = voucher.financial_year
    
    if fy and fy.is_closed and not allow_override:
        raise ValidationError(
            f"Financial year {fy.start_date.year}-{fy.end_date.year} is closed. "
            "Cannot modify vouchers in closed periods."
        )


def guard_voucher_not_reversed(voucher):
    """
    Ensure voucher has not already been reversed.
    
    Args:
        voucher: Voucher instance to check
        
    Raises:
        ValidationError: If voucher is already reversed
    """
    if voucher.status == 'REVERSED':
        raise ValidationError(
            f"Voucher {voucher.voucher_number} has already been reversed."
        )


def guard_voucher_posted(voucher):
    """
    Ensure voucher is posted before allowing reversal.
    
    Args:
        voucher: Voucher instance to check
        
    Raises:
        ValidationError: If voucher is not posted
    """
    if voucher.status != 'POSTED':
        raise ValidationError(
            f"Cannot reverse voucher {voucher.voucher_number}. "
            f"Only POSTED vouchers can be reversed (current status: {voucher.status})."
        )
