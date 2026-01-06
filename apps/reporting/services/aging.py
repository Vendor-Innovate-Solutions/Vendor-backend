"""
Aging Report Service.

Calculates receivables aging for companies - shows how long invoices 
have been outstanding in different time buckets.

PHASE 5 - Aging Report Implementation:
- Bucket classification: 0-30, 31-60, 61-90, 90+ days
- Party-wise breakdown
- Caching mechanism for daily reports
- Integration with Celery for scheduled generation

Aging reports are the subtle threat letters of accounting.
If you don't remind customers to pay, they won't.

Usage:
    from apps.reporting.services.aging import aging_for_company
    
    report = aging_for_company(company)
    # Returns dict with buckets and party breakdown
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Sum, Q, F
from django.core.cache import cache


def money(value) -> Decimal:
    """Round to 2 decimal places"""
    if value is None:
        return Decimal('0.00')
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def aging_for_company(company, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Calculate aging report for a company.
    
    Shows outstanding invoices grouped by age buckets:
    - 0-30 days: Current
    - 31-60 days: Slightly overdue
    - 61-90 days: Overdue
    - 90+ days: Seriously overdue
    
    Args:
        company: Company instance
        as_of_date: Calculate aging as of this date (default: today)
        
    Returns:
        Dict with:
        - total_outstanding: Total across all buckets
        - buckets: Dict with 0-30, 31-60, 61-90, 90+ amounts
        - parties: List of dicts with party-wise breakdown
        - as_of_date: Date of calculation
        
    Example:
        {
            "total_outstanding": "150000.00",
            "buckets": {
                "0-30": "50000.00",
                "31-60": "40000.00",
                "61-90": "30000.00",
                "90+": "30000.00"
            },
            "parties": [
                {
                    "party_id": "...",
                    "party_name": "ABC Retailers",
                    "total": "50000.00",
                    "buckets": {
                        "0-30": "30000.00",
                        "31-60": "20000.00",
                        "61-90": "0.00",
                        "90+": "0.00"
                    }
                }
            ],
            "as_of_date": "2024-01-15"
        }
    """
    from apps.invoice.models import Invoice
    from apps.party.models import Party
    
    if as_of_date is None:
        as_of_date = timezone.now().date()
    
    # Get all posted/partially paid invoices
    invoices = Invoice.objects.filter(
        company=company,
        status__in=['POSTED', 'PARTIALLY_PAID']
    ).select_related('party').order_by('party__name', 'invoice_date')
    
    # Initialize buckets
    total_buckets = {
        "0-30": Decimal('0'),
        "31-60": Decimal('0'),
        "61-90": Decimal('0'),
        "90+": Decimal('0')
    }
    
    # Track party-wise aging
    party_aging = {}  # party_id -> {name, total, buckets}
    
    for invoice in invoices:
        # Calculate outstanding for this invoice
        outstanding = money(invoice.grand_total) - money(invoice.amount_received or 0)
        
        if outstanding <= 0:
            continue  # Fully paid, skip
        
        # Calculate days outstanding from invoice date
        days = (as_of_date - invoice.invoice_date).days
        
        # Classify into bucket
        bucket = _classify_bucket(days)
        
        # Add to total buckets
        total_buckets[bucket] += outstanding
        
        # Add to party buckets
        party_id = str(invoice.party.id)
        if party_id not in party_aging:
            party_aging[party_id] = {
                "party_id": party_id,
                "party_name": invoice.party.name,
                "party_code": invoice.party.code,
                "total": Decimal('0'),
                "buckets": {
                    "0-30": Decimal('0'),
                    "31-60": Decimal('0'),
                    "61-90": Decimal('0'),
                    "90+": Decimal('0')
                },
                "invoices": []  # Detailed invoice list
            }
        
        party_aging[party_id]["total"] += outstanding
        party_aging[party_id]["buckets"][bucket] += outstanding
        party_aging[party_id]["invoices"].append({
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date.isoformat(),
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "days_outstanding": days,
            "bucket": bucket,
            "total_amount": str(money(invoice.grand_total)),
            "amount_received": str(money(invoice.amount_received or 0)),
            "outstanding": str(outstanding)
        })
    
    # Calculate total outstanding
    total_outstanding = sum(total_buckets.values(), Decimal('0'))
    
    # Sort parties by total outstanding (descending)
    parties_list = sorted(
        party_aging.values(),
        key=lambda x: x["total"],
        reverse=True
    )
    
    # Convert Decimals to strings for JSON serialization
    for party in parties_list:
        party["total"] = str(party["total"])
        party["buckets"] = {k: str(v) for k, v in party["buckets"].items()}
    
    result = {
        "company_id": str(company.id),
        "company_name": company.name,
        "total_outstanding": str(total_outstanding),
        "buckets": {k: str(v) for k, v in total_buckets.items()},
        "parties": parties_list,
        "as_of_date": as_of_date.isoformat(),
        "generated_at": timezone.now().isoformat()
    }
    
    return result


