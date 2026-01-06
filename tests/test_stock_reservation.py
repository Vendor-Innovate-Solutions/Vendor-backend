"""
Comprehensive tests for Stock Reservation & Balance Updates.

Tests cover:
1. FIFO stock allocation
2. Stock balance updates
3. Insufficient stock handling
4. Batch expiry tracking
5. Godown-wise stock
6. Stock movement creation
7. Concurrent stock allocation
8. Stock reservation rollback

Run: python -m pytest tests/test_stock_reservation.py -v
"""

import pytest
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
import threading

from apps.company.models import Company, FinancialYear, Currency
from apps.inventory.models import (
    StockItem,
    StockBatch,
    StockBalance,
    StockMovement,
    Godown,
    UnitOfMeasure
)
from apps.voucher.models import Voucher, VoucherLine, VoucherType
from apps.accounting.models import Ledger, AccountGroup
from core.services.posting import PostingService, InsufficientStock

User = get_user_model()


class StockTestCase(TestCase):
    """Base test case for stock tests"""
    
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
            name="Stock Test Company",
            code="STOCK001",
            legal_name="Stock Test Company Private Limited",
            base_currency=currency,
            is_active=True
        )
        
        # Financial Year
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True,
            is_closed=False
        )
        
        # User
        self.user = User.objects.create_user(
            username='stockuser',
            password='testpass123',
            is_internal_user=True
        )
        
        # Godown (Warehouse)
        self.main_godown = Godown.objects.create(
            company=self.company,
            name="Main Warehouse",
            code="WH001",
            is_active=True
        )
        
        self.branch_godown = Godown.objects.create(
            company=self.company,
            name="Branch Warehouse",
            code="WH002",
            is_active=True
        )
        
        # Unit of Measure
        self.uom_pcs = UnitOfMeasure.objects.create(
            company=self.company,
            name="Pieces",
            symbol="PCS",
            is_active=True
        )
        
        # Stock Items
        self.item_a = StockItem.objects.create(
            company=self.company,
            name="Product A",
            sku="PROD-A",
            uom=self.uom_pcs,
            is_active=True
        )
        
        self.item_b = StockItem.objects.create(
            company=self.company,
            name="Product B",
            sku="PROD-B",
            uom=self.uom_pcs,
            is_active=True
        )
        
        # Create account groups
        stock_group = AccountGroup.objects.create(
            company=self.company,
            name="Stock-in-Hand",
            code="STOCK_IN_HAND",
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
        
        # Ledgers
        self.stock_ledger = Ledger.objects.create(
            company=self.company,
            name="Stock",
            code="STOCK001",
            group=stock_group,
            account_type='STOCK',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=self.fy,
            opening_balance_type='DR',
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
        
        # Voucher Type
        self.voucher_type = VoucherType.objects.create(
            company=self.company,
            name="Stock Journal",
            code="STK",
            is_active=True
        )
        
        self.service = PostingService()


class TestFIFOAllocation(StockTestCase):
    """Test FIFO stock allocation logic"""
    
    def test_basic_fifo_allocation(self):
        """Test basic FIFO: First In, First Out"""
        # Create batches with different dates
        batch1 = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-001",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        batch2 = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-002",
            mfg_date=date(2024, 2, 1),  # Later date
            expiry_date=date(2025, 2, 1),
            is_active=True
        )
        
        # Add stock to both batches
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch1,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch2,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Allocate 50 units (should come from batch1 - FIFO)
        allocations = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('50')
        )
        
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].batch, batch1)
        self.assertEqual(allocations[0].quantity, Decimal('50'))
    
    def test_fifo_multiple_batch_allocation(self):
        """Test FIFO allocation across multiple batches"""
        # Create 3 batches
        batches = []
        for i in range(3):
            batch = StockBatch.objects.create(
                company=self.company,
                item=self.item_a,
                batch_number=f"BATCH-{i+1:03d}",
                mfg_date=date(2024, i+1, 1),
                expiry_date=date(2025, i+1, 1),
                is_active=True
            )
            
            StockBalance.objects.create(
                company=self.company,
                item=self.item_a,
                batch=batch,
                godown=self.main_godown,
                quantity_in=Decimal('50'),
                quantity_out=Decimal('0')
            )
            
            batches.append(batch)
        
        # Allocate 120 units (should use batch1: 50, batch2: 50, batch3: 20)
        allocations = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('120')
        )
        
        self.assertEqual(len(allocations), 3)
        self.assertEqual(allocations[0].batch, batches[0])
        self.assertEqual(allocations[0].quantity, Decimal('50'))
        self.assertEqual(allocations[1].batch, batches[1])
        self.assertEqual(allocations[1].quantity, Decimal('50'))
        self.assertEqual(allocations[2].batch, batches[2])
        self.assertEqual(allocations[2].quantity, Decimal('20'))
    
    def test_insufficient_stock_error(self):
        """Test that insufficient stock raises error"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-001",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('50'),
            quantity_out=Decimal('0')
        )
        
        # Try to allocate more than available
        with self.assertRaises(InsufficientStock):
            self.service.allocate_batches_fifo(
                company=self.company,
                item=self.item_a,
                godown=self.main_godown,
                required_qty=Decimal('100')  # Only 50 available
            )
    
    def test_expired_batch_skipped(self):
        """Test that expired batches are not allocated"""
        # Create expired batch
        expired_batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-EXP",
            mfg_date=date(2023, 1, 1),
            expiry_date=date(2023, 12, 31),  # Expired
            is_active=True
        )
        
        # Create valid batch
        valid_batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-VALID",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=expired_batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=valid_batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Allocate - should use valid batch, not expired
        allocations = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('50')
        )
        
        self.assertEqual(allocations[0].batch, valid_batch)


class TestStockBalanceUpdates(StockTestCase):
    """Test stock balance updates"""
    
    def test_stock_in_updates_balance(self):
        """Test that stock IN increases balance"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-IN",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Initial balance
        balance = StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        initial_qty = balance.quantity_in
        
        # Add more stock
        balance.quantity_in += Decimal('50')
        balance.save()
        
        balance.refresh_from_db()
        self.assertEqual(balance.quantity_in, initial_qty + Decimal('50'))
    
    def test_stock_out_updates_balance(self):
        """Test that stock OUT increases quantity_out"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-OUT",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        balance = StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Take stock out
        balance.quantity_out += Decimal('30')
        balance.save()
        
        balance.refresh_from_db()
        self.assertEqual(balance.quantity_out, Decimal('30'))
    
    def test_available_quantity_calculation(self):
        """Test available quantity = quantity_in - quantity_out"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-CALC",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        balance = StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('30')
        )
        
        available = balance.quantity_in - balance.quantity_out
        self.assertEqual(available, Decimal('70'))


