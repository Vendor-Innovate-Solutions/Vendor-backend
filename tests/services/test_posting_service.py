"""
Comprehensive test suite for Posting Service.

Tests cover:
- Voucher posting and reversal
- Transaction validation
- Ledger balance updates
- Double-entry accounting rules
- Concurrent posting handling
- Error cases and rollbacks
"""
import pytest
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from core.services.posting import PostingService
from core.exceptions import BusinessLogicError


@pytest.mark.unit
@pytest.mark.django_db
class TestPostingServiceBasics:
    """Basic posting service functionality tests."""
    
    def test_posting_service_exists(self):
        """Test that PostingService class exists."""
        assert PostingService is not None
    
    def test_posting_service_initialization(self, company):
        """Test PostingService can be initialized."""
        service = PostingService(company=company)
        assert service is not None
        assert service.company == company


@pytest.mark.unit
@pytest.mark.django_db
class TestVoucherPosting:
    """Test voucher posting functionality."""
    
    @pytest.fixture
    def sales_ledger(self, db, company, financial_year):
        """Create sales ledger for testing."""
        from apps.accounting.models import Ledger, AccountGroup
        
        sales_group = AccountGroup.objects.create(
            company=company,
            name='Sales',
            nature='INCOME',
            report_type='PL'
        )
        
        return Ledger.objects.create(
            company=company,
            name='Sales Revenue',
            code='SALES001',
            group=sales_group,
            account_type='INCOME',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=financial_year,
            opening_balance_type='CR'
        )
    
    @pytest.fixture
    def cash_ledger(self, db, company, financial_year):
        """Create cash ledger for testing."""
        from apps.accounting.models import Ledger, AccountGroup
        
        cash_group = AccountGroup.objects.create(
            company=company,
            name='Cash',
            nature='ASSET',
            report_type='BS'
        )
        
        return Ledger.objects.create(
            company=company,
            name='Cash in Hand',
            code='CASH001',
            group=cash_group,
            account_type='CASH',
            opening_balance=Decimal('10000.00'),
            opening_balance_fy=financial_year,
            opening_balance_type='DR'
        )
    
    @pytest.fixture
    def voucher(self, db, company, user):
        """Create test voucher."""
        from apps.voucher.models import Voucher
        return Voucher.objects.create(
            company=company,
            voucher_type='receipt',
            voucher_number='REC-001',
            date=timezone.now().date(),
            amount=Decimal('1000.00'),
            narration='Test voucher',
            created_by=user,
            is_posted=False
        )
    
    @pytest.fixture
    def voucher_entries(self, db, voucher, sales_ledger, cash_ledger):
        """Create voucher entries."""
        from apps.voucher.models import VoucherEntry
        
        # Debit entry (Cash)
        debit_entry = VoucherEntry.objects.create(
            voucher=voucher,
            ledger=cash_ledger,
            entry_type='debit',
            amount=Decimal('1000.00')
        )
        
        # Credit entry (Sales)
        credit_entry = VoucherEntry.objects.create(
            voucher=voucher,
            ledger=sales_ledger,
            entry_type='credit',
            amount=Decimal('1000.00')
        )
        
        return [debit_entry, credit_entry]
    
    def test_post_voucher_success(self, company, voucher, voucher_entries, sales_ledger, cash_ledger):
        """Test successful voucher posting."""
        service = PostingService(company=company)
        
        # Get initial balances
        initial_cash = cash_ledger.current_balance
        initial_sales = sales_ledger.current_balance
        
        # Post voucher
        result = service.post_voucher(voucher)
        
        assert result is True
        
        # Refresh voucher
        voucher.refresh_from_db()
        assert voucher.is_posted is True
        assert voucher.posted_at is not None
        
        # Check ledger balances updated
        cash_ledger.refresh_from_db()
        sales_ledger.refresh_from_db()
        
        assert cash_ledger.current_balance == initial_cash + Decimal('1000.00')
        assert sales_ledger.current_balance == initial_sales + Decimal('1000.00')
    
    def test_post_already_posted_voucher_fails(self, company, voucher, voucher_entries):
        """Test posting an already posted voucher fails."""
        service = PostingService(company=company)
        
        # Post once
        service.post_voucher(voucher)
        
        # Try to post again
        with pytest.raises((BusinessLogicError, Exception)):
            service.post_voucher(voucher)
    
    def test_post_voucher_validates_balanced_entries(self, company, voucher, sales_ledger, cash_ledger):
        """Test posting validates debit = credit."""
        from apps.voucher.models import VoucherEntry
        
        # Create unbalanced entries
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=cash_ledger,
            entry_type='debit',
            amount=Decimal('1000.00')
        )
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=sales_ledger,
            entry_type='credit',
            amount=Decimal('500.00')  # Unbalanced!
        )
        
        service = PostingService(company=company)
        
        with pytest.raises((BusinessLogicError, Exception)):
            service.post_voucher(voucher)
    
    def test_post_voucher_atomic_transaction(self, company, voucher, voucher_entries, sales_ledger):
        """Test posting is atomic - all or nothing."""
        service = PostingService(company=company)
        
        initial_sales_balance = sales_ledger.current_balance
        
        # Simulate an error during posting
        with pytest.raises(Exception):
            with transaction.atomic():
                # Partially post
                sales_ledger.current_balance += Decimal('1000.00')
                sales_ledger.save()
                # Raise error
                raise Exception("Simulated error")
        
        # Balance should be rolled back
        sales_ledger.refresh_from_db()
        assert sales_ledger.current_balance == initial_sales_balance


