"""
Comprehensive tests for Invoice Generation & Outstanding Calculation.

Tests cover:
1. Invoice generation from orders
2. Outstanding calculation (invoice-based, not ledger)
3. Payment tracking and outstanding updates
4. Partial payment handling
5. Invoice status transitions
6. GST calculation in invoices
7. Multiple invoice outstanding aggregation
8. Invoice aging calculation

Run: python -m pytest tests/test_invoice_outstanding.py -v
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta

from apps.company.models import Company, FinancialYear, Currency
from apps.party.models import Party
from apps.invoice.models import Invoice, InvoiceLine
from apps.orders.models import SalesOrder, OrderItem
from apps.products.models import Product, Category
from apps.party.services.credit import (
    get_outstanding_for_party,
    get_credit_status,
    get_overdue_amount
)

User = get_user_model()


class InvoiceTestCase(TestCase):
    """Base test case for invoice tests"""
    
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
            name="Invoice Test Company",
            code="INV001",
            legal_name="Invoice Test Company Private Limited",
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
            username='invoiceuser',
            password='test123',
            is_internal_user=True
        )
        
        # Create account group and ledger for party
        from apps.accounting.models import Ledger, AccountGroup
        
        debtors_group, _ = AccountGroup.objects.get_or_create(
            company=self.company,
            code='SUNDRY_DEBTORS',
            defaults={
                'name': 'Sundry Debtors',
                'nature': 'ASSET',
                'report_type': 'BS',
                'path': '/SUNDRY_DEBTORS'
            }
        )
        
        party_ledger = Ledger.objects.create(
            company=self.company,
            code='LED_CUST001',
            name='Test Customer',
            group=debtors_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        # Party (Customer)
        self.party = Party.objects.create(
            company=self.company,
            name="Test Customer",
            code="CUST001",
            party_type='CUSTOMER',
            ledger=party_ledger,
            gstin="29XYZAB1234C1Z5",
            credit_limit=Decimal('500000.00'),
            credit_days=30,
            is_active=True
        )


class TestInvoiceGeneration(InvoiceTestCase):
    """Test invoice generation"""
    
    def test_simple_invoice_creation(self):
        """Test basic invoice creation"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status='DRAFT',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),  # 18% GST
            grand_total=Decimal('11800.00')
        )
        
        self.assertEqual(invoice.status, 'DRAFT')
        self.assertEqual(invoice.grand_total, Decimal('11800.00'))
        self.assertIsNone(invoice.invoice_number)  # Not yet posted
    
    def test_invoice_posting_generates_number(self):
        """Test that posting invoice generates invoice number"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            status='DRAFT',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),
            grand_total=Decimal('11800.00')
        )
        
        # Post invoice
        invoice.status = 'POSTED'
        invoice.invoice_number = f"INV-{date.today().year}-001"
        invoice.posted_at = timezone.now()
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'POSTED')
        self.assertIsNotNone(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith('INV'))
    
    def test_invoice_with_lines(self):
        """Test invoice with line items"""
        # Create product
        category = Category.objects.create(
            company=self.company,
            name="Electronics"
        )
        
        product = Product.objects.create(
            company=self.company,
            name="Laptop",
            category=category,
            hsn_code="8471",
            price=Decimal('50000.00'),
            available_quantity=100
        )
        
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            status='DRAFT',
            subtotal=Decimal('0.00'),
            tax_amount=Decimal('0.00'),
            grand_total=Decimal('0.00')
        )
        
        # Add line item
        line = InvoiceLine.objects.create(
            invoice=invoice,
            product=product,
            description="Laptop - Dell XPS",
            quantity=Decimal('2'),
            rate=Decimal('50000.00'),
            amount=Decimal('100000.00'),
            tax_rate=Decimal('18.00'),
            tax_amount=Decimal('18000.00'),
            total_amount=Decimal('118000.00')
        )
        
        # Update invoice totals
        invoice.subtotal = Decimal('100000.00')
        invoice.tax_amount = Decimal('18000.00')
        invoice.grand_total = Decimal('118000.00')
        invoice.save()
        
        self.assertEqual(invoice.lines.count(), 1)
        self.assertEqual(invoice.grand_total, Decimal('118000.00'))


class TestOutstandingCalculation(InvoiceTestCase):
    """Test outstanding calculation logic"""
    
    def test_posted_invoice_outstanding(self):
        """Test outstanding for posted invoice with no payment"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-001",
            status='POSTED',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),
            grand_total=Decimal('11800.00'),
            amount_received=Decimal('0.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('11800.00'))
    
    def test_partially_paid_invoice_outstanding(self):
        """Test outstanding for partially paid invoice"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-002",
            status='PARTIALLY_PAID',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),
            grand_total=Decimal('11800.00'),
            amount_received=Decimal('5000.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('6800.00'))  # 11800 - 5000
    
    def test_fully_paid_invoice_no_outstanding(self):
        """Test that fully paid invoices don't contribute to outstanding"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-003",
            status='PAID',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),
            grand_total=Decimal('11800.00'),
            amount_received=Decimal('11800.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('0.00'))
    
    def test_draft_invoice_not_in_outstanding(self):
        """Test that draft invoices are not included in outstanding"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            status='DRAFT',
            subtotal=Decimal('10000.00'),
            tax_amount=Decimal('1800.00'),
            grand_total=Decimal('11800.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('0.00'))
    
    def test_multiple_invoices_outstanding(self):
        """Test outstanding calculation across multiple invoices"""
        # Invoice 1: Fully posted
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-101",
            status='POSTED',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Invoice 2: Partially paid
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-102",
            status='PARTIALLY_PAID',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('12000.00')
        )
        
        # Invoice 3: Fully paid (should not count)
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-103",
            status='PAID',
            grand_total=Decimal('15000.00'),
            amount_received=Decimal('15000.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        # 10000 + (20000 - 12000) = 18000
        self.assertEqual(outstanding, Decimal('18000.00'))


class TestPaymentTracking(InvoiceTestCase):
    """Test payment tracking and updates"""
    
    def test_payment_updates_amount_received(self):
        """Test that payment updates amount_received"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-201",
            status='POSTED',
            grand_total=Decimal('11800.00'),
            amount_received=Decimal('0.00')
        )
        
        # Receive partial payment
        invoice.amount_received = Decimal('5000.00')
        invoice.status = 'PARTIALLY_PAID'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_received, Decimal('5000.00'))
        self.assertEqual(invoice.status, 'PARTIALLY_PAID')
    
    def test_full_payment_changes_status(self):
        """Test that full payment changes status to PAID"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-202",
            status='POSTED',
            grand_total=Decimal('11800.00'),
            amount_received=Decimal('0.00')
        )
        
        # Receive full payment
        invoice.amount_received = Decimal('11800.00')
        invoice.status = 'PAID'
        invoice.save()
        
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'PAID')
        
        # Outstanding should be zero
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('0.00'))
    
    def test_overpayment_handling(self):
        """Test handling of overpayment"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-203",
            status='POSTED',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Overpayment (advance payment scenario)
        invoice.amount_received = Decimal('12000.00')  # More than grand_total
        invoice.status = 'PAID'
        invoice.save()
        
        # Outstanding should be negative (advance)
        outstanding_calc = invoice.grand_total - invoice.amount_received
        self.assertEqual(outstanding_calc, Decimal('-2000.00'))