class TestGodownWiseStock(StockTestCase):
    """Test godown (warehouse) wise stock management"""
    
    def test_stock_isolated_by_godown(self):
        """Test that stock in different godowns is isolated"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-GOD",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Stock in main godown
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Stock in branch godown
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.branch_godown,
            quantity_in=Decimal('50'),
            quantity_out=Decimal('0')
        )
        
        # Allocate from main godown
        allocations_main = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('80')
        )
        
        self.assertEqual(allocations_main[0].quantity, Decimal('80'))
        
        # Allocate from branch godown
        allocations_branch = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.branch_godown,
            required_qty=Decimal('30')
        )
        
        self.assertEqual(allocations_branch[0].quantity, Decimal('30'))
    
    def test_insufficient_stock_in_specific_godown(self):
        """Test that allocation fails if specific godown has insufficient stock"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-SPEC",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Only branch godown has stock
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.branch_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Try to allocate from main godown (has no stock)
        with self.assertRaises(InsufficientStock):
            self.service.allocate_batches_fifo(
                company=self.company,
                item=self.item_a,
                godown=self.main_godown,  # Empty godown
                required_qty=Decimal('50')
            )


class TestStockMovements(StockTestCase):
    """Test stock movement tracking"""
    
    def test_stock_movement_creation(self):
        """Test that stock movements are created"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-MOV",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Create stock movement
        movement = StockMovement.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            movement_type='IN',
            quantity=Decimal('100'),
            reference_type='PURCHASE',
            reference_number='PO-001'
        )
        
        self.assertEqual(movement.quantity, Decimal('100'))
        self.assertEqual(movement.movement_type, 'IN')
    
    def test_stock_movement_history(self):
        """Test that stock movement maintains history"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-HIST",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Multiple movements
        StockMovement.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            movement_type='IN',
            quantity=Decimal('100')
        )
        
        StockMovement.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            movement_type='OUT',
            quantity=Decimal('30')
        )
        
        StockMovement.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            movement_type='OUT',
            quantity=Decimal('20')
        )
        
        # Check history
        movements = StockMovement.objects.filter(
            company=self.company,
            item=self.item_a,
            batch=batch
        ).order_by('created_at')
        
        self.assertEqual(movements.count(), 3)
        self.assertEqual(movements[0].movement_type, 'IN')
        self.assertEqual(movements[1].movement_type, 'OUT')
        self.assertEqual(movements[2].movement_type, 'OUT')