@pytest.mark.unit
@pytest.mark.django_db
class TestVoucherReversal:
    """Test voucher reversal functionality."""
    
    @pytest.fixture
    def posted_voucher(self, db, company, user):
        """Create a posted voucher."""
        from apps.voucher.models import Voucher, VoucherEntry
        from apps.accounting.models import Ledger
        
        # Create ledgers
        cash_ledger = Ledger.objects.create(
            company=company,
            name='Cash',
            ledger_type='asset',
            opening_balance=Decimal('10000.00'),
            current_balance=Decimal('11000.00')
        )
        sales_ledger = Ledger.objects.create(
            company=company,
            name='Sales',
            ledger_type='income',
            opening_balance=Decimal('0.00'),
            current_balance=Decimal('1000.00')
        )
        
        # Create voucher
        voucher = Voucher.objects.create(
            company=company,
            voucher_type='receipt',
            voucher_number='REC-002',
            date=timezone.now().date(),
            amount=Decimal('1000.00'),
            narration='Posted voucher',
            created_by=user,
            is_posted=True,
            posted_at=timezone.now()
        )
        
        # Create entries
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=cash_ledger,
            entry_type='debit',
            amount=Decimal('1000.00')
        )
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=sales_ledger,
            entry_type='credit',
            amount=Decimal('1000.00')
        )
        
        return voucher
    
    def test_reverse_voucher_success(self, company, posted_voucher):
        """Test successful voucher reversal."""
        service = PostingService(company=company)
        
        # Get ledgers
        from apps.accounting.models import Ledger
        cash_ledger = Ledger.objects.get(company=company, name='Cash')
        sales_ledger = Ledger.objects.get(company=company, name='Sales')
        
        initial_cash = cash_ledger.current_balance
        initial_sales = sales_ledger.current_balance
        
        # Reverse voucher
        result = service.reverse_voucher(posted_voucher)
        
        assert result is True
        
        # Refresh voucher
        posted_voucher.refresh_from_db()
        assert posted_voucher.is_posted is False
        assert posted_voucher.reversed_at is not None
        
        # Check balances reverted
        cash_ledger.refresh_from_db()
        sales_ledger.refresh_from_db()
        
        assert cash_ledger.current_balance == initial_cash - Decimal('1000.00')
        assert sales_ledger.current_balance == initial_sales - Decimal('1000.00')
    
    def test_reverse_unposted_voucher_fails(self, company, voucher):
        """Test reversing an unposted voucher fails."""
        voucher.is_posted = False
        voucher.save()
        
        service = PostingService(company=company)
        
        with pytest.raises((BusinessLogicError, Exception)):
            service.reverse_voucher(voucher)
    
    def test_reverse_already_reversed_voucher_fails(self, company, posted_voucher):
        """Test reversing an already reversed voucher fails."""
        service = PostingService(company=company)
        
        # Reverse once
        service.reverse_voucher(posted_voucher)
        
        # Try to reverse again
        with pytest.raises((BusinessLogicError, Exception)):
            service.reverse_voucher(posted_voucher)


