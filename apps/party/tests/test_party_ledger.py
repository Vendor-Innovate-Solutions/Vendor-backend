"""
Test Party-Ledger Integration
Tests party management and ledger integration
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.party.models import Party, PartyAddress, PartyBankAccount
from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger
from apps.voucher.models import Voucher, VoucherType, VoucherLine
from core.services.posting import PostingService

User = get_user_model()


class PartyLedgerIntegrationTest(TestCase):
    """Test party-ledger integration"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="PARTY01", name="Party Test Co", legal_name="Party Test Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="partyuser", password="test123")
        
        # Create account groups
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Current Assets", code="CA",
            nature="ASSET", report_type="BS", path="/CA"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company, name="Current Liabilities", code="CL",
            nature="LIABILITY", report_type="BS", path="/CL"
        )
        
        # Create customer ledger
        self.customer_ledger = Ledger.objects.create(
            company=self.company,
            code="CUST001",
            name="Customer Account",
            group=self.asset_group,
            account_type="CUSTOMER",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        # Create supplier ledger
        self.supplier_ledger = Ledger.objects.create(
            company=self.company,
            code="SUP001",
            name="Supplier Account",
            group=self.liability_group,
            account_type="SUPPLIER",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        # Create bank ledger
        self.bank_ledger = Ledger.objects.create(
            company=self.company,
            code="BANK001",
            name="Bank",
            group=self.asset_group,
            account_type="BANK",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        # Create common sequences for voucher auto-numbering (compound keys)
        for code in ['JV', 'PAY', 'RCP', 'SALES', 'SAL']:
            compound_key = f"{self.company.id}:{code}:{self.fy.id}"
            Sequence.objects.create(
                company=self.company,
                key=compound_key,
                prefix=code,
                last_value=0
            )
    
    def test_party_creation_with_ledger(self):
        """Test creating party linked to ledger"""
        party = Party.objects.create(
            company=self.company,
            name="ABC Enterprises",
            party_type="CUSTOMER",
            ledger=self.customer_ledger,
            email="abc@example.com",
            phone="9876543210",
            credit_limit=Decimal("100000.00"),
            credit_days=30
        )
        
        self.assertEqual(party.name, "ABC Enterprises")
        self.assertEqual(party.party_type, "CUSTOMER")
        self.assertEqual(party.ledger, self.customer_ledger)
        self.assertTrue(party.is_active)
    
    def test_party_with_gstin_and_pan(self):
        """Test creating party with GST and PAN"""
        party = Party.objects.create(
            company=self.company,
            name="XYZ Suppliers",
            party_type="SUPPLIER",
            ledger=self.supplier_ledger,
            email="xyz@example.com",
            phone="9876543211",
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            credit_limit=Decimal("50000.00"),
            credit_days=15
        )
        
        self.assertEqual(party.gstin, "29ABCDE1234F1Z5")
        self.assertEqual(party.pan, "ABCDE1234F")
    
    def test_party_address_creation(self):
        """Test creating party addresses"""
        party = Party.objects.create(
            company=self.company,
            name="Test Customer",
            party_type="CUSTOMER",
            ledger=self.customer_ledger,
            phone="1234567890"
        )
        
        # Create billing address
        billing_addr = PartyAddress.objects.create(
            party=party,
            address_type="BILLING",
            line1="123 Main Street",
            line2="Suite 100",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            pincode="400001"
        )
        
        # Create shipping address
        shipping_addr = PartyAddress.objects.create(
            party=party,
            address_type="SHIPPING",
            line1="456 Delivery Lane",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            pincode="400002"
        )
        
        self.assertEqual(party.addresses.count(), 2)
        self.assertEqual(billing_addr.address_type, "BILLING")
        self.assertEqual(shipping_addr.address_type, "SHIPPING")
    
    def test_party_bank_account(self):
        """Test creating party bank accounts"""
        party = Party.objects.create(
            company=self.company,
            name="Supplier with Bank",
            party_type="SUPPLIER",
            ledger=self.supplier_ledger,
            phone="9999999999"
        )
        
        bank_account = PartyBankAccount.objects.create(
            party=party,
            bank_name="HDFC Bank",
            account_number="123456789012",
            ifsc="HDFC0001234",
            branch="Mumbai Branch",
            is_primary=True
        )
        
        self.assertEqual(bank_account.bank_name, "HDFC Bank")
        self.assertTrue(bank_account.is_primary)
        self.assertEqual(party.bank_accounts.count(), 1)
    
    def test_customer_transaction_flow(self):
        """Test customer transaction (sales) flow"""
        # Create customer
        customer = Party.objects.create(
            company=self.company,
            name="Customer ABC",
            party_type="CUSTOMER",
            ledger=self.customer_ledger,
            phone="1111111111",
            credit_limit=Decimal("200000.00"),
            credit_days=30
        )
        
        # Create voucher types
        sales_type = VoucherType.objects.create(
            company=self.company, name="Sales", code="SAL",
            category="SALES", is_accounting=True
        )
        
        # Create sales voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=sales_type,
            financial_year=self.fy,
            voucher_number="SAL001",
            date=date(2024, 5, 1),
            status="DRAFT",
            narration="Sales to customer"
        )
        
        # Debit customer (increasing receivable)
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=customer.ledger,
            entry_type="DR",
            amount=Decimal("50000.00")
        )
        
        # Credit bank (increasing asset)
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.bank_ledger,
            entry_type="CR",
            amount=Decimal("50000.00")
        )
        
        # Post voucher
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted.status, "POSTED")
    
    def test_supplier_transaction_flow(self):
        """Test supplier transaction (purchase payment) flow"""
        # Create supplier
        supplier = Party.objects.create(
            company=self.company,
            name="Supplier XYZ",
            party_type="SUPPLIER",
            ledger=self.supplier_ledger,
            phone="2222222222",
            credit_limit=Decimal("150000.00"),
            credit_days=45
        )
        
        # Create payment voucher type
        payment_type = VoucherType.objects.create(
            company=self.company, name="Payment", code="PAY",
            category="PAYMENT", is_accounting=True
        )
        
        # Create payment voucher
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=payment_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 15),
            status="DRAFT",
            narration="Payment to supplier"
        )
        
        # Debit supplier (reducing payable)
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=supplier.ledger,
            entry_type="DR",
            amount=Decimal("30000.00")
        )
        
        # Credit bank (reducing asset)
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.bank_ledger,
            entry_type="CR",
            amount=Decimal("30000.00")
        )
        
        # Post voucher
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)
        
        self.assertEqual(posted.status, "POSTED")
    
    def test_party_type_both_customer_and_supplier(self):
        """Test party that is both customer and supplier"""
        # Create ledger for dual-type party
        dual_ledger = Ledger.objects.create(
            company=self.company,
            code="DUAL001",
            name="Dual Party Account",
            group=self.asset_group,
            account_type="CUSTOMER",
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy
        )
        
        party = Party.objects.create(
            company=self.company,
            name="Dual Party Ltd",
            party_type="BOTH",
            ledger=dual_ledger,
            phone="3333333333",
            credit_limit=Decimal("100000.00"),
            credit_days=30
        )
        
        self.assertEqual(party.party_type, "BOTH")
    
    def test_party_credit_limit_validation(self):
        """Test party credit limit tracking"""
        customer = Party.objects.create(
            company=self.company,
            name="Credit Test Customer",
            party_type="CUSTOMER",
            ledger=self.customer_ledger,
            phone="4444444444",
            credit_limit=Decimal("25000.00"),
            credit_days=15
        )
        
        # Verify credit limit is set
        self.assertEqual(customer.credit_limit, Decimal("25000.00"))
        self.assertEqual(customer.credit_days, 15)


