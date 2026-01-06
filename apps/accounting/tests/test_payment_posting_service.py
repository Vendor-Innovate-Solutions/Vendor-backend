"""
Tests for Payment Posting Service
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.company.models import Company, Currency, FinancialYear
from apps.party.models import Party
from apps.accounting.models import Ledger, AccountGroup, LedgerBalance
from apps.voucher.models import Voucher, VoucherType, Payment, PaymentLine
from apps.invoice.models import Invoice
from apps.accounting.services import PaymentPostingService
from core.posting_exceptions import AlreadyPosted

User = get_user_model()


class PaymentPostingServiceTest(TestCase):
    """Test payment posting service"""

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
            code="TST01",
            name="Test Company",
            legal_name="Test Company Ltd",
            company_type="PRIVATE_LIMITED",
            timezone="UTC",
            language="en",
            base_currency=self.currency
        )
        
        # Create financial year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="FY2025-26",
            start_date=timezone.now().date().replace(month=4, day=1),
            end_date=(timezone.now().date().replace(month=3, day=31) + timezone.timedelta(days=365))
        )
        
        # Create account groups
        self.sundry_debtors = AccountGroup.objects.create(
            company=self.company,
            name="Sundry Debtors",
            code="SD001",
            nature="ASSET",
            report_type="BS",
            path="/Sundry Debtors"
        )
        
        self.bank_accounts = AccountGroup.objects.create(
            company=self.company,
            name="Bank Accounts",
            code="BANK001",
            nature="ASSET",
            report_type="BS",
            path="/Bank Accounts"
        )
        
        # Create ledgers
        self.customer_ledger = Ledger.objects.create(
            company=self.company,
            name="Test Customer",
            code="CUST001",
            group=self.sundry_debtors,
            account_type="CUSTOMER",
            opening_balance_fy=self.fy
        )
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company,
            name="HDFC Bank",
            code="BANK001",
            group=self.bank_accounts,
            account_type="BANK",
            opening_balance_fy=self.fy
        )
        
        # Create party
        self.customer = Party.objects.create(
            company=self.company,
            name="Test Customer",
            party_type="CUSTOMER",
            ledger=self.customer_ledger,
            phone="1234567890"
        )
        
        # Create voucher type
        self.receipt_type = VoucherType.objects.create(
            company=self.company,
            name="Receipt",
            code="RCPT",
            category="RECEIPT",
            is_accounting=True
        )
        
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        
        # Create invoice
        self.invoice = Invoice.objects.create(
            company=self.company,
            invoice_number="INV-001",
            invoice_type="SALES",
            party=self.customer,
            currency=self.currency,
            invoice_date=timezone.now().date(),
            due_date=timezone.now().date(),
            status="DRAFT",
            grand_total=Decimal("1000.00"),
            amount_received=Decimal("0.00")
        )

    def test_post_receipt_voucher(self):
        """Test posting a receipt voucher for invoice payment"""
        # Create voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            voucher_number="RCPT-001",
            date=timezone.now().date(),
            status="DRAFT"
        )
        
        # Create payment
        payment = Payment.objects.create(
            company=self.company,
            voucher=voucher,
            bank_account=self.bank_ledger,
            payment_date=timezone.now().date(),
            payment_mode="BANK_TRANSFER",
            status="DRAFT"
        )
        
        # Create payment line
        PaymentLine.objects.create(
            payment=payment,
            invoice=self.invoice,
            amount_applied=Decimal("500.00"),
            line_no=1
        )
        
        # Post the payment
        posted_voucher = PaymentPostingService.post_payment_voucher(
            voucher_id=voucher.id,
            user=self.user
        )
        
        # Verify voucher posted
        self.assertEqual(posted_voucher.status, "POSTED")
        self.assertIsNotNone(posted_voucher.posted_at)
        
        # Verify payment posted
        payment.refresh_from_db()
        self.assertEqual(payment.status, "POSTED")
        
        # Verify invoice updated
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_received, Decimal("500.00"))
        self.assertEqual(self.invoice.status, "PARTIALLY_PAID")
        
        # Verify voucher lines created (2 lines: customer CR + bank DR)
        voucher_lines = posted_voucher.lines.all()
        self.assertEqual(voucher_lines.count(), 2)
        
        # Verify ledger balances updated
        customer_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.customer_ledger,
            financial_year=self.fy
        )
        self.assertEqual(customer_balance.balance_cr, Decimal("500.00"))
        
        bank_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.bank_ledger,
            financial_year=self.fy
        )
        self.assertEqual(bank_balance.balance_dr, Decimal("500.00"))

    def test_full_payment_marks_invoice_paid(self):
        """Test that full payment marks invoice as PAID"""
        # Create voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            voucher_number="RCPT-002",
            date=timezone.now().date(),
            status="DRAFT"
        )
        
        # Create payment
        payment = Payment.objects.create(
            company=self.company,
            voucher=voucher,
            bank_account=self.bank_ledger,
            payment_date=timezone.now().date(),
            payment_mode="CASH",
            status="DRAFT"
        )
        
        # Create payment line for full amount
        PaymentLine.objects.create(
            payment=payment,
            invoice=self.invoice,
            amount_applied=Decimal("1000.00"),
            line_no=1
        )
        
        # Post the payment
        PaymentPostingService.post_payment_voucher(
            voucher_id=voucher.id,
            user=self.user
        )
        
        # Verify invoice fully paid
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_received, Decimal("1000.00"))
        self.assertEqual(self.invoice.status, "PAID")

    def test_cannot_post_already_posted_voucher(self):
        """Test that posting already posted voucher raises error"""
        # Create and post voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            voucher_number="RCPT-003",
            date=timezone.now().date(),
            status="DRAFT"
        )
        
        payment = Payment.objects.create(
            company=self.company,
            voucher=voucher,
            bank_account=self.bank_ledger,
            payment_date=timezone.now().date(),
            payment_mode="CASH",
            status="DRAFT"
        )
        
        PaymentLine.objects.create(
            payment=payment,
            invoice=self.invoice,
            amount_applied=Decimal("100.00"),
            line_no=1
        )
        
        # Post once
        PaymentPostingService.post_payment_voucher(
            voucher_id=voucher.id,
            user=self.user
        )
        
        # Try to post again
        with self.assertRaises(AlreadyPosted):
            PaymentPostingService.post_payment_voucher(
                voucher_id=voucher.id,
                user=self.user
            )

    def test_advance_payment_without_invoice(self):
        """Test advance payment without linked invoice"""
        # Create voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            voucher_number="RCPT-004",
            date=timezone.now().date(),
            status="DRAFT"
        )
        
        # Create payment with party but no invoice
        payment = Payment.objects.create(
            company=self.company,
            voucher=voucher,
            party=self.customer,
            bank_account=self.bank_ledger,
            payment_date=timezone.now().date(),
            payment_mode="CASH",
            status="DRAFT"
        )
        
        # Create payment line without invoice (advance)
        PaymentLine.objects.create(
            payment=payment,
            invoice=None,  # No invoice - advance payment
            amount_applied=Decimal("500.00"),
            line_no=1
        )
        
        # Post the payment
        posted_voucher = PaymentPostingService.post_payment_voucher(
            voucher_id=voucher.id,
            user=self.user
        )
        
        # Verify posted
        self.assertEqual(posted_voucher.status, "POSTED")
        
        # Verify ledger balances for advance
        customer_balance = LedgerBalance.objects.get(
            company=self.company,
            ledger=self.customer_ledger,
            financial_year=self.fy
        )
        self.assertEqual(customer_balance.balance_cr, Decimal("500.00"))
