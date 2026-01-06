"""
Comprehensive tests for Posting & Reversal Engine.

Tests cover:
1. Voucher posting with ledger balance updates
2. Voucher reversal with cleanup
3. Idempotency key handling
4. Concurrent posting scenarios
5. Double-entry validation
6. Sequence generation
7. Integration event emission
8. Audit trail creation

Run: python -m pytest tests/test_posting_reversal.py -v
"""

import pytest
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
import threading
import time

from apps.company.models import Company, FinancialYear, Currency
from apps.voucher.models import Voucher, VoucherLine, VoucherType
from apps.accounting.models import Ledger, LedgerBalance, AccountGroup
from apps.system.models import AuditLog, IntegrationEvent, IdempotencyKey
from core.services.posting import PostingService
from core.services.posting import (
    PostingError,
    AlreadyPosted,
    UnbalancedVoucher,
    FinancialYearClosed,
)

User = get_user_model()


class PostingServiceTestCase(TestCase):
    """Base test case with common setup"""
    
    def setUp(self):
        """Create test data"""
        # Create currency
        currency = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹',
            decimal_places=2
        )
        
        # Create company
        self.company = Company.objects.create(
            name="Test Company",
            code="TEST001",
            legal_name="Test Company Private Limited",
            base_currency=currency,
            is_active=True
        )
        
        # Create financial year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            is_internal_user=True
        )
        
        # Create voucher type
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name="Payment",
            code="PAY",
            category='PAYMENT',
            is_accounting=True,
            is_inventory=False,
            is_active=True
        )
        
        # Create account groups
        from apps.accounting.models import AccountGroup
        
        cash_group = AccountGroup.objects.create(
            company=self.company,
            code='CASH',
            name='Cash Accounts',
            nature='ASSET',
            report_type='BS',
            path='/CASH'
        )
        
        expense_group = AccountGroup.objects.create(
            company=self.company,
            code='EXPENSES',
            name='Direct Expenses',
            nature='EXPENSE',
            report_type='PL',
            path='/EXPENSES'
        )
        
        # Create ledgers
        self.cash_ledger = Ledger.objects.create(
            company=self.company,
            name="Cash",
            code="CASH001",
            group=cash_group,
            account_type='CASH',
            opening_balance=Decimal('0.00'),
            opening_balance_type='DR',
            opening_balance_fy=self.fy,
            is_active=True
        )
        
        self.expense_ledger = Ledger.objects.create(
            company=self.company,
            name="Office Expenses",
            code="EXP001",
            group=expense_group,
            account_type='EXPENSE',
            opening_balance=Decimal('0.00'),
            opening_balance_type='DR',
            opening_balance_fy=self.fy,
            is_active=True
        )
        
        # Create sequence for voucher numbering
        from apps.company.models import Sequence
        key = f"{self.company.id}:{self.voucher_type.code}:{self.fy.id}"
        Sequence.objects.create(
            company=self.company,
            key=key,
            prefix=self.voucher_type.code,
            last_value=0,
            reset_period='YEARLY'
        )
        
        self.service = PostingService()


