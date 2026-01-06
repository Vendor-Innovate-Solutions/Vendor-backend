"""
Test Sales Order Service
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from apps.company.models import Company, Currency
from apps.company import models as company_models
from apps.party.models import Party
from apps.accounting.models import Ledger, AccountGroup
from apps.inventory.models import StockItem, UnitOfMeasure, PriceList, ItemPrice
from apps.orders.services import SalesOrderService


class SalesOrderServiceTest(TestCase):
    """Test sales order service basic functionality"""
    
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
        self.sundry_debtors = AccountGroup.objects.create(
            company=self.company,
            name="Sundry Debtors",
            code="SD001",
            nature="ASSET",
            report_type="BS",
            path="/Sundry Debtors"
        )
        
        # Create financial year
        self.fy = company_models.FinancialYear.objects.create(
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
        
        # Create customer party
        self.customer = Party.objects.create(
            company=self.company,
            name="Test Customer",
            party_type="CUSTOMER",
            ledger=customer_ledger,
            phone="1234567890",
            credit_limit=Decimal("100000.00")
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
            name="Standard Price List",
            currency=self.currency,
            is_default=True,
            valid_from=timezone.now().date()
        )
        
        # Create item price
        self.item_price = ItemPrice.objects.create(
            item=self.item,
            price_list=self.price_list,
            rate=Decimal("100.00"),
            valid_from=timezone.now().date()
        )
    
    def test_create_order(self):
        """Test order creation"""
        order = SalesOrderService.create_order(
            company=self.company,
            customer_party_id=self.customer.id,
            currency_id=self.currency.id,
            price_list_id=self.price_list.id
        )
        
        self.assertIsNotNone(order)
        self.assertEqual(order.status, 'DRAFT')
        self.assertEqual(order.customer, self.customer)
        self.assertIsNotNone(order.order_number)
    
    def test_add_item(self):
        """Test adding item to order"""
        order = SalesOrderService.create_order(
            company=self.company,
            customer_party_id=self.customer.id,
            currency_id=self.currency.id,
            price_list_id=self.price_list.id
        )
        
        item_line = SalesOrderService.add_item(
            order=order,
            item_id=self.item.id,
            quantity=Decimal("10.00")
        )
        
        self.assertIsNotNone(item_line)
        self.assertEqual(item_line.item, self.item)
        self.assertEqual(item_line.quantity, Decimal("10.00"))
        self.assertEqual(item_line.unit_rate, Decimal("100.00"))
