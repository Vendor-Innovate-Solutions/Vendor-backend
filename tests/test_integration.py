"""
Integration Tests for Complete Posting Flow
Tests end-to-end posting scenarios combining multiple modules
"""
from decimal import Decimal
from datetime import date
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model

from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger
from apps.party.models import Party
from apps.inventory.models import (
    StockItem, StockBatch, StockBalance, Godown, UnitOfMeasure
)
from apps.voucher.models import Voucher, VoucherType, VoucherLine
from apps.invoice.models import Invoice, InvoiceLine
from core.services.posting import PostingService

User = get_user_model()


class EndToEndSalesFlowTest(TransactionTestCase):
    """Test complete sales flow from invoice to posting"""
    
    def setUp(self):
        """Set up complete test environment"""
        # Currency
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        # Company
        self.company = Company.objects.create(
            code="E2E01", name="E2E Test Co", legal_name="E2E Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        # Financial Year
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        # User
        self.user = User.objects.create_user(username="e2euser", password="test123")
        
        # Account Groups
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Current Assets", code="CA",
            nature="ASSET", report_type="BS", path="/CA"
        )
        
        self.income_group = AccountGroup.objects.create(
            company=self.company, name="Sales Income", code="INC",
            nature="INCOME", report_type="PL", path="/INC"
        )
        
        # Ledgers
        self.customer_ledger = Ledger.objects.create(
            company=self.company, code="CUST001", name="Customer A/c",
            group=self.asset_group, account_type="CUSTOMER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.sales_ledger = Ledger.objects.create(
            company=self.company, code="SALES001", name="Sales",
            group=self.income_group, account_type="INCOME",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        # Customer
        self.customer = Party.objects.create(
            company=self.company, name="Test Customer Ltd",
            party_type="CUSTOMER", ledger=self.customer_ledger,
            phone="9999999999", credit_limit=Decimal("500000.00"),
            credit_days=30
        )
        
        # Inventory Setup
        self.uom = UnitOfMeasure.objects.create(
            name="Pieces", symbol="PCS", category="QUANTITY"
        )
        
        self.godown = Godown.objects.create(
            company=self.company, name="Main Warehouse", code="WH01"
        )
        
        self.item = StockItem.objects.create(
            company=self.company, sku="PROD001", name="Product A",
            uom=self.uom, is_stock_item=True
        )
        
        self.batch = StockBatch.objects.create(
            company=self.company, item=self.item, batch_number="BATCH001"
        )
        
        StockBalance.objects.create(
            company=self.company, item=self.item, godown=self.godown,
            batch=self.batch, quantity_on_hand=Decimal("100.00")
        )
        
        # Voucher Type
        self.sales_type = VoucherType.objects.create(
            company=self.company, name="Sales", code="SAL",
            category="SALES", is_accounting=True, is_inventory=True
        )
        
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:SAL:{self.fy.id}",
            prefix="SAL",
            last_value=0
        )
    
    def test_complete_sales_invoice_flow(self):
        """Test complete sales flow: invoice -> voucher -> posting"""
        # Create invoice
        from apps.invoice.models import Invoice
        invoice = Invoice.objects.create(
            company=self.company,
            invoice_type="SALES",
            party=self.customer,
            invoice_number="INV001",
            invoice_date=date(2024, 5, 1),
            due_date=date(2024, 5, 31),
            currency=self.currency,
            financial_year=self.fy,
            status="DRAFT"
        )
        
        # Create sales voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.sales_type,
            financial_year=self.fy,
            voucher_number="SAL001",
            date=date(2024, 5, 1),
            status="DRAFT",
            narration="Sale to Test Customer"
        )
        
        # Link invoice to voucher
        invoice.voucher = voucher
        invoice.save()
        
        # Voucher Lines
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=self.customer_ledger, entry_type="DR",
            amount=Decimal("11800.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.sales_ledger, entry_type="CR",
            amount=Decimal("10000.00")
        )
        
        # Tax ledger (simplified)
        tax_group = AccountGroup.objects.create(
            company=self.company, name="Duties & Taxes", code="TAX",
            nature="LIABILITY", report_type="BS", path="/TAX"
        )
        
        tax_ledger = Ledger.objects.create(
            company=self.company, code="GST", name="GST Output",
            group=tax_group, account_type="TAX",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=tax_ledger, entry_type="CR",
            amount=Decimal("1800.00")  # 18% GST
        )
        
        # Stock Movement
        from apps.inventory.models import StockMovement
        
        StockMovement.objects.create(
            company=self.company, voucher=voucher,
            item=self.item, from_godown=self.godown, batch=self.batch,
            quantity=Decimal("10.00"), rate=Decimal("100.00"),
            movement_date=voucher.date
        )
        
        # Post voucher
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)
        
        # Assertions
        self.assertEqual(posted.status, "POSTED")
        
        # Check stock balance updated
        balance = StockBalance.objects.get(
            company=self.company, item=self.item, batch=self.batch
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("90.00"))