class TestCreditStatus(InvoiceTestCase):
    """Test credit status calculation"""
    
    def test_credit_status_with_no_outstanding(self):
        """Test credit status when no outstanding"""
        status = get_credit_status(self.party, self.company)
        
        self.assertEqual(status['credit_limit'], Decimal('500000.00'))
        self.assertEqual(status['outstanding'], Decimal('0.00'))
        self.assertEqual(status['available'], Decimal('500000.00'))
        self.assertEqual(status['utilization_percent'], 0.0)
        self.assertEqual(status['status'], 'OK')
    
    def test_credit_status_with_outstanding(self):
        """Test credit status with outstanding invoices"""
        # Create outstanding invoices
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-301",
            status='POSTED',
            grand_total=Decimal('300000.00'),
            amount_received=Decimal('0.00')
        )
        
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-302",
            status='POSTED',
            grand_total=Decimal('100000.00'),
            amount_received=Decimal('0.00')
        )
        
        status = get_credit_status(self.party, self.company)
        
        self.assertEqual(status['outstanding'], Decimal('400000.00'))
        self.assertEqual(status['available'], Decimal('100000.00'))
        self.assertEqual(status['utilization_percent'], 80.0)  # 400000/500000
        self.assertEqual(status['status'], 'WARNING')  # >= 80%
    
    def test_credit_status_exceeded(self):
        """Test credit status when limit exceeded"""
        # Create invoices exceeding limit
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-401",
            status='POSTED',
            grand_total=Decimal('550000.00'),
            amount_received=Decimal('0.00')
        )
        
        status = get_credit_status(self.party, self.company)
        
        self.assertEqual(status['outstanding'], Decimal('550000.00'))
        self.assertLess(status['available'], Decimal('0.00'))
        self.assertGreater(status['utilization_percent'], 100.0)
        self.assertEqual(status['status'], 'EXCEEDED')
    
    def test_credit_status_no_limit_set(self):
        """Test credit status when no credit limit set"""
        from apps.accounting.models import Ledger, AccountGroup
        
        # Create account group
        debtors_group, _ = AccountGroup.objects.get_or_create(
            company=self.company,
            code='SUNDRY_DEBTORS',
            defaults={
                'name': 'Sundry Debtors',
                'nature': 'ASSET',
                'report_type': 'BS',
                'path': '/SUNDRY_DEBTORS'
            }
        )
        
        # Create ledger
        ledger_no_limit = Ledger.objects.create(
            company=self.company,
            code='LED_CUST002',
            name='No Limit Customer',
            group=debtors_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        party_no_limit = Party.objects.create(
            company=self.company,
            name="No Limit Customer",
            code="CUST002",
            party_type='CUSTOMER',
            ledger=ledger_no_limit,
            credit_limit=None,  # No limit
            is_active=True
        )
        
        status = get_credit_status(party_no_limit, self.company)
        self.assertEqual(status['status'], 'NO_LIMIT')


class TestOverdueCalculation(InvoiceTestCase):
    """Test overdue amount calculation"""
    
    def test_overdue_amount_past_due_date(self):
        """Test overdue calculation for past due date"""
        # Create invoice with past due date
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),  # 30 days overdue
            invoice_number="INV-2024-501",
            status='POSTED',
            grand_total=Decimal('50000.00'),
            amount_received=Decimal('0.00')
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('50000.00'))
    
    def test_no_overdue_before_due_date(self):
        """Test that invoices before due date are not overdue"""
        # Create invoice with future due date
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),  # Future
            invoice_number="INV-2024-502",
            status='POSTED',
            grand_total=Decimal('30000.00'),
            amount_received=Decimal('0.00')
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('0.00'))
    
    def test_partial_overdue_payment(self):
        """Test overdue calculation with partial payment"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            invoice_number="INV-2024-503",
            status='PARTIALLY_PAID',
            grand_total=Decimal('100000.00'),
            amount_received=Decimal('40000.00')  # Partial payment
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('60000.00'))  # 100000 - 40000


class TestInvoiceStatusTransitions(InvoiceTestCase):
    """Test invoice status transitions"""
    
    def test_draft_to_posted(self):
        """Test transition from DRAFT to POSTED"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            status='DRAFT',
            grand_total=Decimal('10000.00')
        )
        
        # Post invoice
        invoice.status = 'POSTED'
        invoice.invoice_number = "INV-2024-601"
        invoice.posted_at = timezone.now()
        invoice.save()
        
        self.assertEqual(invoice.status, 'POSTED')
        self.assertIsNotNone(invoice.invoice_number)
    
    def test_posted_to_partially_paid(self):
        """Test transition from POSTED to PARTIALLY_PAID"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-602",
            status='POSTED',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Partial payment
        invoice.amount_received = Decimal('5000.00')
        invoice.status = 'PARTIALLY_PAID'
        invoice.save()
        
        self.assertEqual(invoice.status, 'PARTIALLY_PAID')
    
    def test_partially_paid_to_paid(self):
        """Test transition from PARTIALLY_PAID to PAID"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-603",
            status='PARTIALLY_PAID',
            grand_total=Decimal('10000.00'),
            amount_received=Decimal('5000.00')
        )
        
        # Complete payment
        invoice.amount_received = Decimal('10000.00')
        invoice.status = 'PAID'
        invoice.save()
        
        self.assertEqual(invoice.status, 'PAID')


