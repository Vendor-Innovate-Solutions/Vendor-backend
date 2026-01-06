"""
Financial reporting services.

Generate financial reports from cached LedgerBalance data:
- Trial Balance
- Profit & Loss Statement
- Balance Sheet
"""
from decimal import Decimal
from typing import Dict, List
from apps.accounting.models import LedgerBalance, AccountGroup
from apps.company.models import Company, FinancialYear


def trial_balance(company: Company, financial_year: FinancialYear) -> Dict:
    """
    Generate trial balance report.
    
    Trial balance shows all ledgers with their debit and credit balances.
    Total debits should equal total credits.
    
    Args:
        company: Company instance for scoping
        financial_year: Financial year for the report
    
    Returns:
        Dict with rows, total_dr, total_cr, difference
    """
    balances = LedgerBalance.objects.filter(
        company=company,
        financial_year=financial_year
    ).select_related('ledger', 'ledger__group').order_by('ledger__name')
    
    rows = []
    total_dr = Decimal('0.00')
    total_cr = Decimal('0.00')
    
    for bal in balances:
        # Convert balance to DR/CR format
        balance_dr = bal.balance if bal.balance > 0 else Decimal('0.00')
        balance_cr = abs(bal.balance) if bal.balance < 0 else Decimal('0.00')
        
        rows.append({
            'ledger_id': str(bal.ledger.id),
            'ledger': bal.ledger.name,
            'group': bal.ledger.group.name,
            'dr': float(balance_dr),
            'cr': float(balance_cr),
        })
        
        total_dr += balance_dr
        total_cr += balance_cr
    
    return {
        'rows': rows,
        'total_dr': float(total_dr),
        'total_cr': float(total_cr),
        'difference': float(total_dr - total_cr),
        'financial_year': financial_year.name,
        'is_balanced': abs(total_dr - total_cr) < Decimal('0.01')  # Allow 1 paisa tolerance
    }


def profit_and_loss(company: Company, financial_year: FinancialYear) -> Dict:
    """
    Generate Profit & Loss statement.
    
    P&L = Income - Expenses = Net Profit/Loss
    
    Args:
        company: Company instance for scoping
        financial_year: Financial year for the report
    
    Returns:
        Dict with income, expense, net_profit, income_details, expense_details
    """
    balances = LedgerBalance.objects.filter(
        company=company,
        financial_year=financial_year
    ).select_related('ledger', 'ledger__group')
    
    income_total = Decimal('0.00')
    expense_total = Decimal('0.00')
    income_details = []
    expense_details = []
    
    for bal in balances:
        nature = bal.ledger.group.nature
        
        if nature == 'INCOME':
            # Income has CR balance normally
            amount = abs(bal.balance) if bal.balance < 0 else bal.balance
            income_total += amount
            income_details.append({
                'ledger_id': str(bal.ledger.id),
                'ledger': bal.ledger.name,
                'amount': float(amount)
            })
        
        elif nature == 'EXPENSE':
            # Expense has DR balance normally
            amount = bal.balance if bal.balance > 0 else abs(bal.balance)
            expense_total += amount
            expense_details.append({
                'ledger_id': str(bal.ledger.id),
                'ledger': bal.ledger.name,
                'amount': float(amount)
            })
    
    net_profit = income_total - expense_total
    
    return {
        'income': float(income_total),
        'expense': float(expense_total),
        'net_profit': float(net_profit),
        'is_profit': net_profit > 0,
        'income_details': income_details,
        'expense_details': expense_details,
        'financial_year': financial_year.name
    }