class EndToEndPurchaseFlowTest(TransactionTestCase):
    """Test complete purchase flow"""
    
    def setUp(self):
        """Set up test environment"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="PUR01", name="Purchase Test Co", legal_name="Purchase Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="puruser", password="test123")
        
        # Account structure
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Current Assets", code="CA",
            nature="ASSET", report_type="BS", path="/CA"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company, name="Current Liabilities", code="CL",
            nature="LIABILITY", report_type="BS", path="/CL"
        )
        
        self.expense_group = AccountGroup.objects.create(
            company=self.company, name="Direct Expenses", code="EXP",
            nature="EXPENSE", report_type="PL", path="/EXP"
        )
        
        self.supplier_ledger = Ledger.objects.create(
            company=self.company, code="SUP001", name="Supplier A/c",
            group=self.liability_group, account_type="SUPPLIER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.purchase_ledger = Ledger.objects.create(
            company=self.company, code="PUR001", name="Purchases",
            group=self.expense_group, account_type="EXPENSE",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        # Supplier
        self.supplier = Party.objects.create(
            company=self.company, name="Supplier XYZ",
            party_type="SUPPLIER", ledger=self.supplier_ledger,
            phone="8888888888", credit_limit=Decimal("300000.00"),
            credit_days=45
        )
        
        # Inventory
        self.uom = UnitOfMeasure.objects.create(
            name="Kilograms", symbol="KG", category="WEIGHT"
        )
        
        self.godown = Godown.objects.create(
            company=self.company, name="Warehouse", code="WH01"
        )
        
        self.item = StockItem.objects.create(
            company=self.company, sku="RM001", name="Raw Material",
            uom=self.uom, is_stock_item=True
        )
        
        self.batch = StockBatch.objects.create(
            company=self.company, item=self.item, batch_number="BATCH001"
        )
        
        # Voucher Type
        self.purchase_type = VoucherType.objects.create(
            company=self.company, name="Purchase", code="PUR",
            category="PURCHASE", is_accounting=True, is_inventory=True
        )
        
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:PUR:{self.fy.id}",
            prefix="PUR",
            last_value=0
        )
    
    def test_complete_purchase_flow(self):
        """Test complete purchase: receipt -> voucher -> posting"""
        # Create invoice
        from apps.invoice.models import Invoice
        invoice = Invoice.objects.create(
            company=self.company,
            invoice_type="PURCHASE",
            party=self.supplier,
            invoice_number="PINV001",
            invoice_date=date(2024, 5, 1),
            due_date=date(2024, 5, 31),
            currency=self.currency,
            financial_year=self.fy,
            status="DRAFT"
        )
        
        # Create purchase voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.purchase_type,
            financial_year=self.fy,
            voucher_number="PUR001",
            date=date(2024, 5, 1),
            status="DRAFT",
            narration="Purchase from Supplier XYZ"
        )
        
        # Link invoice to voucher
        invoice.voucher = voucher
        invoice.save()
        
        # Voucher Lines
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.purchase_ledger, entry_type="DR",
            amount=Decimal("50000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=5,
            ledger=self.supplier_ledger, entry_type="CR",
            amount=Decimal("50000.00")
        )
        
        # Stock Receipt
        from apps.inventory.models import StockMovement
        
        StockMovement.objects.create(
            company=self.company, voucher=voucher,
            item=self.item, to_godown=self.godown, batch=self.batch,
            quantity=Decimal("100.00"), rate=Decimal("500.00"),
            movement_date=voucher.date
        )
        
        # Post voucher
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)
        
        # Assertions
        self.assertEqual(posted.status, "POSTED")
        
        # Check stock balance created/updated
        balance = StockBalance.objects.get(
            company=self.company, item=self.item, batch=self.batch
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("100.00"))
        # Note: value_fifo calculated from StockMovement rates, not stored


class ComplexMultiModuleTest(TransactionTestCase):
    """Test complex scenarios involving multiple modules"""
    
    def setUp(self):
        """Set up comprehensive test environment"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="CMPLX", name="Complex Test Co", legal_name="Complex Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="complex", password="test123")
        
        # Create account structure
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company, code="BANK", name="Bank",
            group=self.asset_group, account_type="BANK",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.cash_ledger = Ledger.objects.create(
            company=self.company, code="CASH", name="Cash",
            group=self.asset_group, account_type="CASH",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.journal_type = VoucherType.objects.create(
            company=self.company, name="Journal", code="JV",
            category="JOURNAL", is_accounting=True
        )
        
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:JV:{self.fy.id}",
            prefix="JV",
            last_value=0
        )
    
    def test_multiple_vouchers_same_day_sequential_numbers(self):
        """Test that multiple vouchers get sequential numbers"""
        vouchers = []
        
        for i in range(5):
            voucher = Voucher.objects.create(
                company=self.company,
                voucher_type=self.journal_type,
                financial_year=self.fy,
                voucher_number="",  # Auto-generated
                date=date(2024, 5, 1),
                status="DRAFT"
            )
            
            VoucherLine.objects.create(voucher=voucher,
            line_no=6,
                ledger=self.bank_ledger, entry_type="DR",
                amount=Decimal("1000.00")
            )
            
            VoucherLine.objects.create(voucher=voucher,
            line_no=7,
                ledger=self.cash_ledger, entry_type="CR",
                amount=Decimal("1000.00")
            )
            
            service = PostingService()
            posted = service.post_voucher(voucher.id, self.user)
            vouchers.append(posted)
        
        # Verify all posted
        for v in vouchers:
            self.assertEqual(v.status, "POSTED")
        
        # Verify unique numbers
        numbers = [v.voucher_number for v in vouchers]
        self.assertEqual(len(numbers), len(set(numbers)))
    
    def test_idempotent_posting_with_retry(self):
        """Test idempotent posting with API retry simulation"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.journal_type,
            financial_year=self.fy,
            voucher_number="JV001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=8,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("5000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=9,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("5000.00")
        )
        
        # First post with idempotency key
        service = PostingService()
        idempotency_key = "api-request-unique-123"
        
        posted1 = service.post_voucher(
            voucher.id, self.user, idempotency_key=idempotency_key
        )
        self.assertEqual(posted1.status, "POSTED")
        
        # Simulate API retry with same key (should be blocked)
        from core.services.posting import AlreadyPosted
        with self.assertRaises(AlreadyPosted):
            service.post_voucher(
                voucher.id, self.user, idempotency_key=idempotency_key
            )
