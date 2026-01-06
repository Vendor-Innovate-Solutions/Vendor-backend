""" Comprehensive tests for Credit Limit Guards.

Tests cover:
1. Credit limit enforcement in order confirmation
2. Outstanding calculation accuracy
3. Credit limit exceeded scenarios
4. No credit limit handling
5. Credit status checks
6. Invoice-based outstanding vs ledger balance
7. Partial payments and credit updates
8. Overdue amount tracking

Run: python -m pytest tests/test_credit_guards.py -v
"""

import pytest
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from datetime import date, timedelta

from apps.company.models import Company, FinancialYear, Currency
from apps.party.models import Party
from apps.invoice.models import Invoice
from apps.orders.models import SalesOrder, OrderItem
from apps.products.models import Product, Category
from apps.orders.services.sales_order_service import SalesOrderService
from apps.party.services.credit import (
    get_outstanding_for_party,
    get_credit_status,
    check_credit_limit,
    can_create_order,
    get_overdue_amount
)

User = get_user_model()


class CreditGuardTestCase(TestCase):
    """Base test case for credit guard tests"""
    
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
            name="Credit Test Company",
            code="CRED001",
            legal_name="Credit Test Company Private Limited",
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
            username='credituser',
            password='test123',
            is_internal_user=True
        )
        
        # Create account group for parties
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
        
        # Create ledgers
        ledger_credit = Ledger.objects.create(
            company=self.company,
            code='LED_CREDIT_CUST',
            name='Credit Customer',
            group=debtors_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        ledger_no_limit = Ledger.objects.create(
            company=self.company,
            code='LED_NO_LIMIT',
            name='No Limit Customer',
            group=debtors_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        # Party with credit limit
        self.party = Party.objects.create(
            company=self.company,
            name="Credit Customer",
            code="CCUST001",
            party_type='CUSTOMER',
            ledger=ledger_credit,
            credit_limit=Decimal('100000.00'),
            credit_days=30,
            is_active=True
        )
        
        # Party without credit limit
        self.party_no_limit = Party.objects.create(
            company=self.company,
            name="No Limit Customer",
            code="NLCUST001",
            party_type='CUSTOMER',
            ledger=ledger_no_limit,
            credit_limit=None,
            is_active=True
        )
        
        # Product
        category = Category.objects.create(
            company=self.company,
            name="Test Category"
        )
        
        self.product = Product.objects.create(
            company=self.company,
            name="Test Product",
            category=category,
            price=Decimal('1000.00'),
            available_quantity=1000
        )
        
        self.service = SalesOrderService()


class TestCreditLimitEnforcement(CreditGuardTestCase):
    """Test credit limit enforcement in orders"""
    
    def test_order_within_credit_limit(self):
        """Test that order within credit limit is allowed"""
        # No existing invoices
        order = SalesOrder.objects.create(
            company=self.company,
            party=self.party,
            order_date=date.today(),
            status='DRAFT',
            subtotal=Decimal('50000.00'),
            tax_amount=Decimal('9000.00'),
            grand_total=Decimal('59000.00')
        )
        
        # Should not raise exception
        result = can_create_order(self.party, self.company, Decimal('59000.00'))
        self.assertTrue(result['allowed'])
    
    def test_order_exceeding_credit_limit(self):
        """Test that order exceeding credit limit is blocked"""
        # Create existing outstanding invoice
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-001",
            status='POSTED',
            grand_total=Decimal('80000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Try to create order that would exceed limit
        # Outstanding: 80000, New order: 30000, Total: 110000 > 100000
        result = can_create_order(self.party, self.company, Decimal('30000.00'))
        self.assertFalse(result['allowed'])
        self.assertIn('exceed', result['reason'].lower())
    
    def test_order_at_exact_credit_limit(self):
        """Test order that reaches exactly the credit limit"""
        # Create invoice using 70000
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-002",
            status='POSTED',
            grand_total=Decimal('70000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Order for exactly remaining 30000
        result = can_create_order(self.party, self.company, Decimal('30000.00'))
        self.assertTrue(result['allowed'])
    
    def test_no_credit_limit_allows_any_order(self):
        """Test that party without credit limit can place any order"""
        result = can_create_order(self.party_no_limit, self.company, Decimal('999999.00'))
        self.assertTrue(result['allowed'])


class TestOutstandingCalculation(CreditGuardTestCase):
    """Test outstanding calculation accuracy"""
    
    def test_zero_outstanding_no_invoices(self):
        """Test that outstanding is zero when no invoices"""
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('0.00'))
    
    def test_single_posted_invoice_outstanding(self):
        """Test outstanding with single posted invoice"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            invoice_number="INV-2024-101",
            status='POSTED',
            grand_total=Decimal('25000.00'),
            amount_received=Decimal('0.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('25000.00'))
    
    def test_multiple_invoices_outstanding(self):
        """Test outstanding with multiple invoices"""
        # Invoice 1: Fully outstanding
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-201",
            status='POSTED',
            grand_total=Decimal('15000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Invoice 2: Partially paid
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-202",
            status='PARTIALLY_PAID',
            grand_total=Decimal('30000.00'),
            amount_received=Decimal('18000.00')
        )
        
        # Invoice 3: Fully paid (should not count)
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-203",
            status='PAID',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('20000.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        # 15000 + (30000-18000) = 27000
        self.assertEqual(outstanding, Decimal('27000.00'))
    
    def test_draft_invoices_not_in_outstanding(self):
        """Test that draft invoices don't count toward outstanding"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            status='DRAFT',
            grand_total=Decimal('50000.00')
        )
        
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('0.00'))


class TestCreditStatusCalculation(CreditGuardTestCase):
    """Test credit status calculation"""
    
    def test_credit_status_ok(self):
        """Test credit status when utilization is low"""
        # 30% utilization (30000/100000)
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-301",
            status='POSTED',
            grand_total=Decimal('30000.00'),
            amount_received=Decimal('0.00')
        )
        
        status = get_credit_status(self.party, self.company)
        self.assertEqual(status['status'], 'OK')
        self.assertEqual(status['utilization_percent'], 30.0)
        self.assertEqual(status['available'], Decimal('70000.00'))
    
    def test_credit_status_warning(self):
        """Test credit status when utilization >= 80%"""
        # 85% utilization
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-302",
            status='POSTED',
            grand_total=Decimal('85000.00'),
            amount_received=Decimal('0.00')
        )
        
        status = get_credit_status(self.party, self.company)
        self.assertEqual(status['status'], 'WARNING')
        self.assertGreaterEqual(status['utilization_percent'], 80.0)
    
    def test_credit_status_exceeded(self):
        """Test credit status when limit exceeded"""
        # 110% utilization
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-303",
            status='POSTED',
            grand_total=Decimal('110000.00'),
            amount_received=Decimal('0.00')
        )
        
        status = get_credit_status(self.party, self.company)
        self.assertEqual(status['status'], 'EXCEEDED')
        self.assertGreater(status['utilization_percent'], 100.0)
        self.assertLess(status['available'], Decimal('0.00'))
    
    def test_credit_status_no_limit(self):
        """Test credit status when no limit set"""
        status = get_credit_status(self.party_no_limit, self.company)
        self.assertEqual(status['status'], 'NO_LIMIT')


