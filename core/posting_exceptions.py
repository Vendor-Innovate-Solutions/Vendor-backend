"""
Posting exceptions and validation utilities
"""
from decimal import Decimal
from django.core.exceptions import ValidationError


class AlreadyPosted(ValidationError):
    """Raised when attempting to post an already posted voucher"""
    def __init__(self, message="Voucher already posted"):
        super().__init__(message)


class InvalidVoucherStateError(ValidationError):
    """Raised when voucher is in invalid state for an operation"""
    def __init__(self, message="Invalid voucher state"):
        super().__init__(message)


class AlreadyReversedError(ValidationError):
    """Raised when attempting to reverse an already reversed voucher"""
    def __init__(self, message="Voucher already reversed"):
        super().__init__(message)


class ClosedFinancialYearError(ValidationError):
    """Raised when attempting to modify vouchers in closed financial year"""
    def __init__(self, message="Financial year is closed"):
        super().__init__(message)


def validate_double_entry(ledger_lines):
    """
    Validates that ledger lines follow double-entry bookkeeping rules.
    Total debits must equal total credits.
    
    Args:
        ledger_lines: List of dicts with keys: ledger, amount, entry_type
        
    Raises:
        ValidationError: If debits != credits
    """
    total_dr = Decimal("0")
    total_cr = Decimal("0")
    
    for line in ledger_lines:
        if line["entry_type"] == "DR":
            total_dr += line["amount"]
        elif line["entry_type"] == "CR":
            total_cr += line["amount"]
        else:
            raise ValidationError(f"Invalid entry_type: {line['entry_type']}")
    
    if total_dr != total_cr:
        raise ValidationError(
            f"Double entry validation failed: DR={total_dr}, CR={total_cr}. "
            f"Difference: {abs(total_dr - total_cr)}"
        )
