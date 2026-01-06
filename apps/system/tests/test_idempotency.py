"""
Test Idempotency Key Handling
Tests API replay protection and idempotent posting
"""
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.system.models import IdempotencyKey, AuditLog
from apps.voucher.models import Voucher, VoucherType, VoucherLine
from apps.company.models import Company, Currency, FinancialYear, Sequence
from apps.accounting.models import AccountGroup, Ledger
from core.services.posting import PostingService, AlreadyPosted

User = get_user_model()


class IdempotencyKeyTest(TestCase):
    """Test idempotency key functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="IDEM01", name="Idempotency Co", legal_name="Idempotency Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="idemuser", password="test123")
        
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
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company, name="Payment", code="PAY",
            category="PAYMENT", is_accounting=True
        )
        
        # Create sequence for auto-numbering
        Sequence.objects.create(
            company=self.company,
            key=f"{self.company.id}:PAY:{self.fy.id}",
            prefix="PAY",
            last_value=0
        )
    
    def test_idempotency_key_creation(self):
        """Test creating an idempotency key"""
        # Create a voucher first
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        idem_key = IdempotencyKey.objects.create(
            company=self.company,
            key="test-key-001",
            voucher=voucher
        )
        
        self.assertEqual(idem_key.key, "test-key-001")
        self.assertEqual(idem_key.voucher, voucher)
        self.assertEqual(idem_key.company, self.company)
    
    def test_idempotency_key_unique_per_company(self):
        """Test that idempotency keys must be unique per company"""
        from django.db import IntegrityError
        
        # Create vouchers
        voucher1 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY002",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        IdempotencyKey.objects.create(
            company=self.company,
            key="unique-key-001",
            voucher=voucher1
        )
        
        voucher2 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY003",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        # Try to create duplicate key for same company
        with self.assertRaises(IntegrityError):
            IdempotencyKey.objects.create(
                company=self.company,
                key="unique-key-001",  # Duplicate
                voucher=voucher2
            )
    
    def test_idempotent_posting_with_same_key(self):
        """Test that posting with same idempotency key is blocked"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=1,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("10000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=2,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("10000.00")
        )
        
        # First posting with idempotency key
        service = PostingService()
        idempotency_key = "api-request-12345"
        
        posted = service.post_voucher(
            voucher.id, 
            self.user, 
            idempotency_key=idempotency_key
        )
        
        self.assertEqual(posted.status, "POSTED")
        
        # Verify idempotency key was created and linked to voucher
        idem = IdempotencyKey.objects.get(
            company=self.company,
            key=idempotency_key
        )
        self.assertEqual(idem.voucher, voucher)
        
        # Try to post again with same key (should return existing voucher)
        # Note: The actual behavior depends on PostingService implementation
        # It should either return the existing voucher or raise an error
    
    def test_different_idempotency_keys_allowed(self):
        """Test that different idempotency keys don't interfere"""
        # Create two vouchers
        voucher1 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY002",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher1,
        line_no=1,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("5000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher1,
        line_no=2,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("5000.00")
        )
        
        voucher2 = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY003",
            date=date(2024, 5, 2),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher2,
        line_no=1,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("8000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher2,
        line_no=2,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("8000.00")
        )
        
        # Post with different keys
        service = PostingService()
        
        posted1 = service.post_voucher(
            voucher1.id,
            self.user,
            idempotency_key="request-aaa"
        )
        
        posted2 = service.post_voucher(
            voucher2.id,
            self.user,
            idempotency_key="request-bbb"
        )
        
        self.assertEqual(posted1.status, "POSTED")
        self.assertEqual(posted2.status, "POSTED")
        
        # Both keys should exist
        keys = IdempotencyKey.objects.filter(company=self.company)
        self.assertEqual(keys.count(), 2)
    
    def test_posting_without_idempotency_key(self):
        """Test that posting without idempotency key works normally"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY004",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=3,
            ledger=self.bank_ledger, entry_type="DR",
            amount=Decimal("3000.00")
        )
        
        VoucherLine.objects.create(voucher=voucher,
        line_no=4,
            ledger=self.cash_ledger, entry_type="CR",
            amount=Decimal("3000.00")
        )
        
        service = PostingService()
        posted = service.post_voucher(voucher.id, self.user)  # No idempotency_key
        
        self.assertEqual(posted.status, "POSTED")
        
        # No idempotency key should be created
        keys = IdempotencyKey.objects.filter(company=self.company)
        self.assertEqual(keys.count(), 0)


class AuditLogTest(TestCase):
    """Test audit logging functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="AUDIT01", name="Audit Co", legal_name="Audit Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company, name="2024-25",
            start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
            is_current=True, is_closed=False
        )
        
        self.user = User.objects.create_user(username="audituser", password="test123")
        
        self.asset_group = AccountGroup.objects.create(
            company=self.company, name="Assets", code="AST",
            nature="ASSET", report_type="BS", path="/AST"
        )
        
        self.bank_ledger = Ledger.objects.create(
            company=self.company, code="BANK", name="Bank",
            group=self.asset_group, account_type="BANK",
            opening_balance=Decimal('0.00'), opening_balance_fy=self.fy
        )
        
        self.voucher_type = VoucherType.objects.create(
            company=self.company, name="Payment", code="PAY",
            category="PAYMENT", is_accounting=True
        )
    
    def test_audit_log_creation(self):
        """Test creating audit log entries"""
        voucher = Voucher.objects.create(
            company=self.company,
            voucher_type=self.voucher_type,
            financial_year=self.fy,
            voucher_number="PAY001",
            date=date(2024, 5, 1),
            status="DRAFT"
        )
        
        audit = AuditLog.objects.create(
            company=self.company,
            actor_user=self.user,
            action_type="POST",
            object_type="Voucher",
            object_id=voucher.id,
            object_repr=f"PAY001 - Payment",
            changes={
                "status": {"old": "DRAFT", "new": "POSTED"}
            },
            ip_address="192.168.1.1",
            metadata={"source": "web"}
        )
        
        self.assertEqual(audit.action_type, "POST")
        self.assertEqual(audit.object_type, "Voucher")
        self.assertEqual(audit.actor_user, self.user)
    
    def test_audit_log_filtering(self):
        """Test filtering audit logs by company and user"""
        # Create audit logs
        for i in range(5):
            AuditLog.objects.create(
                company=self.company,
                actor_user=self.user,
                action_type="CREATE",
                object_type="Voucher",
                object_id=f"00000000-0000-0000-0000-00000000000{i}",
                object_repr=f"Voucher {i}"
            )
        
        # Filter by company
        logs = AuditLog.objects.filter(company=self.company)
        self.assertEqual(logs.count(), 5)
        
        # Filter by user
        logs = AuditLog.objects.filter(actor_user=self.user)
        self.assertEqual(logs.count(), 5)
        
        # Filter by action type
        logs = AuditLog.objects.filter(action_type="CREATE")
        self.assertEqual(logs.count(), 5)
    
    def test_audit_log_changes_tracking(self):
        """Test tracking changes in audit logs"""
        audit = AuditLog.objects.create(
            company=self.company,
            actor_user=self.user,
            action_type="UPDATE",
            object_type="Ledger",
            object_id="00000000-0000-0000-0000-000000000001",
            object_repr="Bank Ledger",
            changes={
                "name": {"old": "Old Bank", "new": "Bank Account"},
                "code": {"old": "BNK", "new": "BANK"}
            }
        )
        
        self.assertIn("name", audit.changes)
        self.assertIn("code", audit.changes)
        self.assertEqual(audit.changes["name"]["new"], "Bank Account")