class TestVoucherPosting(PostingServiceTestCase):
    """Test voucher posting functionality"""
    
    def test_simple_voucher_posting(self):
        """Test basic voucher posting with balanced entries"""
        # Create voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Test payment",
            status='DRAFT'
        )
        
        # Add lines (balanced: DR = CR)
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('1000.00'),

            entry_type='CR'
        )
        
        # Post voucher
        result = self.service.post_voucher(voucher.id, self.user)
        
        # Assertions
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, 'POSTED')
        self.assertIsNotNone(voucher.posted_at)
        self.assertIsNotNone(voucher.voucher_number)
        
        # Check ledger balances
        expense_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.expense_ledger,
            financial_year=self.fy
        )
        self.assertEqual(expense_balance.balance_dr, Decimal('1000.00'))
        self.assertEqual(expense_balance.balance_cr, Decimal('0.00'))
        
        cash_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.cash_ledger,
            financial_year=self.fy
        )
        self.assertEqual(cash_balance.balance_dr, Decimal('0.00'))
        self.assertEqual(cash_balance.balance_cr, Decimal('1000.00'))
    
    def test_unbalanced_voucher_rejection(self):
        """Test that unbalanced vouchers are rejected"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Unbalanced test",
            status='DRAFT'
        )
        
        # Unbalanced lines (DR != CR)
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('800.00'),  # Unbalanced!
            entry_type='CR'
        )
        
        # Should raise UnbalancedVoucher
        with self.assertRaises(UnbalancedVoucher):
            self.service.post_voucher(voucher.id, self.user)
    
    def test_already_posted_voucher(self):
        """Test that already posted vouchers cannot be posted again"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Already posted",
            status='POSTED',
            voucher_number="PAY-2024-001",
            posted_at=timezone.now()
        )
        
        # Should raise AlreadyPosted
        with self.assertRaises(AlreadyPosted):
            self.service.post_voucher(voucher.id, self.user)
    
    def test_voucher_number_generation(self):
        """Test automatic voucher number generation"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Number generation test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('500.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('500.00'),

            entry_type='CR'
        )
        
        self.service.post_voucher(voucher.id, self.user)
        
        voucher.refresh_from_db()
        self.assertIsNotNone(voucher.voucher_number)
        self.assertTrue(voucher.voucher_number.startswith('PAY'))
    
    def test_audit_log_creation(self):
        """Test that posting creates audit log entry"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Audit log test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('300.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('300.00'),

            entry_type='CR'
        )
        
        audit_count_before = AuditLog.objects.count()
        
        self.service.post_voucher(voucher.id, self.user)
        
        audit_count_after = AuditLog.objects.count()
        self.assertGreater(audit_count_after, audit_count_before)
        
        # Check audit log details
        audit_log = AuditLog.objects.filter(
            company=self.company,
            action_type='POST'
        ).first()
        
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.actor_user, self.user)
    
    def test_integration_event_emission(self):
        """Test that posting emits integration event"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Event emission test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('200.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('200.00'),

            entry_type='CR'
        )
        
        event_count_before = IntegrationEvent.objects.count()
        
        self.service.post_voucher(voucher.id, self.user)
        
        event_count_after = IntegrationEvent.objects.count()
        self.assertGreater(event_count_after, event_count_before)
        
        # Check event details
        event = IntegrationEvent.objects.filter(
            company=self.company,
            event_type='voucher.posted'
        ).first()
        
        self.assertIsNotNone(event)
        self.assertIn('voucher_id', event.payload)


class TestVoucherReversal(PostingServiceTestCase):
    """Test voucher reversal functionality"""
    
    def test_simple_voucher_reversal(self):
        """Test basic voucher reversal"""
        # Create and post voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Test reversal",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('1500.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('1500.00'),

            entry_type='CR'
        )
        
        self.service.post_voucher(voucher.id, self.user)
        
        # Get balances after posting
        expense_balance_after_post = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.expense_ledger,
            financial_year=self.fy
        )
        
        # Reverse voucher
        self.service.reverse_voucher(voucher.id, self.user, "Test reversal reason")
        
        voucher.refresh_from_db()
        self.assertEqual(voucher.status, 'REVERSED')
        self.assertIsNotNone(voucher.reversed_at)
        self.assertEqual(voucher.reversal_user, self.user)
        
        # Check balances are zeroed out
        expense_balance_after_reverse = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.expense_ledger,
            financial_year=self.fy
        )
        self.assertEqual(expense_balance_after_reverse.balance_dr, Decimal('0.00'))
        self.assertEqual(expense_balance_after_reverse.balance_cr, Decimal('0.00'))
    
    def test_cannot_reverse_draft_voucher(self):
        """Test that draft vouchers cannot be reversed"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Draft voucher",
            status='DRAFT'
        )
        
        with self.assertRaises(PostingError):
            self.service.reverse_voucher(voucher.id, self.user, "Should fail")
    
    def test_cannot_reverse_already_reversed(self):
        """Test that already reversed vouchers cannot be reversed again"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Already reversed",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('800.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('800.00'),

            entry_type='CR'
        )
        
        # Post and reverse
        self.service.post_voucher(voucher.id, self.user)
        self.service.reverse_voucher(voucher.id, self.user, "First reversal")
        
        # Try to reverse again
        with self.assertRaises(PostingError):
            self.service.reverse_voucher(voucher.id, self.user, "Second reversal")
    
    def test_reversal_audit_trail(self):
        """Test that reversal creates audit log"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Audit trail test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('600.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('600.00'),

            entry_type='CR'
        )
        
        self.service.post_voucher(voucher.id, self.user)
        
        audit_count_before = AuditLog.objects.count()
        self.service.reverse_voucher(voucher.id, self.user, "Audit test")
        audit_count_after = AuditLog.objects.count()
        
        self.assertGreater(audit_count_after, audit_count_before)


