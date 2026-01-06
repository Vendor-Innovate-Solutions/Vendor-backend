"""
Credit Control Service

Manages credit limit enforcement and outstanding calculations for parties.

"Money owed is money frozen — don't let retailers turn you into a bank."
"""
from decimal import Decimal
from django.db.models import Sum, Q
from typing import Dict


def get_outstanding_for_party(party) -> Decimal:
    """
    Calculate total outstanding amount for a party.
    
    Outstanding = Total Invoiced - Total Received
    
    Args:
        party: Party instance
        
    Returns:
        Outstanding amount as Decimal
        
    Logic:
    1. Sum all POSTED and PARTIALLY_PAID invoice totals
    2. Sum all payments received
    3. Return difference
    
    Note: Only posted invoices are included to ensure
    accuracy. Draft invoices don't affect credit limit.
    """
    from apps.invoice.models import Invoice
    
    # Get total value of posted/partially paid invoices
    total_invoiced = Invoice.objects.filter(
        party=party,
        status__in=["POSTED", "PARTIALLY_PAID"]
    ).aggregate(
        amt=Sum("grand_total")
    )["amt"] or Decimal("0")
    
    # Get total amount received (from invoice.amount_received field)
    # This is updated by payment allocation signals
    total_received = Invoice.objects.filter(
        party=party,
        status__in=["POSTED", "PARTIALLY_PAID", "PAID"]
    ).aggregate(
        amt=Sum("amount_received")
    )["amt"] or Decimal("0")
    
    outstanding = total_invoiced - total_received
    
    return max(outstanding, Decimal("0"))  # Never return negative


def get_credit_status(party) -> Dict[str, any]:
    """
    Get comprehensive credit status for a party.
    
    Args:
        party: Party instance
        
    Returns:
        dict with credit limit, outstanding, available, utilization
        
    Response structure:
    {
        "credit_limit": 50000.00,
        "outstanding": 40000.00,
        "available": 10000.00,
        "utilization_percent": 80.0,
        "status": "WARNING"  # OK, WARNING, EXCEEDED, NO_LIMIT
    }
    """
    credit_limit = party.credit_limit or Decimal("0")
    outstanding = get_outstanding_for_party(party)
    
    if credit_limit == 0:
        status = "NO_LIMIT"
        utilization = 0.0
        available = Decimal("0")
    else:
        available = credit_limit - outstanding
        utilization = float((outstanding / credit_limit) * 100) if credit_limit > 0 else 0.0
        
        if outstanding > credit_limit:
            status = "EXCEEDED"
        elif utilization >= 80:
            status = "WARNING"
        else:
            status = "OK"
    
    return {
        "party_id": str(party.id),
        "party_name": party.name,
        "credit_limit": str(credit_limit),
        "outstanding": str(outstanding),
        "available": str(max(available, Decimal("0"))),
        "utilization_percent": round(utilization, 2),
        "status": status
    }


def check_credit_limit(party, additional_amount: Decimal) -> bool:
    """
    Check if party can take additional credit.
    
    Args:
        party: Party instance
        additional_amount: New order/invoice value
        
    Returns:
        True if credit available, False if exceeded
        
    Raises:
        ValidationError if credit limit exceeded
        
    Usage:
        if not check_credit_limit(party, order_value):
            raise ValidationError("Credit limit exceeded")
    """
    from django.core.exceptions import ValidationError
    
    credit_limit = party.credit_limit or Decimal("0")
    
    # No limit = unlimited credit
    if credit_limit == 0:
        return True
    
    outstanding = get_outstanding_for_party(party)
    total_exposure = outstanding + additional_amount
    
    if total_exposure > credit_limit:
        raise ValidationError(
            f"Credit limit exceeded. "
            f"Limit: ₹{credit_limit}, Outstanding: ₹{outstanding}, "
            f"New Order: ₹{additional_amount}, Total: ₹{total_exposure}"
        )
    
    return True


def get_overdue_amount(party) -> Decimal:
    """
    Calculate overdue amount for a party.
    
    Args:
        party: Party instance
        
    Returns:
        Total overdue amount
        
    Logic:
    - Sum outstanding of invoices past their due date
    """
    from apps.invoice.models import Invoice
    from django.utils import timezone
    
    today = timezone.now().date()
    
    overdue = Invoice.objects.filter(
        party=party,
        status__in=["POSTED", "PARTIALLY_PAID"],
        due_date__lt=today
    ).aggregate(
        amt=Sum("grand_total")
    )["amt"] or Decimal("0")
    
    # Subtract received amounts
    received = Invoice.objects.filter(
        party=party,
        status__in=["POSTED", "PARTIALLY_PAID"],
        due_date__lt=today
    ).aggregate(
        amt=Sum("amount_received")
    )["amt"] or Decimal("0")
    
    overdue_outstanding = overdue - received
    
    return max(overdue_outstanding, Decimal("0"))


def can_create_order(party, order_value: Decimal) -> Dict[str, any]:
    """
    Check if party can create a new order.
    
    Args:
        party: Party instance
        order_value: Value of new order
        
    Returns:
        dict with allowed flag and reason
        
    Response:
    {
        "allowed": True/False,
        "reason": "Credit available" or "Credit limit exceeded",
        "credit_status": {...}
    }
    """
    credit_status = get_credit_status(party)
    
    try:
        check_credit_limit(party, order_value)
        return {
            "allowed": True,
            "reason": "Credit available",
            "credit_status": credit_status
        }
    except Exception as e:
        return {
            "allowed": False,
            "reason": str(e),
            "credit_status": credit_status
        }
