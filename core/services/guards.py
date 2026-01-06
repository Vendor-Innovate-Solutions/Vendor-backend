"""
Global Guard Functions

Centralized validation guards for business rules enforcement.
Used across posting, reversal, and other critical operations.
"""
from django.core.exceptions import ValidationError


def guard_fy_open(voucher, allow_override: bool = False):
    """
    Guard to prevent posting or reversal in closed financial years.
    
    Args:
        voucher: Voucher instance to check
        allow_override: If True, allows ADMIN override (default: False)
        
    Raises:
        ValidationError: If financial year is closed and no override
        
    Usage in posting:
        ```python
        guard_fy_open(voucher)
        # continue posting
        ```
    
    Usage in reversal:
        ```python
        guard_fy_open(original_voucher)
        # continue reversal
        ```
    
    This enforces:
    - Audit compliance
    - GST compliance
    - Financial integrity
    - Statutory reporting requirements
    
    Once a financial year is closed:
    - No new transactions can be posted
    - No existing transactions can be reversed
    - No modifications to accounting data
    
    This is standard practice in:
    - Tally ERP
    - Zoho Books
    - SAP
    - Oracle Financials
    """
    if not hasattr(voucher, 'financial_year'):
        raise ValidationError(
            "Voucher must have a financial_year to check if FY is open"
        )
    
    if not voucher.financial_year:
        raise ValidationError(
            "Voucher does not have a financial year assigned"
        )
    
    if voucher.financial_year.is_closed:
        if allow_override:
            # Override allowed - just log a warning
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"FY guard override: Posting/reversal in closed FY {voucher.financial_year.name} "
                f"for voucher {voucher.id}"
            )
        else:
            raise ValidationError(
                f"Financial year {voucher.financial_year.name} is closed. "
                f"Posting and reversal are not allowed. "
                f"Contact administrator to reopen the financial year if needed."
            )


def guard_posting_date_in_fy(voucher):
    """
    Guard to ensure posting date falls within the financial year.
    
    Args:
        voucher: Voucher instance to check
        
    Raises:
        ValidationError: If posting date is outside FY range
    """
    if not hasattr(voucher, 'financial_year') or not voucher.financial_year:
        raise ValidationError("Voucher must have a financial year assigned")
    
    if not hasattr(voucher, 'posting_date') or not voucher.posting_date:
        raise ValidationError("Voucher must have a posting date")
    
    fy = voucher.financial_year
    if not (fy.start_date <= voucher.posting_date <= fy.end_date):
        raise ValidationError(
            f"Posting date {voucher.posting_date} is outside financial year "
            f"{fy.name} ({fy.start_date} to {fy.end_date})"
        )


def guard_company_active(company):
    """
    Guard to ensure company is active.
    
    Args:
        company: Company instance to check
        
    Raises:
        ValidationError: If company is inactive or deleted
    """
    if not hasattr(company, 'is_active') or not company.is_active:
        raise ValidationError(
            f"Company {company.name if hasattr(company, 'name') else company.id} is not active"
        )
    
    if hasattr(company, 'is_deleted') and company.is_deleted:
        raise ValidationError(
            f"Company {company.name if hasattr(company, 'name') else company.id} is deleted"
        )


def guard_ledger_active(ledger):
    """
    Guard to ensure ledger is active before posting.
    
    Args:
        ledger: Ledger instance to check
        
    Raises:
        ValidationError: If ledger is inactive
    """
    if not hasattr(ledger, 'is_active') or not ledger.is_active:
        raise ValidationError(
            f"Ledger {ledger.name if hasattr(ledger, 'name') else ledger.id} is not active"
        )


def guard_item_active(item):
    """
    Guard to ensure item is active before creating stock movements.
    
    Args:
        item: Item instance to check
        
    Raises:
        ValidationError: If item is inactive
    """
    if not hasattr(item, 'is_active') or not item.is_active:
        raise ValidationError(
            f"Item {item.name if hasattr(item, 'name') else item.id} is not active"
        )


# Export all guards
__all__ = [
    'guard_fy_open',
    'guard_posting_date_in_fy',
    'guard_company_active',
    'guard_ledger_active',
    'guard_item_active',
]
