"""
Common test fixtures and utilities for all tests.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger, AccountNature, ReportType
from decimal import Decimal
from datetime import date, timedelta

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common setup for all tests."""
    
    def setUp(self):
        """Set up common test objects."""
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_internal_user=True
        )
        
        # Create currency
        self.currency = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹',
            decimal_places=2
        )
        
        # Create company
        self.company = Company.objects.create(
            code='TEST001',
            name='Test Company',
            legal_name='Test Company Private Limited',
            base_currency=self.currency,
            is_active=True
        )
        
        # Create financial year
        today = date.today()
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name=f'{today.year}-{today.year + 1}',
            start_date=date(today.year, 4, 1),
            end_date=date(today.year + 1, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        # Create account groups
        self.asset_group = AccountGroup.objects.create(
            company=self.company,
            code='ASSETS',
            name='Assets',
            nature=AccountNature.ASSET,
            report_type=ReportType.BS,
            path='/ASSETS/'
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company,
            code='LIAB',
            name='Liabilities',
            nature=AccountNature.LIABILITY,
            report_type=ReportType.BS,
            path='/LIAB/'
        )
        
        self.income_group = AccountGroup.objects.create(
            company=self.company,
            code='INCOME',
            name='Income',
            nature=AccountNature.INCOME,
            report_type=ReportType.PL,
            path='/INCOME/'
        )
        
        self.expense_group = AccountGroup.objects.create(
            company=self.company,
            code='EXPENSE',
            name='Expenses',
            nature=AccountNature.EXPENSE,
            report_type=ReportType.PL,
            path='/EXPENSE/'
        )
        
        # Create common sequences for auto-numbering (compound keys)
        common_sequence_keys = ['JV', 'PAY', 'RCP', 'SALES', 'PURCHASE', 'VOUCHER']
        for code in common_sequence_keys:
            compound_key = f"{self.company.id}:{code}:{self.fy.id}"
            Sequence.objects.get_or_create(
                company=self.company,
                key=compound_key,
                defaults={'prefix': code, 'last_value': 0}
            )
    
    def create_ledger(self, code, name, account_type, group=None):
        """Helper to create a ledger with required fields."""
        if group is None:
            group = self.asset_group
            
        return Ledger.objects.create(
            company=self.company,
            code=code,
            name=name,
            group=group,
            account_type=account_type,
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            is_active=True
        )
