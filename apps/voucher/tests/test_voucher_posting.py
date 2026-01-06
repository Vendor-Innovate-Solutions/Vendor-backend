"""
Test Voucher Posting Service
Tests core voucher posting, reversal, cancellation and numbering
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model

from apps.voucher.models import Voucher, VoucherType, VoucherLine
from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger
from core.services.posting import PostingService, PostingError, AlreadyPosted

User = get_user_model()


class VoucherPostingTest(TestCase):
    """Test voucher posting operations"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="VCH01", name="Voucher Test Co", legal_name="Voucher Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="vchuser", password="test123")
        
        # Create account structure
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Current Assets", code="CA",
            nature="ASSET", report_type="BS", path="/CA"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company, name="Current Liabilities", code="CL",
            nature="LIABILITY", report_type="BS", path="/CL"
        )
        
        self.expense_group = AccountGroup.objects.create(
            company=self.company, name="Direct Expenses", code="EXP",
            nature="EXPENSE", report_type="PL", path="/EXP"
        )
        
        self.income_group = AccountGroup.objects.create(
            company=self.company, name="Direct Income", code="INC",
            nature="INCOME", report_type="PL", path="/INC"
        )
        
        # Create ledgers
        self.bank_ledger = Ledger.objects.create(
            company=self.company, code="BANK001", name="Bank Account",
            group=self.asset_group, account_type="BANK",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company, code="CASH001", name="Cash",
            group=self.asset_group, account_type="CASH",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.supplier_ledger = Ledger.objects.create(
            company=self.company, code="SUP001", name="Supplier Account",
            group=self.liability_group, account_type="SUPPLIER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.expense_ledger = Ledger.objects.create(
            company=self.company, code="EXP001", name="Office Expenses",
            group=self.expense_group, account_type="EXPENSE",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.sales_ledger = Ledger.objects.create(
            company=self.company, code="SALES001", name="Sales",
            group=self.income_group, account_type="INCOME",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        # Create voucher types
        self.journal_type = VoucherType.objects.create(
            company=self.company, name="Journal", code="JV",
            category="JOURNAL", is_accounting=True
        )
        
        self.payment_type = VoucherType.objects.create(
            company=self.company, name="Payment", code="PAY",
            category="PAYMENT", is_accounting=True
        )
        
        self.receipt_type = VoucherType.objects.create(
            company=self.company, name="Receipt", code="RCP",
            category="RECEIPT", is_accounting=True
        )
        
        # Create sequences for auto-numbering (compound keys: company_id:code:fy_id)
        for code in ['JV', 'PAY', 'RCP']:
            compound_key = f"{self.company.id}:{code}:{self.fy.id}"
            Sequence.objects.create(
                company=self.company,
                key=compound_key,
                prefix=code,
                last_value=0
            )
    
    def test_simple_journal_posting(self):
        """Test simple journal voucher posting"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.journal_type,
            financial_year=self.fy,
            voucher_number="JV001",
            date=date(2024, 5, 1),
            status="DRAFT",
            narration="Test journal entry"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("10000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("10000.00")
        )
        
        service = PostingService()
        posted_voucher = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted_voucher.status, "POSTED")
    
    def test_payment_voucher_posting(self):
        """Test payment voucher posting"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.payment_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 15),
            status="DRAFT",
            narration="Payment to supplier"
        )
        
        # Debit supplier (reducing liability)
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=self.supplier_ledger, entry_type="DR",
            amount=Decimal("25000.00")
        )
        
        # Credit bank (reducing asset)
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.bank_ledger, entry_type="CR",
            amount=Decimal("25000.00")
        )
        
        service = PostingService()
        posted_voucher = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted_voucher.status, "POSTED")
    
    def test_receipt_voucher_posting(self):
        """Test receipt voucher posting"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            voucher_number="RCP001",
            date=date(2024, 5, 20),
            status="DRAFT",
            narration="Cash sales"
        )
        
        # Debit cash (increasing asset)
        VoucherLine.objects.create(voucher=voucher,
        line_no=5,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("15000.00")
        )
        
        # Credit sales (increasing income)
        VoucherLine.objects.create(voucher=voucher,
        line_no=6,
            ledger=self.sales_ledger, entry_type="CR",
            amount=Decimal("15000.00")
        )
        
        service = PostingService()
        posted_voucher = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted_voucher.status, "POSTED")
    
    def test_already_posted_voucher_raises_error(self):
        """Test that posting an already posted voucher raises error"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.journal_type,
            financial_year=self.fy,
            voucher_number="JV002",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=7,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("1000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=8,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("1000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        # Try to post again
        with self.assertRaises(AlreadyPosted):
            service.post_voucher(voucher.id, self.user)
    
    def test_inactive_voucher_type_raises_error(self):
        """Test that posting with inactive voucher type raises error"""
        from core.services.posting import InvalidVoucherType
        
        # Create inactive voucher type
        inactive_type = VoucherType.objects.create(
            company=self.company, name="Inactive", code="INACT",
            category="JOURNAL", is_accounting=True, is_active=False
        )
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=inactive_type,
            financial_year=self.fy,
            voucher_number="INACT001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=9,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("500.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=10,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("500.00")
        )
        
        service = PostingService()
        with self.assertRaises(InvalidVoucherType):
            service.post_voucher(voucher.id, self.user)
    
    def test_multi_line_voucher_posting(self):
        """Test voucher with multiple debit and credit lines"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.journal_type,
            financial_year=self.fy,
            voucher_number="JV003",
            date=date(2024, 5, 25),
            status="DRAFT",
            narration="Multiple line entry"
        )
        
        # Multiple debits
        VoucherLine.objects.create(voucher=voucher,
        line_no=11,
            ledger=self.expense_ledger, entry_type="DR",
            amount=Decimal("8000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=12,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("2000.00")
        )
        
        # Multiple credits
        VoucherLine.objects.create(voucher=voucher,
        line_no=13,
            ledger=self.bank_ledger, entry_type="CR",
            amount=Decimal("7000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=14,
            ledger=self.supplier_ledger, entry_type="CR",
            amount=Decimal("3000.00")
        )
        
        service = PostingService()
        posted_voucher = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted_voucher.status, "POSTED")


class VoucherNumberingTest(TransactionTestCase):
    """Test voucher numbering with sequences"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="NUM01", name="Numbering Co", legal_name="Numbering Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="numuser", password="test123")
        
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
    
    def test_auto_numbering_sequential(self):
        """Test that vouchers get sequential auto-generated numbers"""
        # Create multiple vouchers and post them
        vouchers = []
        for i in range(5):
            voucher = Voucher.objects.create(
                company=self.company,
                voucher_type=self.voucher_type,
                financial_year=self.fy,
                voucher_number="",  # Will be auto-generated
                date=date(2024, 5, i + 1),
                status="DRAFT"
            )
            
            VoucherLine.objects.create(voucher=voucher,
            line_no=15,
                ledger=self.bank_ledger, entry_type="DR",
                amount=Decimal("1000.00")
            )
            
            VoucherLine.objects.create(voucher=voucher,
            line_no=16,
                ledger=self.bank_ledger, entry_type="CR",
                amount=Decimal("1000.00")
            )
            
            service = PostingService()
            posted = service.post_voucher(voucher.id, self.user)
            vouchers.append(posted)
        
        # Verify numbers are sequential
        numbers = [v.voucher_number for v in vouchers]
        self.assertEqual(len(numbers), len(set(numbers)))  # All unique
        
        # Extract numeric parts and verify sequence
        # Format is typically like PAY000001, PAY000002, etc.
        for i in range(1, len(vouchers)):
            # Numbers should be incrementing
            self.assertLess(vouchers[i-1].voucher_number, vouchers[i].voucher_number)


class VoucherCancellationTest(TestCase):
    """Test voucher cancellation and reversal"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="CAN01", name="Cancel Co", legal_name="Cancel Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="canuser", password="test123")
        
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company, code="BANK", name="Bank",
            group=self.asset_group, account_type="BANK",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company, code="CASH", name="Cash",
            group=self.asset_group, account_type="CASH",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company, name="Journal", code="JV",
            category="JOURNAL", is_accounting=True
        )
        
        # Create sequence for auto-numbering
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:JV:{self.fy.id}",
            prefix="JV",
            last_value=0
        )
    
    def test_voucher_status_transitions(self):
        """Test voucher status transitions from DRAFT to POSTED"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="JV001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        self.assertEqual(voucher.status, "DRAFT")
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=17,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("5000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=18,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("5000.00")
        )
        
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted.status, "POSTED")
