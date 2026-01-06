"""
Selector pattern for Accounting app.

Selectors encapsulate all data retrieval logic with proper company scoping.
Never use Model.objects.get(id=...) directly - always use selectors.
"""
from django.shortcuts import get_object_or_404
from django.db.models import QuerySet, Sum
from apps.accounting.models import (
    Ledger, LedgerBalance, AccountGroup
)
from apps.company.models import Company, FinancialYear
from typing import Optional
from decimal import Decimal


def get_ledger(company: Company, ledger_id: int) -> Ledger:
    """
    Retrieve a single ledger with company validation.
    
    Args:
        company: Company instance for scoping
        ledger_id: Ledger ID
    
    Returns:
        Ledger instance
    
    Raises:
        Http404: If ledger not found or belongs to different company
    """
    return get_object_or_404(
        Ledger.objects.select_related('group'),
        company=company,
        id=ledger_id
    )


def list_ledgers(
    company: Company,
    group_id: Optional[int] = None,
    active_only: bool = True
) -> QuerySet:
    """
    List ledgers for a company with optional filters.
    
    Args:
        company: Company instance for scoping
        group_id: Optional account group filter
        active_only: If True, only return active ledgers
    
    Returns:
        QuerySet of ledgers
    """
    qs = Ledger.objects.filter(company=company).select_related('group')
    
    if group_id:
        qs = qs.filter(group_id=group_id)
    
    if active_only:
        qs = qs.filter(is_active=True)
    
    return qs.order_by('name')


def get_ledger_balance(
    company: Company,
    ledger_id: int,
    financial_year_id: int
) -> Decimal:
    """
    Get current balance for a ledger in a financial year.
    
    Args:
        company: Company instance for scoping
        ledger_id: Ledger ID
        financial_year_id: Financial year ID
    
    Returns:
        Decimal balance (positive for DR nature, negative for CR nature)
    """
    # Verify ledger belongs to company
    ledger = get_ledger(company, ledger_id)
    
    try:
        balance = LedgerBalance.objects.get(
            company=company,
            ledger_id=ledger_id,
            financial_year_id=financial_year_id
        )
        return balance.balance
    except LedgerBalance.DoesNotExist:
        return Decimal('0.00')


def ledger_balance_detailed(company: Company, ledger: Ledger, financial_year_id: int) -> dict:
    """
    Get detailed balance information for a ledger.
    
    Args:
        company: Company instance for scoping
        ledger: Ledger instance
        financial_year_id: Financial year ID
    
    Returns:
        Dict with ledger_id, name, balance_dr, balance_cr, net
    """
    try:
        bal = LedgerBalance.objects.get(
            company=company,
            ledger=ledger,
            financial_year_id=financial_year_id
        )
        balance_dr = bal.balance if bal.balance > 0 else Decimal('0.00')
        balance_cr = abs(bal.balance) if bal.balance < 0 else Decimal('0.00')
    except LedgerBalance.DoesNotExist:
        balance_dr = Decimal('0.00')
        balance_cr = Decimal('0.00')
    
    return {
        'ledger_id': str(ledger.id),
        'name': ledger.name,
        'balance_dr': balance_dr,
        'balance_cr': balance_cr,
        'net': balance_dr - balance_cr
    }
    # Verify ledger belongs to company
    ledger = get_ledger(company, ledger_id)
    
    try:
        balance = LedgerBalance.objects.get(
            company=company,
            ledger_id=ledger_id,
            financial_year_id=financial_year_id
        )
        return balance.balance
    except LedgerBalance.DoesNotExist:
        return Decimal('0.00')


def get_account_group(company: Company, group_id: int) -> AccountGroup:
    """
    Retrieve an account group with company validation.
    
    Args:
        company: Company instance for scoping
        group_id: Account group ID
    
    Returns:
        AccountGroup instance
    
    Raises:
        Http404: If group not found or belongs to different company
    """
    return get_object_or_404(
        AccountGroup.objects.all(),
        company=company,
        id=group_id
    )


def list_account_groups(
    company: Company,
    nature: Optional[str] = None
) -> QuerySet:
    """
    List account groups for a company.
    
    Args:
        company: Company instance for scoping
        nature: Optional nature filter ('ASSET', 'LIABILITY', 'INCOME', 'EXPENSE')
    
    Returns:
        QuerySet of account groups
    """
    qs = AccountGroup.objects.filter(company=company)
    
    if nature:
        qs = qs.filter(nature=nature)
    
    return qs.order_by('path')


def get_financial_year(company: Company, year_id: int) -> FinancialYear:
    """
    Retrieve a financial year with company validation.
    
    Args:
        company: Company instance for scoping
        year_id: Financial year ID
    
    Returns:
        FinancialYear instance
    
    Raises:
        Http404: If year not found or belongs to different company
    """
    return get_object_or_404(
        FinancialYear.objects.all(),
        company=company,
        id=year_id
    )


def get_active_financial_year(company: Company) -> Optional[FinancialYear]:
    """
    Get the currently active financial year for a company.
    
    Args:
        company: Company instance for scoping
    
    Returns:
        FinancialYear instance or None if no active year
    """
    try:
        return FinancialYear.objects.get(
            company=company,
            is_closed=False
        )
    except FinancialYear.DoesNotExist:
        return None
    except FinancialYear.MultipleObjectsReturned:
        # Return the most recent if multiple active years
        return FinancialYear.objects.filter(
            company=company,
            is_closed=False
        ).order_by('-start_date').first()


def get_trial_balance(
    company: Company,
    financial_year_id: int
) -> QuerySet:
    """
    Get trial balance (all ledger balances) for a financial year.
    
    Args:
        company: Company instance for scoping
        financial_year_id: Financial year ID
    
    Returns:
        QuerySet of LedgerBalance records
    """
    return LedgerBalance.objects.filter(
        company=company,
        financial_year_id=financial_year_id
    ).select_related('ledger', 'ledger__group').order_by('ledger__name')


def get_ledgers_by_nature(
    company: Company,
    nature: str,
    active_only: bool = True
) -> QuerySet:
    """
    Get all ledgers of a specific nature (ASSET, LIABILITY, INCOME, EXPENSE).
    
    Args:
        company: Company instance for scoping
        nature: Account nature
        active_only: If True, only return active ledgers
    
    Returns:
        QuerySet of ledgers
    """
    qs = Ledger.objects.filter(
        company=company,
        group__nature=nature
    ).select_related('group')
    
    if active_only:
        qs = qs.filter(is_active=True)
    
    return qs.order_by('name')
