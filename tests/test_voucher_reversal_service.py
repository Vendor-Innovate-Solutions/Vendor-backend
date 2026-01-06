"""
Tests for VoucherReversalService
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.voucher.models import Voucher, VoucherLine, VoucherType, VoucherCategory
from apps.accounting.models import Ledger, AccountGroup, LedgerBalance
from apps.inventory.models import StockItem, StockMovement, StockBalance, Godown, UnitOfMeasure
from apps.company.models import Company, Currency, FinancialYear
from apps.voucher.services import VoucherReversalService
from core.posting_exceptions import (
    InvalidVoucherStateError,
    AlreadyReversedError,
    ClosedFinancialYearError,
    ValidationError
)

User = get_user_model()


class TestVoucherReversalService(TestCase):
    """Test suite for VoucherReversalService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create currency
        self.currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        
        # Create company
        self.company = Company.objects.create(
            name='Test Company',
            code='TEST',
            base_currency=self.currency
        )
        
        # Create financial year
        self.financial_year = FinancialYear.objects.create(
            company=self.company,
            name='2024-25',
            start_date='2024-04-01',
            end_date='2025-03-31',
            is_closed=False
        )
        
        # Create user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create account groups
        self.assets_group = AccountGroup.objects.create(
            company=self.company,
            name='Assets',
            code='ASSETS',
            nature='ASSET',
            report_type='BS',
            path='/ASSETS'
        )
        self.expenses_group = AccountGroup.objects.create(
            company=self.company,
            name='Expenses',
            code='EXPENSES',
            nature='EXPENSE',
            report_type='PL',
            path='/EXPENSES'
        )
        
        # Create ledgers
        self.cash_ledger = Ledger.objects.create(
            company=self.company,
            name='Cash',
            code='CASH',
            group=self.assets_group,
            account_type='CASH',
            opening_balance_fy=self.financial_year
        )
        self.expense_ledger = Ledger.objects.create(
            company=self.company,
            name='Office Expense',
            code='OFFICE_EXP',
            group=self.expenses_group,
            account_type='EXPENSE',
            opening_balance_fy=self.financial_year
        )
        
        # Create voucher type
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name='Journal',
            code='JV',
            category=VoucherCategory.JOURNAL
        )
        
        # Create UOM
        self.uom = UnitOfMeasure.objects.create(
            name='Piece',
            symbol='PC',
            category='QUANTITY'
        )
        
        # Create stock item
        self.stock_item = StockItem.objects.create(
            company=self.company,
            name='Test Product',
            sku='PROD001',
            uom=self.uom
        )
        
        # Create godowns
        self.main_godown = Godown.objects.create(
            company=self.company,
            name='Main Warehouse',
            code='MAIN'
        )
        self.branch_godown = Godown.objects.create(
            company=self.company,
            name='Branch Warehouse',
            code='BRANCH'
        )
    
    def test_reverse_journal_voucher(self):
        """Test reversing a simple journal voucher."""
        # Create and post a journal voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-001',
            date=timezone.now().date(),
            financial_year=self.financial_year,
            narration='Test journal entry',
            posted_at=timezone.now()
        )
        
        # Create voucher lines
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.expense_ledger,
            amount=Decimal('1000.00'),
            entry_type='DR'
        )
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=2,
            ledger=self.cash_ledger,
            amount=Decimal('1000.00'),
            entry_type='CR'
        )
        
        # Initialize ledger balances
        LedgerBalance.objects.create(
            company=self.company,
            ledger=self.expense_ledger,
            financial_year=self.financial_year,
            balance_dr=Decimal('1000.00'),
            balance_cr=Decimal('0.00')
        )
        LedgerBalance.objects.create(
            company=self.company,
            ledger=self.cash_ledger,
            financial_year=self.financial_year,
            balance_dr=Decimal('0.00'),
            balance_cr=Decimal('1000.00')
        )
        
        # Reverse the voucher
        service = VoucherReversalService(self.user)
        reversal = service.reverse_voucher(
            voucher,
            reversal_reason='Correction needed'
        )
        
        # Verify reversal voucher created
        self.assertNotEqual(reversal.id, voucher.id)
        self.assertTrue(reversal.voucher_number.startswith('REV-'))
        self.assertIn('Reversal of JV-001', reversal.narration)
        self.assertIsNotNone(reversal.posted_at)
        
        # Verify original voucher marked as reversed
        voucher.refresh_from_db()
        self.assertEqual(voucher.reversed_voucher, reversal)
        self.assertIsNotNone(voucher.reversed_at)
        self.assertEqual(voucher.reversal_reason, 'Correction needed')
        self.assertEqual(voucher.reversal_user, self.user)
        
        # Verify reversal lines (swapped DR/CR)
        reversal_lines = reversal.lines.all()
        self.assertEqual(reversal_lines.count(), 2)
        
        # Office expense: was DR 1000, now CR 1000
        expense_line = reversal_lines.get(ledger=self.expense_ledger)
        self.assertEqual(expense_line.amount, Decimal('1000.00'))
        self.assertEqual(expense_line.entry_type, 'CR')
        
        # Cash: was CR 1000, now DR 1000
        cash_line = reversal_lines.get(ledger=self.cash_ledger)
        self.assertEqual(cash_line.amount, Decimal('1000.00'))
        self.assertEqual(cash_line.entry_type, 'DR')
        
        # Verify ledger balances updated
        expense_balance = LedgerBalance.objects.get(
            ledger=self.expense_ledger,
            financial_year=self.financial_year
        )
        # Original: DR 1000, Reversal: CR 1000 = DR 1000 + CR 1000
        self.assertEqual(expense_balance.balance_dr, Decimal('1000.00'))
        self.assertEqual(expense_balance.balance_cr, Decimal('1000.00'))
        
        cash_balance = LedgerBalance.objects.get(
            ledger=self.cash_ledger,
            financial_year=self.financial_year
        )
        # Original: CR 1000, Reversal: DR 1000 = DR 1000 + CR 1000
        self.assertEqual(cash_balance.balance_dr, Decimal('1000.00'))
        self.assertEqual(cash_balance.balance_cr, Decimal('1000.00'))
    
    def test_reverse_inventory_voucher(self):
        """Test reversing a voucher with stock movements."""
        # Create and post a voucher with stock movement
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-002',
            date=timezone.now().date(),
            financial_year=self.financial_year,
            narration='Stock transfer',
            posted_at=timezone.now()
        )
        
        # Create stock movement (Main -> Branch)
        StockMovement.objects.create(
            company=self.company,
            voucher=voucher,
            item=self.stock_item,
            from_godown=self.main_godown,
            to_godown=self.branch_godown,
            quantity=Decimal('100'),
            rate=Decimal('10.00'),
            movement_date=voucher.date
        )
        
        # Initialize stock balances
        main_balance = StockBalance.objects.create(
            company=self.company,
            item=self.stock_item,
            godown=self.main_godown,
            quantity_on_hand=Decimal('900.00'),  # 1000 - 100
            quantity_reserved=Decimal('0.00'),
            quantity_allocated=Decimal('0.00')
        )
        branch_balance = StockBalance.objects.create(
            company=self.company,
            item=self.stock_item,
            godown=self.branch_godown,
            quantity_on_hand=Decimal('100.00'),  # 0 + 100
            quantity_reserved=Decimal('0.00'),
            quantity_allocated=Decimal('0.00')
        )
        
        # Reverse the voucher
        service = VoucherReversalService(self.user)
        reversal = service.reverse_voucher(
            voucher,
            reversal_reason='Wrong transfer'
        )
        
        # Verify reversal movement (Branch -> Main, swapped godowns)
        reversal_movements = reversal.stock_movements.all()
        self.assertEqual(reversal_movements.count(), 1)
        
        movement = reversal_movements.first()
        self.assertEqual(movement.from_godown, self.branch_godown)  # Swapped
        self.assertEqual(movement.to_godown, self.main_godown)      # Swapped
        self.assertEqual(movement.quantity, Decimal('100'))
        
        # Verify stock balances updated
        main_balance.refresh_from_db()
        branch_balance.refresh_from_db()
        
        # Main: 900 + 100 (from reversal) = 1000
        self.assertEqual(main_balance.quantity_on_hand, Decimal('1000.00'))
        
        # Branch: 100 - 100 (from reversal) = 0
        self.assertEqual(branch_balance.quantity_on_hand, Decimal('0.00'))
    
    def test_prevent_reversing_unposted_voucher(self):
        """Test that unposted vouchers cannot be reversed."""
        # Create unposted voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-003',
            date=timezone.now().date(),
            financial_year=self.financial_year,
            posted_at=None  # Not posted
        )
        
        # Attempt to reverse
        service = VoucherReversalService(self.user)
        with self.assertRaises(InvalidVoucherStateError) as context:
            service.reverse_voucher(voucher, 'Test reason')
        
        self.assertIn('not posted', str(context.exception))
    
    def test_prevent_double_reversal(self):
        """Test that vouchers cannot be reversed twice."""
        # Create and post voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-004',
            date=timezone.now().date(),
            financial_year=self.financial_year,
            posted_at=timezone.now()
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('100.00'),
            entry_type='DR'
        )
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('100.00'),
            entry_type='CR'
        )
        
        # First reversal
        service = VoucherReversalService(self.user)
        service.reverse_voucher(voucher, 'First reversal')
        
        # Attempt second reversal
        with self.assertRaises(AlreadyReversedError) as context:
            service.reverse_voucher(voucher, 'Second reversal')
        
        self.assertIn('already reversed', str(context.exception))
    
    def test_prevent_reversing_closed_fy(self):
        """Test that vouchers in closed FY cannot be reversed."""
        # Create closed financial year
        closed_fy = FinancialYear.objects.create(
            company=self.company,
            name='2023-24',
            start_date='2023-04-01',
            end_date='2024-03-31',
            is_closed=True  # Closed
        )
        
        # Create voucher in closed FY
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-005',
            date='2023-05-01',
            financial_year=closed_fy,
            posted_at=timezone.now()
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('100.00'),
            entry_type='DR'
        )
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=2,
            ledger=self.expense_ledger,
            amount=Decimal('100.00'),
            entry_type='CR'
        )
        
        # Attempt to reverse
        service = VoucherReversalService(self.user)
        with self.assertRaises(ClosedFinancialYearError) as context:
            service.reverse_voucher(voucher, 'Test reason')
        
        self.assertIn('closed financial year', str(context.exception))
    
    def test_reversal_reason_required(self):
        """Test that reversal reason is required."""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            voucher_number='JV-006',
            date=timezone.now().date(),
            financial_year=self.financial_year,
            posted_at=timezone.now()
        )
        
        service = VoucherReversalService(self.user)
        
        # Empty reason
        with self.assertRaises(ValidationError) as context:
            service.reverse_voucher(voucher, '')
        self.assertIn('required', str(context.exception))
        
        # Whitespace only
        with self.assertRaises(ValidationError) as context:
            service.reverse_voucher(voucher, '   ')
        self.assertIn('required', str(context.exception))
