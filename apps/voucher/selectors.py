"""
Selector pattern for Voucher app.

Selectors encapsulate all data retrieval logic with proper company scoping.
Never use Model.objects.get(id=...) directly - always use selectors.
"""
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet
from apps.voucher.models import Voucher, VoucherLine
from apps.company.models import Company
from typing import Optional


def get_voucher(company: Company, voucher_id: int) -> Voucher:
    """
    Retrieve a single voucher with company validation.
    
    Args:
        company: Company instance for scoping
        voucher_id: Voucher ID
    
    Returns:
        Voucher instance
    
    Raises:
        Http404: If voucher not found or belongs to different company
    """
    return get_object_or_404(
        Voucher.objects.select_related('financial_year', 'reversal_user'),
        company=company,
        id=voucher_id
    )


def list_vouchers(
    company: Company,
    voucher_type: Optional[str] = None,
    filters: dict = None
) -> QuerySet:
    """
    List vouchers for a company with optional filters.
    
    Args:
        company: Company instance for scoping
        voucher_type: Optional voucher type filter
        filters: Optional dict of filter parameters
    
    Returns:
        QuerySet of vouchers
    """
    qs = Voucher.objects.filter(company=company).select_related(
        'financial_year'
    ).prefetch_related('lines')
    
    if voucher_type:
        qs = qs.filter(voucher_type=voucher_type)
    
    if filters:
        if 'posted' in filters:
            qs = qs.filter(is_posted=filters['posted'])
        
        if 'reversed' in filters:
            qs = qs.filter(reversed_at__isnull=not filters['reversed'])
        
        if 'start_date' in filters:
            qs = qs.filter(date__gte=filters['start_date'])
        
        if 'end_date' in filters:
            qs = qs.filter(date__lte=filters['end_date'])
    
    return qs.order_by('-date', '-voucher_number')


def get_voucher_lines(company: Company, voucher_id: int) -> QuerySet:
    """
    Get all lines for a voucher with company validation.
    
    Args:
        company: Company instance for scoping
        voucher_id: Voucher ID
    
    Returns:
        QuerySet of voucher lines
    
    Raises:
        Http404: If voucher not found or belongs to different company
    """
    # First verify voucher belongs to company
    voucher = get_voucher(company, voucher_id)
    
    return VoucherLine.objects.filter(voucher=voucher).select_related(
        'ledger'
    ).order_by('line_number')


def get_posted_vouchers(company: Company, financial_year_id: int) -> QuerySet:
    """
    Get all posted vouchers for a financial year.
    
    Args:
        company: Company instance for scoping
        financial_year_id: Financial year ID
    
    Returns:
        QuerySet of posted vouchers
    """
    return Voucher.objects.filter(
        company=company,
        financial_year_id=financial_year_id,
        is_posted=True
    ).order_by('date', 'voucher_number')


def get_unposted_vouchers(company: Company) -> QuerySet:
    """
    Get all unposted vouchers for a company.
    
    Args:
        company: Company instance for scoping
    
    Returns:
        QuerySet of unposted vouchers
    """
    return Voucher.objects.filter(
        company=company,
        is_posted=False
    ).order_by('-date')


def get_voucher_by_number(company: Company, voucher_number: str) -> Voucher:
    """
    Retrieve voucher by voucher number with company validation.
    
    Args:
        company: Company instance for scoping
        voucher_number: Voucher number (e.g., "JV-2024-0001")
    
    Returns:
        Voucher instance
    
    Raises:
        Http404: If voucher not found or belongs to different company
    """
    return get_object_or_404(
        Voucher.objects.select_related('financial_year'),
        company=company,
        voucher_number=voucher_number
    )


def get_reversed_vouchers(company: Company) -> QuerySet:
    """
    Get all reversed vouchers for a company.
    
    Args:
        company: Company instance for scoping
    
    Returns:
        QuerySet of reversed vouchers
    """
    return Voucher.objects.filter(
        company=company,
        reversed_at__isnull=False
    ).select_related('reversal_user').order_by('-reversed_at')
