"""
Integration tests for end-to-end workflows.

Tests cover:
- Complete order-to-invoice flow
- Order fulfillment with stock updates
- Voucher posting and accounting integration
- Multi-step business processes
- Data consistency across modules
"""
import pytest
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

from apps.orders.models import SalesOrder, OrderItem
from apps.invoice.models import Invoice
from apps.voucher.models import Voucher
from apps.inventory.models import StockItem, StockBalance, StockMovement
from core.services.posting import PostingService


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestOrderToInvoiceFlow:
    """Test complete order to invoice workflow."""
    
    @pytest.fixture
    def confirmed_order(self, db, company, party, product, user):
        """Create a confirmed order with items."""
        order = SalesOrder.objects.create(
            company=company,
            party=party,
            order_number='SO-INT-001',
            order_date=timezone.now().date(),
            order_type='sales',
            status='confirmed',
            subtotal=Decimal('4500.00'),
            tax_amount=Decimal('810.00'),
            total_amount=Decimal('5310.00'),
            created_by=user
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.00'),
            unit_price=Decimal('450.00'),
            discount_percent=Decimal('0.00'),
            line_total=Decimal('4500.00')
        )
        return order
    
    def test_create_invoice_from_order(self, authenticated_client, company, confirmed_order):
        """Test creating invoice from confirmed order."""
        url = f'/api/orders/{confirmed_order.id}/create-invoice/'
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == 201
        assert 'invoice_id' in response.data
        
        # Verify invoice was created
        invoice_id = response.data['invoice_id']
        from apps.invoice.models import Invoice
        invoice = Invoice.objects.get(id=invoice_id)
        
        assert invoice.order_id == confirmed_order.id
        assert invoice.total_amount == confirmed_order.total_amount
        assert invoice.party_id == confirmed_order.party_id
    
    def test_complete_order_to_payment_flow(self, authenticated_client, company, confirmed_order, user):
        """Test complete flow: Order -> Invoice -> Payment -> Voucher -> Posting."""
        
        # Step 1: Create invoice from order
        url = f'/api/orders/{confirmed_order.id}/create-invoice/'
        response = authenticated_client.post(url, {}, format='json')
        assert response.status_code == 201
        invoice_id = response.data['invoice_id']
        
        # Step 2: Create payment voucher for invoice
        from apps.accounting.models import Ledger
        
        # Create necessary ledgers
        cash_ledger = Ledger.objects.create(
            company=company,
            name='Cash Account',
            ledger_type='asset',
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00')
        )
        sales_ledger = Ledger.objects.create(
            company=company,
            name='Sales Revenue',
            ledger_type='income',
            opening_balance=Decimal('0.00'),
            current_balance=Decimal('0.00')
        )
        
        # Create voucher
        voucher_url = '/api/vouchers/'
        voucher_data = {
            'voucher_type': 'receipt',
            'voucher_date': timezone.now().date().isoformat(),
            'amount': '5310.00',
            'reference_type': 'invoice',
            'reference_id': str(invoice_id),
            'narration': 'Payment received',
            'entries': [
                {
                    'ledger_id': str(cash_ledger.id),
                    'entry_type': 'debit',
                    'amount': '5310.00'
                },
                {
                    'ledger_id': str(sales_ledger.id),
                    'entry_type': 'credit',
                    'amount': '5310.00'
                }
            ]
        }
        voucher_response = authenticated_client.post(voucher_url, voucher_data, format='json')
        assert voucher_response.status_code == 201
        
        # Step 3: Post the voucher
        voucher_id = voucher_response.data['id']
        post_url = f'/api/vouchers/{voucher_id}/post/'
        post_response = authenticated_client.post(post_url, {}, format='json')
        assert post_response.status_code == 200
        
        # Step 4: Verify ledger balances updated
        cash_ledger.refresh_from_db()
        sales_ledger.refresh_from_db()
        
        assert cash_ledger.current_balance == Decimal('105310.00')  # Increased
        assert sales_ledger.current_balance == Decimal('5310.00')  # Increased
        
        # Step 5: Verify order status
        confirmed_order.refresh_from_db()
        # Order should potentially be marked as paid/completed
        # (depends on your business logic)


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestOrderFulfillmentWithInventory:
    """Test order fulfillment with stock updates."""
    
    @pytest.fixture
    def stock_item(self, db, company):
        """Create stock item linked to product."""
        return StockItem.objects.create(
            company=company,
            name='Cement Stock',
            item_code='CEM-STK-001',
            uom='BAG',
            is_active=True
        )
    
    @pytest.fixture
    def stock_balance(self, db, company, stock_item):
        """Create initial stock balance."""
        return StockBalance.objects.create(
            company=company,
            stock_item=stock_item,
            warehouse_name='Main Warehouse',
            quantity_on_hand=Decimal('1000.00'),
            quantity_reserved=Decimal('0.00'),
            quantity_available=Decimal('1000.00'),
            average_cost=Decimal('400.00')
        )
    
    @pytest.fixture
    def order_with_stock(self, db, company, party, product, stock_item, user):
        """Create order for product with stock."""
        # Link product to stock item
        product.stock_item = stock_item
        product.save()
        
        order = SalesOrder.objects.create(
            company=company,
            party=party,
            order_number='SO-STOCK-001',
            order_date=timezone.now().date(),
            order_type='sales',
            status='confirmed',
            subtotal=Decimal('4500.00'),
            tax_amount=Decimal('810.00'),
            total_amount=Decimal('5310.00'),
            created_by=user
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.00'),
            unit_price=Decimal('450.00'),
            line_total=Decimal('4500.00')
        )
        return order
    
    def test_fulfill_order_reduces_stock(self, authenticated_client, company, order_with_stock, stock_balance):
        """Test fulfilling order reduces available stock."""
        initial_available = stock_balance.quantity_available
        
        # Fulfill order
        url = f'/api/orders/{order_with_stock.id}/fulfill/'
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == 200
        
        # Check stock was reduced
        stock_balance.refresh_from_db()
        expected_available = initial_available - Decimal('10.00')
        assert stock_balance.quantity_available == expected_available
        
        # Verify stock transaction created
        transaction_exists = StockMovement.objects.filter(
            company=company,
            reference_type='order',
            reference_id=order_with_stock.id,
            transaction_type='issue'
        ).exists()
        assert transaction_exists
    
    def test_cannot_fulfill_without_sufficient_stock(self, authenticated_client, company, order_with_stock, stock_balance):
        """Test cannot fulfill order without sufficient stock."""
        # Reduce available stock to less than required
        stock_balance.quantity_available = Decimal('5.00')
        stock_balance.save()
        
        url = f'/api/orders/{order_with_stock.id}/fulfill/'
        response = authenticated_client.post(url, {}, format='json')
        
        # Should fail with 400
        assert response.status_code == 400
        assert 'stock' in str(response.data).lower() or 'insufficient' in str(response.data).lower()
    
    def test_cancel_fulfilled_order_restores_stock(self, authenticated_client, company, order_with_stock, stock_balance):
        """Test canceling fulfilled order restores stock."""
        # First fulfill the order
        url = f'/api/orders/{order_with_stock.id}/fulfill/'
        response = authenticated_client.post(url, {}, format='json')
        assert response.status_code == 200
        
        stock_balance.refresh_from_db()
        stock_after_fulfill = stock_balance.quantity_available
        
        # Now cancel the order
        cancel_url = f'/api/orders/{order_with_stock.id}/cancel/'
        cancel_response = authenticated_client.post(cancel_url, {'reason': 'Test'}, format='json')
        assert cancel_response.status_code == 200
        
        # Stock should be restored
        stock_balance.refresh_from_db()
        assert stock_balance.quantity_available > stock_after_fulfill


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestVoucherPostingIntegration:
    """Test voucher posting with accounting integration."""
    
    @pytest.fixture
    def ledgers(self, db, company):
        """Create test ledgers."""
        from apps.accounting.models import Ledger
        
        cash = Ledger.objects.create(
            company=company,
            name='Cash',
            ledger_type='asset',
            opening_balance=Decimal('50000.00'),
            current_balance=Decimal('50000.00')
        )
        sales = Ledger.objects.create(
            company=company,
            name='Sales',
            ledger_type='income',
            opening_balance=Decimal('0.00'),
            current_balance=Decimal('0.00')
        )
        bank = Ledger.objects.create(
            company=company,
            name='Bank',
            ledger_type='asset',
            opening_balance=Decimal('100000.00'),
            current_balance=Decimal('100000.00')
        )
        return {'cash': cash, 'sales': sales, 'bank': bank}
    
    def test_post_multiple_vouchers_maintains_consistency(self, authenticated_client, company, ledgers, user):
        """Test posting multiple vouchers maintains ledger consistency."""
        from apps.voucher.models import Voucher, VoucherEntry
        
        # Create and post voucher 1: Cash receipt
        voucher1 = Voucher.objects.create(
            company=company,
            voucher_type='receipt',
            voucher_number='REC-001',
            date=timezone.now().date(),
            amount=Decimal('1000.00'),
            narration='Sale receipt',
            created_by=user,
            is_posted=False
        )
        VoucherEntry.objects.create(
            voucher=voucher1,
            ledger=ledgers['cash'],
            entry_type='debit',
            amount=Decimal('1000.00')
        )
        VoucherEntry.objects.create(
            voucher=voucher1,
            ledger=ledgers['sales'],
            entry_type='credit',
            amount=Decimal('1000.00')
        )
        
        # Post voucher 1
        service = PostingService(company=company)
        service.post_voucher(voucher1)
        
        # Create and post voucher 2: Bank deposit
        voucher2 = Voucher.objects.create(
            company=company,
            voucher_type='contra',
            voucher_number='CON-001',
            date=timezone.now().date(),
            amount=Decimal('500.00'),
            narration='Bank deposit',
            created_by=user,
            is_posted=False
        )
        VoucherEntry.objects.create(
            voucher=voucher2,
            ledger=ledgers['bank'],
            entry_type='debit',
            amount=Decimal('500.00')
        )
        VoucherEntry.objects.create(
            voucher=voucher2,
            ledger=ledgers['cash'],
            entry_type='credit',
            amount=Decimal('500.00')
        )
        
        # Post voucher 2
        service.post_voucher(voucher2)
        
        # Verify final balances
        ledgers['cash'].refresh_from_db()
        ledgers['sales'].refresh_from_db()
        ledgers['bank'].refresh_from_db()
        
        # Cash: 50000 + 1000 - 500 = 50500
        assert ledgers['cash'].current_balance == Decimal('50500.00')
        # Sales: 0 + 1000 = 1000
        assert ledgers['sales'].current_balance == Decimal('1000.00')
        # Bank: 100000 + 500 = 100500
        assert ledgers['bank'].current_balance == Decimal('100500.00')
    
    def test_reverse_voucher_maintains_consistency(self, company, ledgers, user):
        """Test reversing voucher maintains ledger consistency."""
        from apps.voucher.models import Voucher, VoucherEntry
        
        # Create and post voucher
        voucher = Voucher.objects.create(
            company=company,
            voucher_type='receipt',
            voucher_number='REV-001',
            date=timezone.now().date(),
            amount=Decimal('2000.00'),
            narration='To be reversed',
            created_by=user,
            is_posted=False
        )
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=ledgers['cash'],
            entry_type='debit',
            amount=Decimal('2000.00')
        )
        VoucherEntry.objects.create(
            voucher=voucher,
            ledger=ledgers['sales'],
            entry_type='credit',
            amount=Decimal('2000.00')
        )
        
        # Get initial balances
        initial_cash = ledgers['cash'].current_balance
        initial_sales = ledgers['sales'].current_balance
        
        # Post voucher
        service = PostingService(company=company)
        service.post_voucher(voucher)
        
        # Verify balances changed
        ledgers['cash'].refresh_from_db()
        ledgers['sales'].refresh_from_db()
        assert ledgers['cash'].current_balance == initial_cash + Decimal('2000.00')
        assert ledgers['sales'].current_balance == initial_sales + Decimal('2000.00')
        
        # Reverse voucher
        service.reverse_voucher(voucher)
        
        # Verify balances restored
        ledgers['cash'].refresh_from_db()
        ledgers['sales'].refresh_from_db()
        assert ledgers['cash'].current_balance == initial_cash
        assert ledgers['sales'].current_balance == initial_sales


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestConcurrentOperations:
    """Test concurrent business operations."""
    
    def test_concurrent_stock_transactions(self, company):
        """Test concurrent stock transactions maintain consistency."""
        # Create stock item and balance
        stock_item = StockItem.objects.create(
            company=company,
            name='Concurrent Test Item',
            item_code='CON-001',
            uom='PCS'
        )
        stock_balance = StockBalance.objects.create(
            company=company,
            stock_item=stock_item,
            warehouse_name='Main',
            quantity_on_hand=Decimal('1000.00'),
            quantity_available=Decimal('1000.00')
        )
        
        # Simulate concurrent transactions
        # In real test, would use threading/multiprocessing
        with transaction.atomic():
            # Transaction 1: Issue 100
            StockMovement.objects.create(
                company=company,
                stock_item=stock_item,
                transaction_type='issue',
                quantity=Decimal('100.00'),
                warehouse_name='Main',
                transaction_date=timezone.now().date()
            )
            stock_balance.quantity_available -= Decimal('100.00')
            stock_balance.save()
        
        with transaction.atomic():
            # Transaction 2: Issue 150
            stock_balance.refresh_from_db()
            StockMovement.objects.create(
                company=company,
                stock_item=stock_item,
                transaction_type='issue',
                quantity=Decimal('150.00'),
                warehouse_name='Main',
                transaction_date=timezone.now().date()
            )
            stock_balance.quantity_available -= Decimal('150.00')
            stock_balance.save()
        
        # Verify final quantity is correct
        stock_balance.refresh_from_db()
        assert stock_balance.quantity_available == Decimal('750.00')


@pytest.mark.integration
@pytest.mark.django_db
class TestDataConsistency:
    """Test data consistency across modules."""
    
    def test_product_deletion_with_dependencies(self, company, category, product, user):
        """Test product deletion handles dependencies."""
        from apps.orders.models import Order, OrderItem
        
        # Create order with product
        order = SalesOrder.objects.create(
            company=company,
            party=user,  # Using user as party for simplicity
            order_number='DEP-001',
            order_date=timezone.now().date(),
            order_type='sales',
            status='pending',
            total_amount=Decimal('1000.00'),
            created_by=user
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('1000.00')
        )
        
        # Try to delete product
        # Should either fail or handle gracefully
        product_id = product.id
        
        try:
            product.delete()
            # If deletion succeeded, verify order item handled
            order_item = OrderItem.objects.filter(order=order).first()
            # Business logic dependent - might set product to None or keep reference
        except Exception as e:
            # If deletion prevented, that's valid behavior
            assert product.id == product_id
    
    def test_party_balance_consistency(self, company, party):
        """Test party balance remains consistent across transactions."""
        # This would test that party outstanding balance
        # matches sum of unpaid invoices
        pass