class TestInvoiceAging(InvoiceTestCase):
    """Test invoice aging calculation"""
    
    def test_invoice_age_calculation(self):
        """Test calculating days since invoice date"""
        invoice = Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=45),
            invoice_number="INV-2024-701",
            status='POSTED',
            grand_total=Decimal('10000.00')
        )
        
        age_days = (date.today() - invoice.invoice_date).days
        self.assertEqual(age_days, 45)
    
    def test_invoice_aging_buckets(self):
        """Test classification into aging buckets"""
        invoices_data = [
            (15, "0-30"),   # 15 days old
            (45, "31-60"),  # 45 days old
            (75, "61-90"),  # 75 days old
            (120, "90+"),   # 120 days old
        ]
        
        for days, expected_bucket in invoices_data:
            invoice_date = date.today() - timedelta(days=days)
            invoice = Invoice.objects.create(
                company=self.company,
                party=self.party,
                invoice_date=invoice_date,
                invoice_number=f"INV-2024-{700+days}",
                status='POSTED',
                grand_total=Decimal('10000.00')
            )
            
            age = (date.today() - invoice.invoice_date).days
            
            # Classify bucket
            if age <= 30:
                bucket = "0-30"
            elif age <= 60:
                bucket = "31-60"
            elif age <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"
            
            self.assertEqual(bucket, expected_bucket)


# Run with: python -m pytest tests/test_invoice_outstanding.py -v --tb=short