class PartySearchAndFilterTest(TestCase):
    """Test party search and filtering"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="SEARCH01", name="Search Co", legal_name="Search Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        # Create financial year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.liability_group = AccountGroup.objects.create(
            company=self.company, name="Liabilities", code="LIB",
            nature="LIABILITY", report_type="BS", path="/LIB"
        )
    
    def test_filter_parties_by_type(self):
        """Test filtering parties by type"""
        # Create customers
        for i in range(3):
            ledger = Ledger.objects.create(
                company=self.company,
                code=f"CUST{i:03d}",
                name=f"Customer {i}",
                group=self.asset_group,
                account_type="CUSTOMER",
                opening_balance=Decimal('0.00'),
                opening_balance_fy=self.fy
            )
            Party.objects.create(
                company=self.company,
                name=f"Customer {i}",
                party_type="CUSTOMER",
                ledger=ledger,
                phone=f"111111111{i}"
            )
        
        # Create suppliers
        for i in range(2):
            ledger = Ledger.objects.create(
                company=self.company,
                code=f"SUP{i:03d}",
                name=f"Supplier {i}",
                group=self.liability_group,
                account_type="SUPPLIER",
                opening_balance=Decimal('0.00'),
                opening_balance_fy=self.fy
            )
            Party.objects.create(
                company=self.company,
                name=f"Supplier {i}",
                party_type="SUPPLIER",
                ledger=ledger,
                phone=f"222222222{i}"
            )
        
        # Filter by type
        customers = Party.objects.filter(
            company=self.company,
            party_type="CUSTOMER"
        )
        suppliers = Party.objects.filter(
            company=self.company,
            party_type="SUPPLIER"
        )
        
        self.assertEqual(customers.count(), 3)
        self.assertEqual(suppliers.count(), 2)
    
    def test_filter_active_parties(self):
        """Test filtering active vs inactive parties"""
        # Create active party
        ledger1 = Ledger.objects.create(
            company=self.company, code="ACT001", name="Active Party",
            group=self.asset_group, account_type="CUSTOMER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        active_party = Party.objects.create(
            company=self.company, name="Active Party",
            party_type="CUSTOMER", ledger=ledger1, phone="5555555555",
            is_active=True
        )
        
        # Create inactive party
        ledger2 = Ledger.objects.create(
            company=self.company, code="INACT001", name="Inactive Party",
            group=self.asset_group, account_type="CUSTOMER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        inactive_party = Party.objects.create(
            company=self.company, name="Inactive Party",
            party_type="CUSTOMER", ledger=ledger2, phone="6666666666",
            is_active=False
        )
        
        # Filter active parties
        active = Party.objects.filter(company=self.company, is_active=True)
        inactive = Party.objects.filter(company=self.company, is_active=False)
        
        self.assertEqual(active.count(), 1)
        self.assertEqual(inactive.count(), 1)
    
    def test_party_with_gstin_filtering(self):
        """Test filtering parties by GST registration"""
        ledger1 = Ledger.objects.create(
            company=self.company, code="GST001", name="GST Party",
            group=self.asset_group, account_type="CUSTOMER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        gst_party = Party.objects.create(
            company=self.company, name="GST Registered Party",
            party_type="CUSTOMER", ledger=ledger1, phone="7777777777",
            gstin="29ABCDE1234F1Z5"
        )
        
        ledger2 = Ledger.objects.create(
            company=self.company, code="NOGST001", name="Non-GST Party",
            group=self.asset_group, account_type="CUSTOMER",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        non_gst_party = Party.objects.create(
            company=self.company, name="Non-GST Party",
            party_type="CUSTOMER", ledger=ledger2, phone="8888888888"
        )
        
        # Filter parties with GSTIN
        gst_parties = Party.objects.filter(
            company=self.company
        ).exclude(gstin="")
        
        self.assertEqual(gst_parties.count(), 1)
        self.assertEqual(gst_parties.first().gstin, "29ABCDE1234F1Z5")
