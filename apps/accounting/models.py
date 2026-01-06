"""
Accounting models for ERP system.
Models: AccountGroup, Ledger, TaxLedger, CostCenter, LedgerBalance
"""
from django.db import models
from django.core.exceptions import ValidationError
from core.models import BaseModel, CompanyScopedModel


class AccountNature(models.TextChoices):
    """Enum for account nature"""
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'
    INCOME = 'INCOME', 'Income'
    EXPENSE = 'EXPENSE', 'Expense'


class ReportType(models.TextChoices):
    """Enum for financial report types"""
    BS = 'BS', 'Balance Sheet'
    PL = 'PL', 'Profit & Loss'


class AccountGroup(CompanyScopedModel):
    """
    Hierarchical account group structure.
    Provides chart of accounts organization.
    """
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, db_index=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children'
    )
    nature = models.CharField(
        max_length=20,
        choices=AccountNature.choices
    )
    report_type = models.CharField(
        max_length=10,
        choices=ReportType.choices
    )
    path = models.CharField(
        max_length=255,
        help_text="Materialized path for hierarchy traversal"
    )

    class Meta:
        verbose_name_plural = "Account Groups"
        unique_together = ("company", "code")
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'parent']),
            models.Index(fields=['company', 'nature']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class AccountType(models.TextChoices):
    """Enum for ledger account types"""
    BANK = 'BANK', 'Bank Account'
    CASH = 'CASH', 'Cash Account'
    CUSTOMER = 'CUSTOMER', 'Customer'
    SUPPLIER = 'SUPPLIER', 'Supplier'
    EMPLOYEE = 'EMPLOYEE', 'Employee'
    TAX = 'TAX', 'Tax'
    EXPENSE = 'EXPENSE', 'Expense'
    INCOME = 'INCOME', 'Income'
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'


class BalanceType(models.TextChoices):
    """Enum for opening balance type"""
    DR = 'DR', 'Debit'
    CR = 'CR', 'Credit'


class Ledger(CompanyScopedModel):
    """
    Ledger accounts (leaf level in chart of accounts).
    All financial transactions post to ledgers.
    """
    code = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=255)
    group = models.ForeignKey(
        AccountGroup,
        on_delete=models.PROTECT,
        related_name='ledgers'
    )
    account_type = models.CharField(
        max_length=30,
        choices=AccountType.choices
    )
    
    # Opening balance (kept for UI, but should create opening voucher)
    opening_balance = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=0,
        help_text="Opening balance amount"
    )
    opening_balance_type = models.CharField(
        max_length=2,
        choices=BalanceType.choices,
        default=BalanceType.DR
    )
    opening_balance_fy = models.ForeignKey(
        "company.FinancialYear",
        on_delete=models.PROTECT,
        related_name='ledger_opening_balances',
        help_text="Financial year for opening balance"
    )
    
    # Ledger behavior flags
    is_bill_wise = models.BooleanField(
        default=False,
        help_text="Enable bill-by-bill tracking (for receivables/payables)"
    )
    is_cost_center_applicable = models.BooleanField(
        default=False,
        help_text="Require cost center on entries"
    )
    requires_reconciliation = models.BooleanField(
        default=False,
        help_text="Enable bank reconciliation"
    )
    is_system = models.BooleanField(
        default=False,
        help_text="System-generated ledger (cannot be deleted)"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Ledgers"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'account_type']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class TaxType(models.TextChoices):
    """Enum for tax types"""
    GST = 'GST', 'GST'
    CGST = 'CGST', 'Central GST'
    SGST = 'SGST', 'State GST'
    IGST = 'IGST', 'Integrated GST'
    VAT = 'VAT', 'VAT'
    SERVICE_TAX = 'SERVICE_TAX', 'Service Tax'
    TDS = 'TDS', 'TDS'
    TCS = 'TCS', 'TCS'


class TaxDirection(models.TextChoices):
    """Enum for tax direction"""
    PAYABLE = 'PAYABLE', 'Tax Payable (Output)'
    RECEIVABLE = 'RECEIVABLE', 'Tax Receivable (Input)'


class TaxLedger(BaseModel):
    """
    Tax-specific configuration for ledgers.
    Links accounting ledgers to tax rules.
    """
    ledger = models.OneToOneField(
        Ledger,
        on_delete=models.CASCADE,
        related_name='tax_config'
    )
    tax_type = models.CharField(
        max_length=20,
        choices=TaxType.choices
    )
    rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Tax rate percentage"
    )
    tax_direction = models.CharField(
        max_length=10,
        choices=TaxDirection.choices
    )
    effective_from = models.DateField()

    class Meta:
        verbose_name_plural = "Tax Ledgers"

    def __str__(self):
        return f"{self.ledger.name} - {self.tax_type} @ {self.rate}%"


class CostCenter(CompanyScopedModel):
    """
    Cost center / profit center for dimensional analysis.
    Allows tracking expenses and revenue by department, project, branch, etc.
    """
    code = models.CharField(max_length=50, db_index=True)
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        verbose_name_plural = "Cost Centers"
        indexes = [
            models.Index(fields=['company', 'code']),
            models.Index(fields=['company', 'is_active']),
            models.Index(fields=['company', 'created_at']),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class LedgerBalance(CompanyScopedModel):
    """
    Cached ledger running balance per financial year.
    Source of truth is VoucherLine. This table provides fast balance queries
    for statements, credit checks, and financial reports.
    
    Maintained per-FY for easier year-end rollover and historical reporting.
    Updated transactionally within posting service using select_for_update().
    """
    ledger = models.ForeignKey(
        "accounting.Ledger",
        on_delete=models.PROTECT,
        related_name='balances'
    )
    financial_year = models.ForeignKey(
        "company.FinancialYear",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ledger_balances',
        help_text="Null means all-time balance (for non-FY specific queries)"
    )

    balance_dr = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=0,
        help_text="Total debit balance"
    )
    balance_cr = models.DecimalField(
        max_digits=24,
        decimal_places=2,
        default=0,
        help_text="Total credit balance"
    )

    last_posted_voucher = models.ForeignKey(
        "voucher.Voucher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='balance_updates',
        help_text="Last posted voucher that updated this balance (for idempotency)"
    )
    last_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "ledger", "financial_year")
        verbose_name_plural = "Ledger Balances"
        indexes = [
            models.Index(fields=['company', 'ledger']),
            models.Index(fields=['company', 'financial_year', 'ledger']),
            models.Index(fields=['company', 'ledger', 'financial_year']),
            models.Index(fields=['company', 'created_at']),
        ]

    def net(self):
        """
        Net balance = balance_dr - balance_cr.
        Positive = Debit balance (Asset/Expense increase)
        Negative = Credit balance (Liability/Income/Equity increase)
        """
        return self.balance_dr - self.balance_cr

    def __str__(self):
        fy_info = f" FY:{self.financial_year.name}" if self.financial_year else " (All-time)"
        net_balance = self.net()
        balance_type = "DR" if net_balance >= 0 else "CR"
        return f"{self.ledger.code}{fy_info} {abs(net_balance):.2f} {balance_type}"