class TestIdempotencyHandling(PostingServiceTestCase):
    """Test idempotency key handling"""
    
    def test_idempotency_key_prevents_duplicate_posting(self):
        """Test that same idempotency key prevents duplicate posting"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Idempotency test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('400.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('400.00'),

            entry_type='CR'
        )
        
        idempotency_key = "test-key-12345"
        
        # First posting
        result1 = self.service.post_voucher(
            voucher.id,
            self.user,
            idempotency_key=idempotency_key
        )
        
        # Second posting with same key should return cached result
        voucher.status = 'DRAFT'  # Reset status
        voucher.save()
        
        result2 = self.service.post_voucher(
            voucher.id,
            self.user,
            idempotency_key=idempotency_key
        )
        
        # Should return same result
        self.assertEqual(result1.id, result2.id)
        
        # Check idempotency key was recorded
        idem_key = IdempotencyKey.objects.filter(key=idempotency_key).first()
        self.assertIsNotNone(idem_key)


class TestConcurrentPosting(TransactionTestCase):
    """Test concurrent posting scenarios"""
    
    def setUp(self):
        """Create test data"""
        # Create currency
        currency = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹',
            decimal_places=2
        )
        
        self.company = Company.objects.create(
            name="Concurrent Test Company",
            code="CONC001",
            base_currency=currency,
            is_active=True
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        self.user = User.objects.create_user(
            username='concurrentuser',
            password='testpass123',
            is_internal_user=True
        )
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name="Payment",
            code="PAY",
            is_active=True
        )
        
        # Create account groups
        cash_group = AccountGroup.objects.create(
            company=self.company,
            name="Cash",
            code="CASH",
            nature='ASSET',
            report_type='BS'
        )
        
        expense_group = AccountGroup.objects.create(
            company=self.company,
            name="Direct Expenses",
            code="DIRECT_EXPENSES",
            nature='EXPENSE',
            report_type='PL'
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company,
            name="Cash",
            code="CASH001",
            group=cash_group,
            account_type='CASH',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        self.expense_ledger = Ledger.objects.create(
            company=self.company,
            name="Expenses",
            code="EXP001",
            group=expense_group,
            account_type='EXPENSE',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        # Create sequence for voucher numbering
        from apps.company.models import Sequence
        key = f"{self.company.id}:{self.voucher_type.code}:{self.fy.id}"
        Sequence.objects.create(
            company=self.company,
            key=key,
            prefix=self.voucher_type.code,
            last_value=0,
            reset_period='YEARLY'
        )
        
        self.service = PostingService()
    
    def test_concurrent_voucher_posting(self):
        """Test that concurrent postings don't corrupt balances"""
        # Create multiple vouchers
        vouchers = []
        for i in range(5):
            voucher = Voucher.objects.create(
                company=self.company,
                voucher_type=self.voucher_type,
                financial_year=self.fy,
                date=date.today(),
                narration=f"Concurrent test {i}",
                voucher_number=f"TEMP-{i}",  # Temporary number to avoid constraint violation
                status='DRAFT'
            )
            
            VoucherLine.objects.create(
                voucher=voucher,
                line_no=1,
                ledger=self.expense_ledger,
                amount=Decimal('100.00'),
                entry_type='DR'
            )
            
            VoucherLine.objects.create(
                voucher=voucher,
                line_no=1,
                ledger=self.cash_ledger,
                amount=Decimal('100.00'),
                entry_type='CR'
            )
            
            vouchers.append(voucher)
        
        # Post all vouchers concurrently
        threads = []
        for voucher in vouchers:
            thread = threading.Thread(
                target=self._post_voucher_thread,
                args=(voucher.id,)
            )
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Check final balance
        cash_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.cash_ledger,
            financial_year=self.fy
        )
        
        # Should be exactly 500.00 (5 vouchers × 100.00)
        self.assertEqual(cash_balance.balance_cr, Decimal('500.00'))
    
    def _post_voucher_thread(self, voucher_id):
        """Helper method to post voucher in thread"""
        try:
            service = PostingService()
            service.post_voucher(voucher_id, self.user)
        except Exception as e:
            print(f"Error in thread: {e}")


class TestFinancialYearValidation(PostingServiceTestCase):
    """Test financial year validation in posting"""
    
    def test_cannot_post_to_closed_fy(self):
        """Test that posting to closed FY is prevented"""
        # Close financial year
        self.fy.is_closed = True
        self.fy.closed_at = timezone.now()
        self.fy.closed_by = self.user
        self.fy.save()
        
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date(2024, 5, 1),  # Within FY but closed
            narration="Closed FY test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('100.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('100.00'),

            entry_type='CR'
        )
        
        # Should raise FinancialYearClosed
        with self.assertRaises(FinancialYearClosed):
            self.service.post_voucher(voucher.id, self.user)
    
    def test_can_post_to_open_fy(self):
        """Test that posting to open FY works"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date(2024, 5, 1),
            narration="Open FY test",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('250.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('250.00'),

            entry_type='CR'
        )
        
        # Should succeed
        result = self.service.post_voucher(voucher.id, self.user)
        self.assertIsNotNone(result)


class TestDecimalPrecision(PostingServiceTestCase):
    """Test decimal precision handling"""
    
    def test_decimal_rounding_in_posting(self):
        """Test that decimal amounts are properly rounded"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Decimal test",
            status='DRAFT'
        )
        
        # Use amounts with many decimal places
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('1000.12345'),  # Will be rounded to 1000.12
            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('1000.12345'),  # Will be rounded to 1000.12
            entry_type='CR'
        )
        
        self.service.post_voucher(voucher.id, self.user)
        
        # Check that balance has 2 decimal places
        expense_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.expense_ledger,
            financial_year=self.fy
        )
        
        self.assertEqual(expense_balance.balance_dr, Decimal('1000.12'))


# Run with: python -m pytest tests/test_posting_reversal.py -v --tb=short
