"""
Test Concurrent Posting Protection
Tests thread-safe voucher posting with proper locking
"""
import threading
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model

from apps.voucher.models import Voucher, VoucherType, VoucherLine
from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger
from core.services.posting import PostingService, AlreadyPosted

User = get_user_model()


class ConcurrentPostingTest(TransactionTestCase):
    """Test concurrent posting protection"""
    
    reset_sequences = True
    
    def setUp(self):
        """Set up test data"""
        # Create currency
        self.currency = Currency.objects.create(
            code="INR",
            name="Indian Rupee",
            symbol="₹",
            decimal_places=2
        )
        
        # Create company
        self.company = Company.objects.create(
            code="CONC01",
            name="Concurrent Test Co",
            legal_name="Concurrent Test Co Ltd",
            company_type="PRIVATE_LIMITED",
            timezone="UTC",
            language="en",
            base_currency=self.currency
        )
        
        # Create financial year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date="2024-04-01",
            end_date="2025-03-31",
            is_current=True,
            is_closed=False
        )
        
        # Create user
        self.user = User.objects.create_user(
            username="concurrent_tester",
            password="testpass123"
        )
        
        # Create account groups
        self.asset_group = AccountGroup.objects.create(
            company=self.company,
            name="Current Assets",
            code="CA",
            nature="ASSET",
            report_type="BS",
            path="/CA"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company,
            name="Current Liabilities",
            code="CL",
            nature="LIABILITY",
            report_type="BS",
            path="/CL"
        )
        
        # Create ledgers
        self.bank_ledger = Ledger.objects.create(
            company=self.company,
            code="BANK001",
            name="Bank Account",
            group=self.asset_group,
            account_type="BANK",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        self.creditor_ledger = Ledger.objects.create(
            company=self.company,
            code="CRED001",
            name="Creditor Account",
            group=self.liability_group,
            account_type="SUPPLIER",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        # Create voucher type
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name="Journal",
            code="JRN",
            category="JOURNAL",
            is_accounting=True,
            is_inventory=False
        )
        
        # Create sequence for auto-numbering
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:JRN:{self.fy.id}",
            prefix="JRN",
            last_value=0
        )
        
        # Create test voucher
        self.voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="JRN001",
            date="2024-05-01",
            status="DRAFT",
            narration="Test concurrent posting"
        )
        
        # Create voucher lines
        VoucherLine.objects.create(voucher=self.voucher,
        line_no=1,
            ledger=self.bank_ledger,
            entry_type="DR",
            amount=Decimal("10000.00")
        )
        
        VoucherLine.objects.create(voucher=self.voucher,
        line_no=2,
            ledger=self.creditor_ledger,
            entry_type="CR",
            amount=Decimal("10000.00")
        )
    
    def _post_voucher(self, results, idx):
        """Helper method to post voucher in thread"""
        try:
            service = PostingService()
            service.post_voucher(self.voucher.id, self.user)
            results[idx] = "SUCCESS"
        except AlreadyPosted as e:
            results[idx] = "ALREADY_POSTED"
        except Exception as e:
            results[idx] = f"ERROR: {str(e)}"
    
    def test_double_posting_protection(self):
        """Test that only one thread can post a voucher"""
        results = {}
        
        # Create two threads trying to post same voucher
        thread1 = threading.Thread(
            target=self._post_voucher, 
            args=(results, 1)
        )
        thread2 = threading.Thread(
            target=self._post_voucher, 
            args=(results, 2)
        )
        
        # Start both threads simultaneously
        thread1.start()
        thread2.start()
        
        # Wait for both to complete
        thread1.join()
        thread2.join()
        
        # Exactly one should succeed
        success_count = list(results.values()).count("SUCCESS")
        already_posted_count = list(results.values()).count("ALREADY_POSTED")
        
        self.assertEqual(success_count, 1, 
                        f"Expected exactly 1 success, got {success_count}. Results: {results}")
        self.assertEqual(already_posted_count, 1,
                        f"Expected exactly 1 already_posted, got {already_posted_count}. Results: {results}")
        
        # Verify voucher is posted
        self.voucher.refresh_from_db()
        self.assertEqual(self.voucher.status, "POSTED")
    
    def test_sequential_posting_of_multiple_vouchers(self):
        """Test that multiple different vouchers can be posted"""
        # Create second voucher
        voucher2 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="JRN002",
            date="2024-05-02",
            status="DRAFT",
            narration="Second voucher"
        )
        
        VoucherLine.objects.create(voucher=voucher2,
        line_no=1,
            ledger=self.bank_ledger,
            entry_type="DR",
            amount=Decimal("5000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher2,
        line_no=2,
            ledger=self.creditor_ledger,
            entry_type="CR",
            amount=Decimal("5000.00")
        )
        
        # Post both vouchers
        service = PostingService()
        service.post_voucher(self.voucher.id, self.user)
        service.post_voucher(voucher2.id, self.user)
        
        # Verify both are posted
        self.voucher.refresh_from_db()
        voucher2.refresh_from_db()
        
        self.assertEqual(self.voucher.status, "POSTED")
        self.assertEqual(voucher2.status, "POSTED")


class DoubleEntryValidationTest(TransactionTestCase):
    """Test double-entry validation logic"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="DBL01", name="Double Entry Co", legal_name="Double Entry Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date="2024-04-01", end_date="2025-03-31",
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="dbl_user", password="test123")
        
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company, name="Liabilities", code="LIB",
            nature="LIABILITY", report_type="BS", path="/LIB"
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company, code="CASH", name="Cash",
            group=self.asset_group, account_type="CASH",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.loan_ledger = Ledger.objects.create(
            company=self.company, code="LOAN", name="Loan",
            group=self.liability_group, account_type="LIABILITY",
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
    
    def test_balanced_voucher_posts_successfully(self):
        """Test balanced voucher (DR = CR) posts successfully"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="BAL001",
            date="2024-05-01",
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("50000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.loan_ledger, entry_type="CR",
            amount=Decimal("50000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "POSTED")
    
    def test_unbalanced_voucher_raises_error(self):
        """Test unbalanced voucher (DR != CR) raises error"""
        from core.services.posting import UnbalancedVoucher
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="UNBAL001",
            date="2024-05-01",
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("50000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.loan_ledger, entry_type="CR",
            amount=Decimal("45000.00")  # Unbalanced!
        )
        
        service = PostingService()
        with self.assertRaises(UnbalancedVoucher):
            service.post_voucher(voucher.id, self.user)
        
        # Voucher should remain in DRAFT
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "DRAFT")
    
    def test_complex_multi_line_voucher_balance(self):
        """Test complex voucher with multiple debit and credit lines"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="MULTI001",
            date="2024-05-01",
            status="DRAFT"
        )
        
        # Multiple debits
        VoucherLine.objects.create(voucher=voucher,
        line_no=5,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("10000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=6,
            ledger=self.cash_ledger, entry_type="DR",
            amount=Decimal("15000.00")
        )
        
        # Multiple credits
        VoucherLine.objects.create(voucher=voucher,
        line_no=7,
            ledger=self.loan_ledger, entry_type="CR",
            amount=Decimal("12000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=8,
            ledger=self.loan_ledger, entry_type="CR",
            amount=Decimal("13000.00")
        )
        
        service = PostingService()
        service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, "POSTED")
