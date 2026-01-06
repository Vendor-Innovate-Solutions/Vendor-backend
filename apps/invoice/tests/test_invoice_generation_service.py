"""
Tests for Invoice Generation Service
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.company.models import Company, Currency, Sequence, FinancialYear
from apps.party.models import Party
from apps.accounting.models import Ledger, AccountGroup
from apps.inventory.models import UnitOfMeasure, StockItem
from apps.orders.models import SalesOrder, OrderItem
from apps.invoice.models import Invoice, InvoiceLine
from apps.invoice.services import InvoiceGenerationService
from core.exceptions import AlreadyPosted

User = get_user_model()


class InvoiceGenerationServiceTest(TestCase):
    """Test invoice generation from sales orders"""

    def setUp(self):
        """Set up test data"""
        # Create currency first
        self.currency = Currency.objects.create(
            code="INR",
            name="Indian Rupee",
            symbol="₹",
            decimal_places=2
        )
        
        # Create company with base currency
        self.company = Company.objects.create(
            code="TST01",
            name="Test Company",
            legal_name="Test Company Ltd",
            company_type="PRIVATE_LIMITED",
            timezone="UTC",
            language="en",
            base_currency=self.currency
        )
        
        # Create account group for sundry debtors
        self.sundry_debtors = AccountGroup.objects.create(
            company=self.company,
            name="Sundry Debtors",
            code="SD001",
            nature="ASSET",
            report_type="BS",
            path="/Sundry Debtors"
        )
        
        # Create financial year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="FY2025-26",
            start_date=timezone.now().date().replace(month=4, day=1),
            end_date=(timezone.now().date().replace(month=3, day=31) + timezone.timedelta(days=365))
        )
        
        # Create customer ledger
        customer_ledger = Ledger.objects.create(
            company=self.company,
            name="Test Customer",
            code="CUST001",
            group=self.sundry_debtors,
            account_type="CUSTOMER",
            opening_balance_fy=self.fy
        )
        
        # Create UOM (global, not company-scoped)
        self.uom = UnitOfMeasure.objects.create(
            name="Pieces",
            symbol="PCS",
            category="QUANTITY"
        )
        
        # Create stock item
        self.item = StockItem.objects.create(
            company=self.company,
            name="Test Product",
            sku="TST-001",
            uom=self.uom,
            is_active=True
        )
        
        # Create customer party with ledger
        self.customer = Party.objects.create(
            company=self.company,
            name="Test Customer",
            party_type="CUSTOMER",
            ledger=customer_ledger,
            phone="1234567890"
        )
        
        # Create user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123"
        )
        
        # Create confirmed sales order
        self.sales_order = SalesOrder.objects.create(
            company=self.company,
            order_number="SO-000001",
            customer=self.customer,
            currency=self.currency,
            order_date=timezone.now().date(),
            status="CONFIRMED",
            confirmed_at=timezone.now(),
            created_by=self.user
        )
        
        # Add order item
        OrderItem.objects.create(
            company=self.company,
            sales_order=self.sales_order,
            item=self.item,
            quantity=Decimal("10.000"),
            unit_rate=Decimal("100.00"),
            uom=self.uom,
            line_no=1
        )

    def test_generate_invoice_from_sales_order(self):
        """Test generating invoice from confirmed sales order"""
        invoice = InvoiceGenerationService.generate_from_sales_order(
            sales_order=self.sales_order,
            created_by=self.user,
            apply_gst=False  # Skip GST for this test
        )
        
        # Verify invoice created
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.status, "DRAFT")
        self.assertEqual(invoice.invoice_type, "SALES")
        self.assertEqual(invoice.party, self.customer)
        self.assertEqual(invoice.sales_order, self.sales_order)
        self.assertEqual(invoice.created_by, self.user)
        
        # Verify invoice lines
        lines = invoice.lines.all()
        self.assertEqual(lines.count(), 1)
        self.assertEqual(lines[0].item, self.item)
        self.assertEqual(lines[0].quantity, Decimal("10.000"))
        self.assertEqual(lines[0].unit_rate, Decimal("100.00"))
        
        # Verify sales order status updated
        self.sales_order.refresh_from_db()
        self.assertEqual(self.sales_order.status, "INVOICE_CREATED_PENDING_POSTING")

    def test_cannot_invoice_draft_order(self):
        """Test that draft orders cannot be invoiced"""
        self.sales_order.status = "DRAFT"
        self.sales_order.save()
        
        with self.assertRaises(Exception):
            InvoiceGenerationService.generate_from_sales_order(
                sales_order=self.sales_order,
                created_by=self.user
            )

    def test_mark_invoiced(self):
        """Test marking sales order as invoiced"""
        # First generate invoice
        self.sales_order.status = "INVOICE_CREATED_PENDING_POSTING"
        self.sales_order.save()
        
        # Mark as invoiced
        updated_order = InvoiceGenerationService.mark_invoiced(self.sales_order)
        
        self.assertEqual(updated_order.status, "INVOICED")
        self.assertIsNotNone(updated_order.invoiced_at)
