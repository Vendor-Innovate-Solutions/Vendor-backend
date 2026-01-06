"""
Unit tests for posting service.
Tests voucher posting, invoice posting, stock movements, and FIFO allocation.
"""
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from decimal import Decimal
from datetime import date, timedelta
from tests.conftest_helpers import BaseTestCase
from core.services.posting import (
    PostingService,
    PostingError,
    AlreadyPosted,
    UnbalancedVoucher,
    InsufficientStock,
    FinancialYearClosed,
    money
)
from apps.voucher.models import Voucher, VoucherLine, VoucherType
from apps.inventory.models import StockMovement, StockItem, StockBatch, Godown, UnitOfMeasure
from apps.company.models import Sequence
from apps.system.models import IdempotencyKey


class MoneyUtilityTest(TestCase):
    """Test money utility function."""
    
    def test_money_rounding(self):
        """Test proper decimal rounding."""
        self.assertEqual(money(10.123), Decimal('10.12'))
        self.assertEqual(money(10.125), Decimal('10.13'))
        self.assertEqual(money(10.127), Decimal('10.13'))
        self.assertEqual(money('10.995'), Decimal('11.00'))
    
    def test_money_precision(self):
        """Test two decimal place precision."""
        result = money(100.123456789)
        self.assertEqual(result, Decimal('100.12'))
        self.assertEqual(str(result), '100.12')


class SequenceGenerationTest(BaseTestCase):
    """Test sequence number generation."""
    
    def setUp(self):
        super().setUp()
        self.posting_service = PostingService()
        
        # Note: VOUCHER sequence already created by BaseTestCase
        # We'll create a different one for testing
        self.test_seq = Sequence.objects.create(
            company=self.company,
            key='TEST_SEQ',
            prefix='TS',
            last_value=0
        )
    
    def test_next_sequence_basic(self):
        """Test basic sequence generation."""
        seq1 = self.posting_service.next_sequence_value(self.company, 'TEST_SEQ')
        seq2 = self.posting_service.next_sequence_value(self.company, 'TEST_SEQ')
        
        self.assertIn('TS', seq1)
        self.assertIn('TS', seq2)
        self.assertNotEqual(seq1, seq2)
    
    def test_sequence_thread_safety(self):
        """Test sequence generation is thread-safe."""
        from threading import Thread
        results = []
        
        def get_sequence():
            seq = self.posting_service.next_sequence_value(self.company, 'TEST_SEQ')
            results.append(seq)
        
        threads = [Thread(target=get_sequence) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All sequences should be unique
        self.assertEqual(len(results), len(set(results)))
    
    def test_sequence_not_found(self):
        """Test error when sequence doesn't exist."""
        with self.assertRaises(PostingError):
            self.posting_service.next_sequence_value(self.company, 'NONEXISTENT')


class VoucherPostingTest(BaseTestCase):
    """Test voucher posting functionality."""
    
    def setUp(self):
        super().setUp()
        self.posting_service = PostingService()
        
        # Create voucher type
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            code='PAYMENT',
            name='Payment',
            category='PAYMENT',
            is_active=True
        )
        
        # Create sequences (compound key: company_id:code:fy_id)
        compound_key = f"{self.company.id}:PAYMENT:{self.fy.id}"
        Sequence.objects.create(
            company=self.company,
            key=compound_key,
            prefix='PAY',
            last_value=0
        )
        
        # Create ledgers
        self.bank_ledger = self.create_ledger('BANK', 'Bank Account', 'BANK')
        self.expense_ledger = self.create_ledger('EXP001', 'Office Expense', 'EXPENSE', self.expense_group)
    
    def test_balanced_voucher_posts_successfully(self):
        """Test that a balanced voucher posts correctly."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),
            entry_type='DR'
        )
        
        # Post voucher
        posted_voucher = self.posting_service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted_voucher.status, 'POSTED')
        self.assertIsNotNone(posted_voucher.voucher_number)
    
    def test_unbalanced_voucher_raises_error(self):
        """Test that unbalanced voucher cannot be posted."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('999.00'),  # Unbalanced
            entry_type='DR'
        )
        
        with self.assertRaises(UnbalancedVoucher):
            self.posting_service.post_voucher(voucher.id, self.user)
    
    def test_double_posting_prevented(self):
        """Test that already posted voucher cannot be posted again."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),
            entry_type='DR'
        )
        
        # Post once
        self.posting_service.post_voucher(voucher.id, self.user)
        
        # Try to post again
        with self.assertRaises(AlreadyPosted):
            self.posting_service.post_voucher(voucher.id, self.user)
    
    def test_idempotency_key_prevents_duplicate(self):
        """Test idempotency key prevents duplicate posting."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),
            entry_type='DR'
        )
        
        idempotency_key = 'test-key-123'
        
        # Post with idempotency key
        result1 = self.posting_service.post_voucher(
            voucher.id, self.user, idempotency_key=idempotency_key
        )
        
        # Create another voucher
        voucher2 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher2,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('2000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher2,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('2000.00'),
            entry_type='DR'
        )
        
        # Try to post with same key - should return original
        result2 = self.posting_service.post_voucher(
            voucher2.id, self.user, idempotency_key=idempotency_key
        )
        
        self.assertEqual(result1.id, result2.id)
        
        # Check second voucher wasn't posted
        voucher2.refresh_from_db()
        self.assertEqual(voucher2.status, 'DRAFT')


class FinancialYearValidationTest(BaseTestCase):
    """Test financial year validation during posting."""
    
    def setUp(self):
        super().setUp()
        self.posting_service = PostingService()
        
        # Lock the financial year
        self.fy.is_closed = True
        self.fy.save()
        
        # Create voucher type and sequence
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            code='PAYMENT',
            name='Payment',
            category='PAYMENT',
            is_active=True
        )
        
        compound_key = f"{self.company.id}:PAYMENT:{self.fy.id}"
        Sequence.objects.create(
            company=self.company,
            key=compound_key,
            prefix='PAY',
            last_value=0
        )
        
        self.bank_ledger = self.create_ledger('BANK', 'Bank', 'BANK')
        self.expense_ledger = self.create_ledger('EXP', 'Expense', 'EXPENSE', self.expense_group)
    
    def test_locked_fy_prevents_posting(self):
        """Test that locked FY prevents posting."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            date=date.today(),
            status='DRAFT'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        VoucherLine.objects.create(voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),
            entry_type='DR'
        )
        
        with self.assertRaises(FinancialYearClosed):
            self.posting_service.post_voucher(voucher.id, self.user)