def _classify_bucket(days: int) -> str:
    """
    Classify number of days into aging bucket.
    
    Args:
        days: Number of days outstanding
        
    Returns:
        Bucket name: "0-30", "31-60", "61-90", or "90+"
    """
    if days <= 30:
        return "0-30"
    elif days <= 60:
        return "31-60"
    elif days <= 90:
        return "61-90"
    else:
        return "90+"


def generate_and_cache_aging(company, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Generate aging report and cache it.
    
    This function is called by Celery task daily to pre-generate reports.
    Cached reports can be retrieved quickly via API.
    
    Args:
        company: Company instance
        as_of_date: Calculate aging as of this date (default: today)
        
    Returns:
        Aging report dict (same as aging_for_company)
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()
    
    # Generate report
    report = aging_for_company(company, as_of_date)
    
    # Cache for 24 hours
    cache_key = f"aging_report:{company.id}:{as_of_date.isoformat()}"
    cache.set(cache_key, report, timeout=86400)  # 24 hours
    
    return report


def get_cached_aging(company, as_of_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached aging report.
    
    If no cached report exists, returns None.
    API can then decide to generate on-demand or return error.
    
    Args:
        company: Company instance
        as_of_date: Date of report (default: today)
        
    Returns:
        Cached aging report dict or None
    """
    if as_of_date is None:
        as_of_date = timezone.now().date()
    
    cache_key = f"aging_report:{company.id}:{as_of_date.isoformat()}"
    return cache.get(cache_key)


def aging_summary(company, as_of_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Get summary aging statistics (without detailed party breakdown).
    
    Faster than full aging report. Useful for dashboards.
    
    Args:
        company: Company instance
        as_of_date: Calculate aging as of this date (default: today)
        
    Returns:
        Dict with total_outstanding and buckets only
    """
    from apps.invoice.models import Invoice
    
    if as_of_date is None:
        as_of_date = timezone.now().date()
    
    # Get all posted/partially paid invoices
    invoices = Invoice.objects.filter(
        company=company,
        status__in=['POSTED', 'PARTIALLY_PAID']
    )
    
    # Initialize buckets
    buckets = {
        "0-30": Decimal('0'),
        "31-60": Decimal('0'),
        "61-90": Decimal('0'),
        "90+": Decimal('0')
    }
    
    for invoice in invoices:
        outstanding = money(invoice.grand_total) - money(invoice.amount_received or 0)
        
        if outstanding <= 0:
            continue
        
        days = (as_of_date - invoice.invoice_date).days
        bucket = _classify_bucket(days)
        buckets[bucket] += outstanding
    
    total_outstanding = sum(buckets.values(), Decimal('0'))
    
    return {
        "company_id": str(company.id),
        "total_outstanding": str(total_outstanding),
        "buckets": {k: str(v) for k, v in buckets.items()},
        "as_of_date": as_of_date.isoformat()
    }


def overdue_parties(company, days_threshold: int = 30) -> List[Dict[str, Any]]:
    """
    Get list of parties with overdue amounts beyond threshold.
    
    Useful for collections team to prioritize follow-ups.
    
    Args:
        company: Company instance
        days_threshold: Only include parties with invoices older than this (default: 30)
        
    Returns:
        List of dicts with party info and overdue amounts
        
    Example:
        [
            {
                "party_id": "...",
                "party_name": "ABC Retailers",
                "overdue_amount": "50000.00",
                "oldest_invoice_days": 75,
                "invoice_count": 3
            }
        ]
    """
    from apps.invoice.models import Invoice
    from django.db.models import Count
    
    today = timezone.now().date()
    threshold_date = today - timedelta(days=days_threshold)
    
    # Get invoices older than threshold
    invoices = Invoice.objects.filter(
        company=company,
        status__in=['POSTED', 'PARTIALLY_PAID'],
        invoice_date__lt=threshold_date
    ).select_related('party')
    
    # Group by party
    party_data = {}
    
    for invoice in invoices:
        outstanding = money(invoice.grand_total) - money(invoice.amount_received or 0)
        
        if outstanding <= 0:
            continue
        
        party_id = str(invoice.party.id)
        days = (today - invoice.invoice_date).days
        
        if party_id not in party_data:
            party_data[party_id] = {
                "party_id": party_id,
                "party_name": invoice.party.name,
                "party_code": invoice.party.code,
                "overdue_amount": Decimal('0'),
                "oldest_invoice_days": 0,
                "invoice_count": 0
            }
        
        party_data[party_id]["overdue_amount"] += outstanding
        party_data[party_id]["oldest_invoice_days"] = max(
            party_data[party_id]["oldest_invoice_days"],
            days
        )
        party_data[party_id]["invoice_count"] += 1
    
    # Convert to list and sort by overdue amount
    result = sorted(
        party_data.values(),
        key=lambda x: x["overdue_amount"],
        reverse=True
    )
    
    # Convert Decimals to strings
    for party in result:
        party["overdue_amount"] = str(party["overdue_amount"])
    
    return result