class TestCreditLimitValidation(CreditGuardTestCase):
    """Test credit limit validation function"""
    
    def test_check_credit_limit_passes(self):
        """Test that check passes when within limit"""
        # Should not raise exception
        try:
            check_credit_limit(
                party=self.party,
                company=self.company,
                additional_amount=Decimal('50000.00')
            )
        except ValidationError:
            self.fail("check_credit_limit raised ValidationError unexpectedly")
    
    def test_check_credit_limit_fails(self):
        """Test that check fails when exceeding limit"""
        # Create outstanding
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-401",
            status='POSTED',
            grand_total=Decimal('90000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Try to add more
        with self.assertRaises(ValidationError) as context:
            check_credit_limit(
                party=self.party,
                company=self.company,
                additional_amount=Decimal('20000.00')  # Would exceed
            )
        
        self.assertIn('credit limit', str(context.exception).lower())


class TestOverdueCalculation(CreditGuardTestCase):
    """Test overdue amount calculation"""
    
    def test_no_overdue_no_invoices(self):
        """Test that overdue is zero when no invoices"""
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('0.00'))
    
    def test_overdue_past_due_date(self):
        """Test overdue amount for invoice past due date"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            invoice_number="INV-2024-501",
            status='POSTED',
            grand_total=Decimal('35000.00'),
            amount_received=Decimal('0.00')
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('35000.00'))
    
    def test_no_overdue_before_due_date(self):
        """Test that future due dates don't count as overdue"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            invoice_number="INV-2024-502",
            status='POSTED',
            grand_total=Decimal('20000.00'),
            amount_received=Decimal('0.00')
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('0.00'))
    
    def test_partial_payment_overdue(self):
        """Test overdue with partial payment"""
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_date=date.today() - timedelta(days=90),
            due_date=date.today() - timedelta(days=60),
            invoice_number="INV-2024-503",
            status='PARTIALLY_PAID',
            grand_total=Decimal('50000.00'),
            amount_received=Decimal('30000.00')
        )
        
        overdue = get_overdue_amount(self.party, self.company)
        self.assertEqual(overdue, Decimal('20000.00'))


class TestInvoiceBasedVsLedgerBased(CreditGuardTestCase):
    """Test that outstanding is invoice-based, not ledger-based"""
    
    def test_invoice_based_outstanding(self):
        """Test that only invoices count, not all ledger entries"""
        # Create posted invoice
        Invoice.objects.create(
            company=self.company,
            party=self.party,
            invoice_number="INV-2024-601",
            status='POSTED',
            grand_total=Decimal('40000.00'),
            amount_received=Decimal('0.00')
        )
        
        # Outstanding should be based on invoice, not ledger
        outstanding = get_outstanding_for_party(self.party, self.company)
        self.assertEqual(outstanding, Decimal('40000.00'))


# Run with: python -m pytest tests/test_credit_guards.py -v --tb=short