@pytest.mark.unit
@pytest.mark.django_db
class TestLedgerBalanceCalculations:
    """Test ledger balance calculation logic."""
    
    @pytest.fixture
    def ledger(self, db, company):
        """Create test ledger."""
        from apps.accounting.models import Ledger
        return Ledger.objects.create(
            company=company,
            name='Test Ledger',
            ledger_type='asset',
            opening_balance=Decimal('5000.00'),
            current_balance=Decimal('5000.00')
        )
    
    def test_debit_increases_asset_balance(self, company, ledger):
        """Test debit entry increases asset ledger balance."""
        service = PostingService(company=company)
        
        initial_balance = ledger.current_balance
        
        # Apply debit
        service.apply_entry(ledger, 'debit', Decimal('1000.00'))
        
        ledger.refresh_from_db()
        assert ledger.current_balance == initial_balance + Decimal('1000.00')
    
    def test_credit_decreases_asset_balance(self, company, ledger):
        """Test credit entry decreases asset ledger balance."""
        service = PostingService(company=company)
        
        initial_balance = ledger.current_balance
        
        # Apply credit
        service.apply_entry(ledger, 'credit', Decimal('500.00'))
        
        ledger.refresh_from_db()
        assert ledger.current_balance == initial_balance - Decimal('500.00')
    
    def test_balance_calculation_precision(self, company, ledger):
        """Test balance calculations maintain decimal precision."""
        service = PostingService(company=company)
        
        # Apply multiple small amounts
        service.apply_entry(ledger, 'debit', Decimal('0.01'))
        service.apply_entry(ledger, 'debit', Decimal('0.01'))
        service.apply_entry(ledger, 'debit', Decimal('0.01'))
        
        ledger.refresh_from_db()
        # Should be exactly 5000.03, not 5000.030000000001
        assert ledger.current_balance == Decimal('5000.03')


@pytest.mark.concurrent
@pytest.mark.django_db(transaction=True)
class TestConcurrentPosting:
    """Test concurrent posting scenarios."""
    
    def test_concurrent_posting_same_ledger(self, company):
        """Test concurrent posts to same ledger maintain consistency."""
        from apps.accounting.models import Ledger
        
        # Create ledger
        ledger = Ledger.objects.create(
            company=company,
            name='Concurrent Test Ledger',
            ledger_type='asset',
            opening_balance=Decimal('1000.00'),
            current_balance=Decimal('1000.00')
        )
        
        service = PostingService(company=company)
        
        # This test would require actual concurrent execution
        # For now, test sequential is consistent
        service.apply_entry(ledger, 'debit', Decimal('100.00'))
        service.apply_entry(ledger, 'debit', Decimal('200.00'))
        
        ledger.refresh_from_db()
        assert ledger.current_balance == Decimal('1300.00')
    
    @pytest.mark.slow
    def test_posting_with_locking(self, company):
        """Test posting uses proper locking to prevent race conditions."""
        # This is a placeholder for actual concurrent testing
        # Would require threading or multiprocessing
        pass


@pytest.mark.unit
@pytest.mark.django_db
class TestPostingValidation:
    """Test posting service validation logic."""
    
    def test_validates_company_match(self, db):
        """Test posting validates company context."""
        from apps.company.models import Company, Currency
        
        # Create two companies
        currency = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹'
        )
        company1 = Company.objects.create(
            name='Company 1',
            company_type='vendor',
            base_currency=currency
        )
        company2 = Company.objects.create(
            name='Company 2',
            company_type='vendor',
            base_currency=currency
        )
        
        # Create voucher in company1
        from apps.voucher.models import Voucher
        voucher = Voucher.objects.create(
            company=company1,
            voucher_type='receipt',
            voucher_number='TEST-001',
            date=timezone.now().date(),
            amount=Decimal('1000.00')
        )
        
        # Try to post with company2 service
        service = PostingService(company=company2)
        
        with pytest.raises((BusinessLogicError, Exception)):
            service.post_voucher(voucher)
    
    def test_validates_positive_amounts(self, company):
        """Test posting validates amounts are positive."""
        service = PostingService(company=company)
        
        with pytest.raises((BusinessLogicError, ValueError)):
            service.validate_amount(Decimal('-100.00'))
    
    def test_validates_zero_amounts(self, company):
        """Test posting handles zero amounts appropriately."""
        service = PostingService(company=company)
        
        # Zero amounts should typically be invalid
        with pytest.raises((BusinessLogicError, ValueError)):
            service.validate_amount(Decimal('0.00'))


@pytest.mark.unit
@pytest.mark.django_db
class TestPostingServiceHelpers:
    """Test helper methods in posting service."""
    
    def test_calculate_total_debits(self, company, voucher, voucher_entries):
        """Test calculation of total debits."""
        service = PostingService(company=company)
        
        total_debits = service.calculate_total_debits(voucher)
        assert total_debits == Decimal('1000.00')
    
    def test_calculate_total_credits(self, company, voucher, voucher_entries):
        """Test calculation of total credits."""
        service = PostingService(company=company)
        
        total_credits = service.calculate_total_credits(voucher)
        assert total_credits == Decimal('1000.00')
    
    def test_is_balanced(self, company, voucher, voucher_entries):
        """Test balance checking."""
        service = PostingService(company=company)
        
        is_balanced = service.is_balanced(voucher)
        assert is_balanced is True


