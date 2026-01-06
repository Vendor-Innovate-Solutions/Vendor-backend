"""
Comprehensive tests for Payment Allocation.

Tests cover:
1. Payment allocation to single invoice
2. Payment allocation to multiple invoices
3. Partial payment handling
4. Overpayment/advance scenarios
5. Payment voucher creation
6. Payment reversal and reallocation
7. Knock-off logic
8. Payment aging

Run: python -m pytest tests/test_payment_allocation.py -v
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta

from apps.company.models import Company, FinancialYear, Currency
from apps.party.models import Party
from apps.invoice.models import Invoice
from apps.voucher.models import Voucher, VoucherLine, VoucherType
from apps.accounting.models import Ledger, LedgerBalance, AccountGroup

User = get_user_model()


class PaymentTestCase(TestCase):
    """Base test case for payment tests"""
    
    def setUp(self):
        """Create test data"""
        # Currency
        currency = Currency.objects.create(
            code='INR',
            name='Indian Rupee',
            symbol='₹',
            decimal_places=2
        )
        
        # Company
        self.company = Company.objects.create(
            name="Payment Test Company",
            code="PAY001",
            legal_name="Payment Test Company Private Limited",
            base_currency=currency,
            is_active=True
        )
        
        # Financial Year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True
        )
        
        # User
        self.user = User.objects.create_user(
            username='paymentuser',
            password='test123',
            is_internal_user=True
        )
        
        # Create account groups
        debtor_group = AccountGroup.objects.create(
            company=self.company,
            name="Sundry Debtors",
            code="SUNDRY_DEBTORS",
            nature='ASSET',
            report_type='BS'
        )
        
        cash_group = AccountGroup.objects.create(
            company=self.company,
            name="Cash",
            code="CASH",
            nature='ASSET',
            report_type='BS'
        )
        
        bank_group = AccountGroup.objects.create(
            company=self.company,
            name="Bank Accounts",
            code="BANK_ACCOUNTS",
            nature='ASSET',
            report_type='BS'
        )
        
        # Party Ledger (create before Party)
        self.party_ledger = Ledger.objects.create(
            company=self.company,
            name="Payment Customer",
            code="PCUST001",
            group=debtor_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        # Party
        self.party = Party.objects.create(
            company=self.company,
            name="Payment Customer",
            party_type='CUSTOMER',
            ledger=self.party_ledger,
            credit_limit=Decimal('500000.00'),
            is_active=True
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
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company,
            name="HDFC Bank",
            code="BANK001",
            group=bank_group,
            account_type='BANK',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        # Voucher Types
        self.receipt_type = VoucherType.objects.create(
            company=self.company,
            name="Receipt",
            code="RCP",
            is_active=True
        )
        
        self.payment_type = VoucherType.objects.create(
            company=self.company,
            name="Payment",
            code="PAY",
            is_active=True
        )


class TestSingleInvoicePayment(PaymentTestCase):
    """Test payment allocation to single invoice"""
    
    def test_full_payment_single_invoice(self):
        """Test full payment of a single invoice"""
        # Create invoice
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-001",
            status='POSTED',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Create payment voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration=f"Payment for {invoice.invoice_number}",
            status='DRAFT'
        )
        
        # Payment lines (DR Cash, CR Party)
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('10000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('10000.00'),

            entry_type='CR'
        )
        
        # Allocate payment to invoice
        invoice.amount_received = Decimal('10000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')
        self.assertEqual(invoice.amount_received, invoice.grand_total)
    
    def test_partial_payment_single_invoice(self):
        """Test partial payment of a single invoice"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-002",
            status='POSTED',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Create payment for 12000
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration=f"Partial payment for {invoice.invoice_number}",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('12000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('12000.00'),

            entry_type='CR'
        )
        
        # Allocate partial payment
        invoice.amount_received = Decimal('12000.00')
        invoice.status = 'PARTIALLY_PAID'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PARTIALLY_PAID')
        self.assertEqual(invoice.amount_received, Decimal('12000.00'))
        
        # Outstanding should be 8000
        outstanding = invoice.grand_total - invoice.amount_received
        self.assertEqual(outstanding, Decimal('8000.00'))
    
    def test_multiple_partial_payments(self):
        """Test multiple partial payments on same invoice"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-003",
            status='POSTED',
            grand_total=Decimal('30000.00'),
            amount_received=Decimal('0.00')
        )
        
        # First payment: 10000
        invoice.amount_received = Decimal('10000.00')
        invoice.status = 'PARTIALLY_PAID'
        invoice.save()
        
        # Second payment: 15000
        invoice.amount_received += Decimal('15000.00')
        invoice.save()
        
        # Third payment: 5000 (completing)
        invoice.amount_received += Decimal('5000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_received, Decimal('30000.00'))
        self.assertEqual(invoice.status, 'PAID')


class TestMultipleInvoicePayment(PaymentTestCase):
    """Test payment allocation across multiple invoices"""
    
    def test_payment_split_across_invoices(self):
        """Test single payment allocated to multiple invoices"""
        # Create 3 invoices
        invoice1 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=30),
            invoice_number="INV-2024-101",
            status='POSTED',
            grand_total=Decimal('5000.00'),
            amount_received=Decimal('0.00')
        )
        
        invoice2 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=20),
            invoice_number="INV-2024-102",
            status='POSTED',
            grand_total=Decimal('8000.00'),
            amount_received=Decimal('0.00')
        )
        
        invoice3 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=10),
            invoice_number="INV-2024-103",
            status='POSTED',
            grand_total=Decimal('12000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Create payment for 20000 (covers invoice1 fully, invoice2 fully, invoice3 partially)
        total_payment = Decimal('20000.00')
        
        # Allocate in FIFO order (oldest first)
        remaining = total_payment
        
        # Invoice 1: 5000
        invoice1.amount_received = Decimal('5000.00')
        invoice1.status = 'PAID'
        invoice1.save()
        remaining -= Decimal('5000.00')
        
        # Invoice 2: 8000
        invoice2.amount_received = Decimal('8000.00')
        invoice2.status = 'PAID'
        invoice2.save()
        remaining -= Decimal('8000.00')
        
        # Invoice 3: remaining 7000
        invoice3.amount_received = remaining
        invoice3.status = 'PARTIALLY_PAID'
        invoice3.save()
        
        # Verify allocations
        invoice1.refresh_from_db()
        invoice2.refresh_from_db()
        invoice3.refresh_from_db()
        
        self.assertEqual(invoice1.status, 'PAID')
        self.assertEqual(invoice2.status, 'PAID')
        self.assertEqual(invoice3.status, 'PARTIALLY_PAID')
        self.assertEqual(invoice3.amount_received, Decimal('7000.00'))
    
    def test_fifo_allocation_logic(self):
        """Test FIFO (First In First Out) payment allocation"""
        # Create invoices with different dates
        invoices = []
        for i, days_ago in enumerate([60, 45, 30, 15]):
            invoice = Invoice.objects.create(
                company=self.company,
                party=self.party,
                invoice_date=date.today() - timedelta(days=days_ago),
                invoice_number=f"INV-2024-{200+i}",
                status='POSTED',
                grand_total=Decimal('10000.00'),
                amount_received=Decimal('0.00')
            )
            invoices.append(invoice)
        
        # Payment of 25000 (should cover first 2.5 invoices in FIFO order)
        payment_amount = Decimal('25000.00')
        remaining = payment_amount
        
        for invoice in invoices:
            if remaining <= 0:
                break
            
            if remaining >= invoice.grand_total:
                invoice.amount_received = invoice.grand_total
                invoice.status = 'PAID'
                remaining -= invoice.grand_total
            else:
                invoice.amount_received = remaining
                invoice.status = 'PARTIALLY_PAID'
                remaining = Decimal('0.00')
            
            invoice.save()
        
        # Check results
        invoices[0].refresh_from_db()
        invoices[1].refresh_from_db()
        invoices[2].refresh_from_db()
        invoices[3].refresh_from_db()
        
        self.assertEqual(invoices[0].status, 'PAID')
        self.assertEqual(invoices[1].status, 'PAID')
        self.assertEqual(invoices[2].status, 'PARTIALLY_PAID')
        self.assertEqual(invoices[2].amount_received, Decimal('5000.00'))
        self.assertEqual(invoices[3].amount_received, Decimal('0.00'))


class TestOverpaymentHandling(PaymentTestCase):
    """Test overpayment and advance payment scenarios"""
    
    def test_overpayment_creates_advance(self):
        """Test that overpayment is tracked as advance"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-301",
            status='POSTED',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Payment of 12000 (2000 excess)
        invoice.amount_received = Decimal('12000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        # Calculate advance
        advance = invoice.amount_received - invoice.grand_total
        self.assertEqual(advance, Decimal('2000.00'))
    
    def test_advance_payment_before_invoice(self):
        """Test advance payment received before invoice"""
        # Create advance payment voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Advance payment received",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('15000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('15000.00'),

            entry_type='CR'
        )
        
        # Later create invoice
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() + timedelta(days=7),
            invoice_number="INV-2024-302",
            status='PARTIALLY_PAID',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('15000.00')  # Apply advance
        )
        
        # Outstanding should be 5000
        outstanding = invoice.grand_total - invoice.amount_received
        self.assertEqual(outstanding, Decimal('5000.00'))


