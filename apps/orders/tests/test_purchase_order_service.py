"""
Test Purchase Order Service
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from apps.company.models import Company, Currency
from apps.company import models as company_models
from apps.party.models import Party
from apps.accounting.models import Ledger, AccountGroup
from apps.inventory.models import StockItem, UnitOfMeasure, PriceList, ItemPrice
from apps.orders.services import PurchaseOrderService


class PurchaseOrderServiceTest(TestCase):
    """Test purchase order service basic functionality"""
    
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
        
        # Create account group
        self.sundry_creditors = AccountGroup.objects.create(
            company=self.company,
            name="Sundry Creditors",
            code="SC001",
            nature="LIABILITY",
            report_type="BS",
            path="/Sundry Creditors"
        )
        
        # Create financial year
        self.fy = company_models.FinancialYear.objects.create(
            company=self.company,
            name="FY2025-26",
            start_date=timezone.now().date().replace(month=4, day=1),
            end_date=(timezone.now().date().replace(month=3, day=31) + timezone.timedelta(days=365))
        )
        
        # Create supplier ledger
        supplier_ledger = Ledger.objects.create(
            company=self.company,
            name="Test Supplier",
            code="SUPP001",
            group=self.sundry_creditors,
            account_type="SUPPLIER",
            opening_balance_fy=self.fy
        )
        
        # Create supplier party
        self.supplier = Party.objects.create(
            company=self.company,
            name="Test Supplier",
            party_type="SUPPLIER",
            ledger=supplier_ledger,
            phone="1234567890"
        )
        
        # Create UOM
        self.uom = UnitOfMeasure.objects.create(
            name="Pieces",
            symbol="PCS",
            category="QUANTITY"
        )
        
        # Create item
        self.item = StockItem.objects.create(
            company=self.company,
            name="Test Product",
            sku="TST-001",
            uom=self.uom,
            is_active=True
        )
        
        # Create price list
        self.price_list = PriceList.objects.create(
            company=self.company,
            name="Supplier Price List",
            currency=self.currency,
            is_default=True,
            valid_from=timezone.now().date()
        )
        
        # Create item price
        self.item_price = ItemPrice.objects.create(
            item=self.item,
            price_list=self.price_list,
            rate=Decimal("80.00"),  # Cost price
            valid_from=timezone.now().date()
        )
    
    def test_create_order(self):
        """Test purchase order creation"""
        order = PurchaseOrderService.create_order(
            company=self.company,
            supplier_party_id=self.supplier.id,
            currency_id=self.currency.id,
            price_list_id=self.price_list.id
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'DRAFT')
        self.assertEqual(order.supplier, self.supplier)
        self.assertIsNotNone(order.order_number)
        self.assertTrue(order.order_number.startswith('PO-'))
    
    def test_add_item(self):
        """Test adding item to purchase order"""
        order = PurchaseOrderService.create_order(
            company=self.company,
            supplier_party_id=self.supplier.id,
            currency_id=self.currency.id,
            price_list_id=self.price_list.id
        )
        
        item_line = PurchaseOrderService.add_item(
            order=order,
            item_id=self.item.id,
            quantity=Decimal("20.00")
        )
        
        self.assertIsNotNone(item_line)
        self.assertEqual(item_line.item, self.item)
        self.assertEqual(item_line.quantity, Decimal("20.00"))
        self.assertEqual(item_line.unit_rate, Decimal("80.00"))
    
    def test_confirm_order(self):
        """Test confirming purchase order"""
        order = PurchaseOrderService.create_order(
            company=self.company,
            supplier_party_id=self.supplier.id,
            currency_id=self.currency.id,
            price_list_id=self.price_list.id
        )
        
        PurchaseOrderService.add_item(
            order=order,
            item_id=self.item.id,
            quantity=Decimal("20.00")
        )
        
        confirmed = PurchaseOrderService.confirm_order(order)
        
        self.assertEqual(confirmed.status, 'CONFIRMED')
        self.assertIsNotNone(confirmed.confirmed_at)
    
    def test_mark_partial_received(self):
        """Test marking order as partially received"""
        order = PurchaseOrderService.create_order(
            company=self.company,
            supplier_party_id=self.supplier.id,
            currency_id=self.currency.id
        )
        
        PurchaseOrderService.add_item(
            order=order,
            item_id=self.item.id,
            quantity=Decimal("20.00")
        )
        
        PurchaseOrderService.confirm_order(order)
        partial = PurchaseOrderService.mark_partial_received(order)
        
        self.assertEqual(partial.status, 'PARTIAL_RECEIVED')