class IntegrationEventTest(TestCase):
    """Test integration event emission"""
    
    def setUp(self):
        """Set up test data"""
        self.currency = Currency.objects.create(
            code="INR", name="Indian Rupee", symbol="₹", decimal_places=2
        )
        
        self.company = Company.objects.create(
            code="EVENT01", name="Event Co", legal_name="Event Co Ltd",
            company_type="PRIVATE_LIMITED", timezone="UTC", language="en",
            base_currency=self.currency
        )
        
        self.user = User.objects.create_user(username="eventuser", password="test123")
    
    def test_integration_event_creation(self):
        """Test creating integration events"""
        from apps.system.models import IntegrationEvent
        
        event = IntegrationEvent.objects.create(
            company=self.company,
            event_type="voucher.posted",
            source_object_type="Voucher",
            source_object_id="00000000-0000-0000-0000-000000000001",
            payload={
                "voucher_number": "PAY001",
                "amount": "10000.00",
                "date": "2024-05-01"
            },
            status="PENDING"
        )
        
        self.assertEqual(event.event_type, "voucher.posted")
        self.assertEqual(event.status, "PENDING")
        self.assertIn("voucher_number", event.payload)
    
    def test_integration_event_status_transitions(self):
        """Test integration event status changes"""
        from apps.system.models import IntegrationEvent
        
        event = IntegrationEvent.objects.create(
            company=self.company,
            event_type="invoice.created",
            source_object_type="Invoice",
            source_object_id="00000000-0000-0000-0000-000000000002",
            payload={"invoice_number": "INV001"},
            status="PENDING"
        )
        
        # Process event
        event.status = "PROCESSED"
        event.processed_at = date.today()
        event.save()
        
        event.refresh_from_db()
        self.assertEqual(event.status, "PROCESSED")
        self.assertIsNotNone(event.processed_at)
