"""
Test Financial Year Closing and Lock Enforcement
Tests that closed FY blocks posting and company lock enforcement
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.company.models import (
    Company, Currency, FinancialYear, CompanyFeature, Sequence
)
from apps.voucher.models import Voucher, VoucherType, VoucherLine
from apps.accounting.models import AccountGroup, Ledger
from core.services.posting import (
    PostingService, FinancialYearClosed, CompanyLocked
)

User = get_user_model()


class FinancialYearCloseTest(TestCase):
    """Test financial year closing enforcement"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR",
            name="Indian Rupee",
            symbol="₹",
            decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="FYTEST",
            name="FY Test Company",
            legal_name="FY Test Company Ltd",
            company_type="PRIVATE_LIMITED",
            timezone="Asia/Kolkata",
            language="en",
            base_currency=self.currency
        )
        
        # Create closed financial year
        self.fy_closed = FinancialYear.objects.create(
            company=self.company,
            name="2023-24",
            start_date=date(2023, 4, 1),
            end_date=date(2024, 3, 31),
            is_current=False,
            is_closed=True
        )
        
        # Create open financial year
        self.fy_open = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        self.user = User.objects.create_user(
            username="fyuser",
            password="test123"
        )
        
        # Create account structure
        self.asset_group = AccountGroup.objects.create(
            company=self.company,
            name="Current Assets",
            code="CA",
            nature="ASSET",
            report_type="BS",
            path="/CA"
        )
        
        self.income_group = AccountGroup.objects.create(
            company=self.company,
            name="Income",
            code="INC",
            nature="INCOME",
            report_type="PL",
            path="/INC"
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company,
            code="CASH001",
            name="Cash",
            group=self.asset_group,
            account_type="CASH",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy_open
        )
        
        self.sales_ledger = Ledger.objects.create(
            company=self.company,
            code="SALES001",
            name="Sales",
            group=self.income_group,
            account_type="INCOME",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy_open
        )
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name="Journal",
            code="JV",
            category="JOURNAL",
            is_accounting=True
        )
        
        # Create sequence for auto-numbering
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:JV:{self.fy_open.id}",
            prefix="JV",
            last_value=0
        )
    
    def test_posting_blocked_when_fy_closed(self):
        """Test that posting is blocked when financial year is closed"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy_closed,
            voucher_number="JV001",
            date=date(2023, 6, 1),  # Date within closed FY
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=self.cash_ledger,
            entry_type="DR",
            amount=Decimal("1000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.sales_ledger,
            entry_type="CR",
            amount=Decimal("1000.00")
        )
        
        service = PostingService()
        with self.assertRaises(FinancialYearClosed):
            service.post_voucher(voucher.id, self.user)
        
        # Voucher should remain in DRAFT
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "DRAFT")
    
    def test_posting_allowed_when_fy_open(self):
        """Test that posting is allowed when financial year is open"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy_open,
            voucher_number="JV002",
            date=date(2024, 6, 1),  # Date within open FY
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=self.cash_ledger,
            entry_type="DR",
            amount=Decimal("2000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.sales_ledger,
            entry_type="CR",
            amount=Decimal("2000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "POSTED")
    
    def test_multiple_fy_constraint(self):
        """Test that only one financial year can be current per company"""
        from django.db import IntegrityError
        
        # Try to create another current FY
        with self.assertRaises(IntegrityError):
            FinancialYear.objects.create(
                company=self.company,
                name="2025-26",
                start_date=date(2025, 4, 1),
                end_date=date(2026, 3, 31),
                is_current=True,  # Conflict with existing current FY
                is_closed=False
            )
    
    def test_fy_date_validation(self):
        """Test that FY start date must be before end date"""
        from django.db import IntegrityError
        
        # Try to create FY with start_date > end_date
        with self.assertRaises(IntegrityError):
            FinancialYear.objects.create(
                company=self.company,
                name="Invalid FY",
                start_date=date(2026, 3, 31),
                end_date=date(2025, 4, 1),  # End before start
                is_current=False,
                is_closed=False
            )


class CompanyLockTest(TestCase):
    """Test company lock (accounting freeze) enforcement"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="LOCK01", name="Lock Test Co", legal_name="Lock Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="lockuser", password="test123")
        
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company, code="BANK", name="Bank",
            group=self.asset_group, account_type="BANK",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company, name="Payment", code="PAY",
            category="PAYMENT", is_accounting=True
        )
        
        # Create sequence for auto-numbering
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:PAY:{self.fy.id}",
            prefix="PAY",
            last_value=0
        )
    
    def test_posting_blocked_when_company_locked(self):
        """Test that posting is blocked when company is locked"""
        # Create and lock company features
        CompanyFeature.objects.create(
            company=self.company,
            accounting_enabled=True,
            inventory_enabled=True,
            locked=True  # Accounting freeze
        )
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=5,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("5000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=6,
            ledger=self.bank_ledger, entry_type="CR",
            amount=Decimal("5000.00")
        )
        
        service = PostingService()
        with self.assertRaises(CompanyLocked):
            service.post_voucher(voucher.id, self.user)
    
    def test_posting_allowed_when_company_unlocked(self):
        """Test that posting is allowed when company is not locked"""
        # Create unlocked company features
        CompanyFeature.objects.create(
            company=self.company,
            accounting_enabled=True,
            inventory_enabled=True,
            locked=False
        )
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY002",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=7,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("3000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=8,
            ledger=self.bank_ledger, entry_type="CR",
            amount=Decimal("3000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "POSTED")
    
    def test_posting_allowed_when_no_company_features(self):
        """Test that posting is allowed when no CompanyFeature record exists"""
        # Don't create CompanyFeature (implies not locked)
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY003",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=9,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("7000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=10,
            ledger=self.bank_ledger, entry_type="CR",
            amount=Decimal("7000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "POSTED")


class CompanyConfigurationTest(TestCase):
    """Test company configuration and multi-tenancy"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="USD", name="US Dollar", symbol="$", decimal_places=2
        )
    
    def test_company_creation(self):
        """Test company creation with all required fields"""
        company = Company.objects.create(
            code="COMP01",
            name="Test Company",
            legal_name="Test Company Inc.",
            company_type="PRIVATE_LIMITED",
            timezone="America/New_York",
            language="en",
            base_currency=self.currency
        )
        
        self.assertEqual(company.code, "COMP01")
        self.assertTrue(company.is_active)
        self.assertFalse(company.is_deleted)
    
    def test_company_code_uniqueness(self):
        """Test that company codes must be unique"""
        from django.db import IntegrityError
        
        Company.objects.create(
            code="UNIQUE01", name="Company One", legal_name="Company One Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        with self.assertRaises(IntegrityError):
            Company.objects.create(
                code="UNIQUE01",  # Duplicate code
                name="Company Two",
                legal_name="Company Two Ltd",
                company_type="PRIVATE_LIMITED",
                timezone="UTC",
                language="en",
                base_currency=self.currency
            )
    
    def test_currency_creation(self):
        """Test currency master creation"""
        currency = Currency.objects.create(
            code="EUR",
            name="Euro",
            symbol="€",
            decimal_places=2
        )
        
        self.assertEqual(currency.code, "EUR")
        self.assertEqual(currency.decimal_places, 2)