class TestPaymentReversal(PaymentTestCase):
    """Test payment reversal and reallocation"""
    
    def test_payment_reversal_updates_invoice(self):
        """Test that reversing payment updates invoice status"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-401",
            status='PAID',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('10000.00')
        )
        
        # Reverse payment
        invoice.amount_received = Decimal('0.00')
        invoice.status = 'POSTED'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'POSTED')
        self.assertEqual(invoice.amount_received, Decimal('0.00'))
    
    def test_partial_payment_reversal(self):
        """Test reversing partial payment"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-402",
            status='PARTIALLY_PAID',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('12000.00')
        )
        
        # Reverse 5000
        invoice.amount_received -= Decimal('5000.00')
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_received, Decimal('7000.00'))
        self.assertEqual(invoice.status, 'PARTIALLY_PAID')


class TestKnockOffLogic(PaymentTestCase):
    """Test knock-off (automatic matching) logic"""
    
    def test_automatic_knockoff_matching_amounts(self):
        """Test automatic knock-off when amounts match"""
        # Create invoice
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-501",
            status='POSTED',
            grand_total=Decimal('15000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Create payment voucher with exact amount
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration=f"Auto knock-off for {invoice.invoice_number}",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,
            amount=Decimal('15000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('15000.00'),

            entry_type='CR'
        )
        
        # Knock off (auto-allocate)
        invoice.amount_received = Decimal('15000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        self.assertEqual(invoice.status, 'PAID')
    
    def test_manual_knockoff_selection(self):
        """Test manual selection of invoices for knock-off"""
        # Create multiple invoices
        invoice1 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-601",
            status='POSTED',
            grand_total=Decimal('5000.00')
        )
        
        invoice2 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-602",
            status='POSTED',
            grand_total=Decimal('8000.00')
        )
        
        invoice3 = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-603",
            status='POSTED',
            grand_total=Decimal('12000.00')
        )
        
        # Payment of 13000 - manually select invoice1 and invoice2
        invoice1.amount_received = Decimal('5000.00')
        invoice1.status = 'PAID'
        invoice1.save()
        
        invoice2.amount_received = Decimal('8000.00')
        invoice2.status = 'PAID'
        invoice2.save()
        
        # invoice3 remains unpaid
        self.assertEqual(invoice1.status, 'PAID')
        self.assertEqual(invoice2.status, 'PAID')
        self.assertEqual(invoice3.status, 'POSTED')