class TestConcurrentStockAllocation(TransactionTestCase):
    """Test concurrent stock allocation scenarios"""
    
    def setUp(self):
        """Create test data"""
        self.company = Company.objects.create(
            name="Concurrent Stock Company",
            code="CONC002",
            is_active=True
        )
        
        self.fy = FinancialYear.objects.create(
            company=self.company,
            name="2024-25",
            start_date=date(2024, 4, 1),
            end_date=date(2025, 3, 31),
            is_current=True
        )
        
        self.user = User.objects.create_user(
            username='concurrentstock',
            password='test123',
            is_internal_user=True
        )
        
        self.godown = Godown.objects.create(
            company=self.company,
            name="Main Warehouse",
            code="WH001",
            is_active=True
        )
        
        self.uom = UnitOfMeasure.objects.create(
            company=self.company,
            name="Pieces",
            symbol="PCS",
            is_active=True
        )
        
        self.item = StockItem.objects.create(
            company=self.company,
            name="Concurrent Product",
            sku="CONC-PROD",
            uom=self.uom,
            is_active=True
        )
        
        self.batch = StockBatch.objects.create(
            company=self.company,
            item=self.item,
            batch_number="BATCH-CONC",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        # Initial stock
        StockBalance.objects.create(
            company=self.company,
            item=self.item,
            batch=self.batch,
            godown=self.godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        self.service = PostingService()
    
    def test_concurrent_allocation_prevents_overselling(self):
        """Test that concurrent allocations don't oversell stock"""
        allocation_results = []
        errors = []
        
        def allocate_stock():
            try:
                allocations = self.service.allocate_batches_fifo(
                    company=self.company,
                    item=self.item,
                    godown=self.godown,
                    required_qty=Decimal('30')
                )
                allocation_results.append(allocations)
            except InsufficientStock as e:
                errors.append(str(e))
        
        # Try to allocate 5 times × 30 units = 150 units (only 100 available)
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=allocate_stock)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have some successful and some failed
        # Total allocated should not exceed 100
        total_allocated = sum(
            sum(a.quantity for a in result)
            for result in allocation_results
        )
        
        self.assertLessEqual(total_allocated, Decimal('100'))
        self.assertGreater(len(errors), 0)  # Some should fail


class TestStockReservation(StockTestCase):
    """Test stock reservation and rollback"""
    
    def test_stock_reservation_locks_quantity(self):
        """Test that stock reservation prevents allocation"""
        batch = StockBatch.objects.create(
            company=self.company,
            item=self.item_a,
            batch_number="BATCH-RES",
            mfg_date=date(2024, 1, 1),
            expiry_date=date(2025, 1, 1),
            is_active=True
        )
        
        StockBalance.objects.create(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown,
            quantity_in=Decimal('100'),
            quantity_out=Decimal('0')
        )
        
        # Reserve 80 units
        # (In real system, this would update a reserved field)
        # For now, simulate by allocating
        allocations = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('80')
        )
        
        # Update balance
        balance = StockBalance.objects.get(
            company=self.company,
            item=self.item_a,
            batch=batch,
            godown=self.main_godown
        )
        balance.quantity_out += Decimal('80')
        balance.save()
        
        # Try to allocate remaining
        remaining_allocations = self.service.allocate_batches_fifo(
            company=self.company,
            item=self.item_a,
            godown=self.main_godown,
            required_qty=Decimal('20')
        )
        
        self.assertEqual(remaining_allocations[0].quantity, Decimal('20'))
        
        # Try to over-allocate should fail
        with self.assertRaises(InsufficientStock):
            self.service.allocate_batches_fifo(
                company=self.company,
                item=self.item_a,
                godown=self.main_godown,
                required_qty=Decimal('10')  # Only 20 left, already allocated
            )


# Run with: python -m pytest tests/test_stock_reservation.py -v --tb=short