def balance_sheet(company: Company, financial_year: FinancialYear) -> Dict:
    """
    Generate Balance Sheet.
    
    Balance Sheet equation: Assets = Liabilities + Equity
    
    Args:
        company: Company instance for scoping
        financial_year: Financial year for the report
    
    Returns:
        Dict with assets, liabilities, equity, balance_check
    """
    balances = LedgerBalance.objects.filter(
        company=company,
        financial_year=financial_year
    ).select_related('ledger', 'ledger__group')
    
    assets_total = Decimal('0.00')
    liabilities_total = Decimal('0.00')
    equity_total = Decimal('0.00')
    
    assets_details = []
    liabilities_details = []
    equity_details = []
    
    for bal in balances:
        nature = bal.ledger.group.nature
        
        if nature == 'ASSET':
            # Assets have DR balance normally
            amount = bal.balance if bal.balance > 0 else abs(bal.balance)
            assets_total += amount
            assets_details.append({
                'ledger_id': str(bal.ledger.id),
                'ledger': bal.ledger.name,
                'amount': float(amount)
            })
        
        elif nature == 'LIABILITY':
            # Liabilities have CR balance normally
            amount = abs(bal.balance) if bal.balance < 0 else bal.balance
            liabilities_total += amount
            liabilities_details.append({
                'ledger_id': str(bal.ledger.id),
                'ledger': bal.ledger.name,
                'amount': float(amount)
            })
        
        elif nature == 'EQUITY':
            # Equity has CR balance normally
            amount = abs(bal.balance) if bal.balance < 0 else bal.balance
            equity_total += amount
            equity_details.append({
                'ledger_id': str(bal.ledger.id),
                'ledger': bal.ledger.name,
                'amount': float(amount)
            })
    
    # Balance check: Assets should equal Liabilities + Equity
    balance_check = assets_total - (liabilities_total + equity_total)
    
    return {
        'assets': float(assets_total),
        'liabilities': float(liabilities_total),
        'equity': float(equity_total),
        'balance_check': float(balance_check),
        'is_balanced': abs(balance_check) < Decimal('0.01'),  # Allow 1 paisa tolerance
        'assets_details': assets_details,
        'liabilities_details': liabilities_details,
        'equity_details': equity_details,
        'financial_year': financial_year.name
    }


def ledger_statement(
    company: Company,
    ledger_id: int,
    financial_year: FinancialYear,
    start_date=None,
    end_date=None
) -> Dict:
    """
    Generate ledger statement (transaction history).
    
    Shows all voucher lines affecting this ledger with running balance.
    
    Args:
        company: Company instance for scoping
        ledger_id: Ledger ID
        financial_year: Financial year for the report
        start_date: Optional start date filter
        end_date: Optional end date filter
    
    Returns:
        Dict with opening_balance, transactions, closing_balance
    """
    from apps.accounting.models import Ledger
    from apps.voucher.models import VoucherLine
    
    # Get ledger
    ledger = Ledger.objects.get(company=company, id=ledger_id)
    
    # Get opening balance
    try:
        balance_obj = LedgerBalance.objects.get(
            company=company,
            ledger_id=ledger_id,
            financial_year=financial_year
        )
        opening_balance = balance_obj.opening_balance
        current_balance = balance_obj.balance
    except LedgerBalance.DoesNotExist:
        opening_balance = Decimal('0.00')
        current_balance = Decimal('0.00')
    
    # Get transactions
    transactions_qs = VoucherLine.objects.filter(
        voucher__company=company,
        ledger_id=ledger_id,
        voucher__financial_year=financial_year,
        voucher__is_posted=True
    ).select_related('voucher').order_by('voucher__date', 'voucher__voucher_number')
    
    if start_date:
        transactions_qs = transactions_qs.filter(voucher__date__gte=start_date)
    if end_date:
        transactions_qs = transactions_qs.filter(voucher__date__lte=end_date)
    
    # Build transaction list with running balance
    transactions = []
    running_balance = opening_balance
    
    for line in transactions_qs:
        if line.entry_type == 'DR':
            running_balance += line.amount
        else:  # CR
            running_balance -= line.amount
        
        transactions.append({
            'date': line.voucher.date.isoformat(),
            'voucher_number': line.voucher.voucher_number,
            'voucher_type': line.voucher.voucher_type,
            'description': line.description or '',
            'debit': float(line.amount) if line.entry_type == 'DR' else 0.0,
            'credit': float(line.amount) if line.entry_type == 'CR' else 0.0,
            'balance': float(running_balance)
        })
    
    return {
        'ledger_id': str(ledger.id),
        'ledger_name': ledger.name,
        'opening_balance': float(opening_balance),
        'transactions': transactions,
        'closing_balance': float(current_balance),
        'financial_year': financial_year.name
    }