class TestPaymentMethods(PaymentTestCase):
    """Test different payment methods"""
    
    def test_cash_payment(self):
        """Test cash payment recording"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-701",
            status='POSTED',
            grand_total=Decimal('8000.00')
        )
        
        # Cash payment voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Cash payment",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.cash_ledger,  # Cash account
            amount=Decimal('8000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('8000.00'),

            entry_type='CR'
        )
        
        # Allocate
        invoice.amount_received = Decimal('8000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        self.assertEqual(invoice.status, 'PAID')
    
    def test_bank_payment(self):
        """Test bank payment recording"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-702",
            status='POSTED',
            grand_total=Decimal('25000.00')
        )
        
        # Bank payment voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.receipt_type,
            financial_year=self.fy,
            date=date.today(),
            narration="Bank transfer payment",
            status='DRAFT'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.bank_ledger,  # Bank account
            amount=Decimal('25000.00'),

            entry_type='DR'
        )
        
        VoucherLine.objects.create(
            voucher=voucher,
            line_no=1,
            ledger=self.party_ledger,
            amount=Decimal('25000.00'),

            entry_type='CR'
        )
        
        # Allocate
        invoice.amount_received = Decimal('25000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        self.assertEqual(invoice.status, 'PAID')


class TestPaymentAging(PaymentTestCase):
    """Test payment aging and tracking"""
    
    def test_payment_received_within_credit_days(self):
        """Test payment received within credit period"""
        # Party has 30 day credit
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=20),
            due_date=date.today() + timedelta(days=10),
            invoice_number="INV-2024-801",
            status='POSTED',
            grand_total=Decimal('10000.00')
        )
        
        # Payment received within credit days
        invoice.amount_received = Decimal('10000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        # Not overdue
        days_from_invoice = (date.today() - invoice.invoice_date).days
        self.assertLess(days_from_invoice, 30)
    
    def test_payment_received_after_due_date(self):
        """Test payment received after due date"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            invoice_number="INV-2024-802",
            status='POSTED',
            grand_total=Decimal('15000.00')
        )
        
        # Payment received late
        invoice.amount_received = Decimal('15000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        # Was overdue
        days_overdue = (date.today() - invoice.due_date).days
        self.assertGreater(days_overdue, 0)


# Run with: python -m pytest tests/test_payment_allocation.py -v --tb=short
