"""
Comprehensive test suite for Inventory API endpoints.

Tests cover:
- Stock item CRUD operations
- Stock balance queries
- Stock transactions
- FIFO valuation
- Stock adjustments
- Warehouse management
- Company scoping
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from apps.inventory.models import StockItem, StockBalance, StockMovement


@pytest.mark.api
@pytest.mark.django_db
class TestStockItemAPI:
    """Test suite for Stock Item API endpoints."""
    
    @pytest.fixture
    def uom(self, db):
        """Create test unit of measure."""
        from apps.inventory.models import UnitOfMeasure
        return UnitOfMeasure.objects.create(
            name='Pieces',
            symbol='PCS',
            category='QUANTITY'
        )
    
    @pytest.fixture
    def stock_item(self, db, company, uom):
        """Create test stock item."""
        return StockItem.objects.create(
            company=company,
            name='Test Item',
            sku='TEST-001',
            description='Test stock item',
            uom=uom,
            is_stock_item=True
        )
    
    def test_list_stock_items(self, authenticated_client, company, stock_item):
        """Test listing stock items."""
        url = '/api/inventory/stock-items/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert len(data) >= 1
    
    def test_create_stock_item(self, authenticated_client, company):
        """Test creating a stock item."""
        url = '/api/inventory/stock-items/'
        data = {
            'name': 'New Stock Item',
            'item_code': 'NEW-001',
            'description': 'New item description',
            'uom': 'KG',
            'is_active': True
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        assert response.data['name'] == 'New Stock Item'
        assert 'id' in response.data
    
    def test_get_stock_item_detail(self, authenticated_client, company, stock_item):
        """Test retrieving stock item detail."""
        url = f'/api/inventory/stock-items/{stock_item.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.data['id'] == str(stock_item.id)
        assert response.data['name'] == stock_item.name
    
    def test_update_stock_item(self, authenticated_client, company, stock_item):
        """Test updating a stock item."""
        url = f'/api/inventory/stock-items/{stock_item.id}/'
        data = {
            'name': 'Updated Item',
            'item_code': stock_item.item_code,
            'uom': 'KG',
            'is_active': True
        }
        response = authenticated_client.put(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['name'] == 'Updated Item'
    
    def test_delete_stock_item(self, authenticated_client, company, stock_item):
        """Test deleting a stock item."""
        url = f'/api/inventory/stock-items/{stock_item.id}/'
        response = authenticated_client.delete(url)
        
        assert response.status_code == 204
        assert not StockItem.objects.filter(id=stock_item.id).exists()
    
    def test_stock_item_filters_by_company(self, authenticated_client, company, stock_item, db):
        """Test stock items are filtered by company."""
        from apps.company.models import Company, Currency
        
        # Create another company
        other_currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$'
        )
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        StockItem.objects.create(
            company=other_company,
            name='Other Item',
            item_code='OTHER-001',
            uom='PCS'
        )
        
        url = '/api/inventory/stock-items/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        # Should only see own company's items
        assert len(data) == 1
        assert data[0]['name'] == stock_item.name


@pytest.mark.api
@pytest.mark.django_db
class TestStockBalanceAPI:
    """Test suite for Stock Balance API endpoints."""
    
    @pytest.fixture
    def stock_item(self, db, company):
        """Create test stock item."""
        return StockItem.objects.create(
            company=company,
            name='Balance Test Item',
            item_code='BAL-001',
            uom='PCS'
        )
    
    @pytest.fixture
    def stock_balance(self, db, company, stock_item):
        """Create test stock balance."""
        return StockBalance.objects.create(
            company=company,
            stock_item=stock_item,
            warehouse_name='Main Warehouse',
            quantity_on_hand=Decimal('100.00'),
            quantity_reserved=Decimal('20.00'),
            quantity_available=Decimal('80.00'),
            average_cost=Decimal('50.00')
        )
    
    def test_list_stock_balances(self, authenticated_client, company, stock_balance):
        """Test listing stock balances."""
        url = '/api/inventory/stock-balances/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert len(data) >= 1
    
    def test_get_stock_balance_by_item(self, authenticated_client, company, stock_item, stock_balance):
        """Test filtering balances by stock item."""
        url = f'/api/inventory/stock-balances/?stock_item_id={stock_item.id}'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['stock_item_id'] == str(stock_item.id) for item in data)
    
    def test_get_stock_balance_by_warehouse(self, authenticated_client, company, stock_balance):
        """Test filtering balances by warehouse."""
        url = '/api/inventory/stock-balances/?warehouse=Main Warehouse'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['warehouse_name'] == 'Main Warehouse' for item in data)
    
    def test_stock_balance_calculations(self, authenticated_client, company, stock_balance):
        """Test balance calculations are correct."""
        url = f'/api/inventory/stock-balances/{stock_balance.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        # Available = On Hand - Reserved
        on_hand = Decimal(response.data['quantity_on_hand'])
        reserved = Decimal(response.data['quantity_reserved'])
        available = Decimal(response.data['quantity_available'])
        
        assert available == on_hand - reserved


@pytest.mark.api
@pytest.mark.django_db
class TestStockTransactionAPI:
    """Test suite for Stock Transaction API endpoints."""
    
    @pytest.fixture
    def stock_item(self, db, company):
        """Create test stock item."""
        return StockItem.objects.create(
            company=company,
            name='Transaction Test Item',
            item_code='TXN-001',
            uom='PCS'
        )
    
    @pytest.fixture
    def stock_balance(self, db, company, stock_item):
        """Create stock balance with initial quantity."""
        return StockBalance.objects.create(
            company=company,
            stock_item=stock_item,
            warehouse_name='Main Warehouse',
            quantity_on_hand=Decimal('100.00'),
            quantity_available=Decimal('100.00'),
            average_cost=Decimal('50.00')
        )
    
    def test_create_stock_receipt(self, authenticated_client, company, stock_item):
        """Test creating a stock receipt transaction."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'receipt',
            'quantity': '50.00',
            'warehouse_name': 'Main Warehouse',
            'transaction_date': timezone.now().date().isoformat(),
            'reference_number': 'GRN-001',
            'unit_cost': '60.00'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        assert response.data['transaction_type'] == 'receipt'
        assert response.data['quantity'] == '50.00'
    
    def test_create_stock_issue(self, authenticated_client, company, stock_item, stock_balance):
        """Test creating a stock issue transaction."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'issue',
            'quantity': '30.00',
            'warehouse_name': 'Main Warehouse',
            'transaction_date': timezone.now().date().isoformat(),
            'reference_number': 'ISS-001'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        assert response.data['transaction_type'] == 'issue'
    
    def test_stock_adjustment(self, authenticated_client, company, stock_item, stock_balance):
        """Test stock adjustment transaction."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'adjustment',
            'quantity': '10.00',
            'warehouse_name': 'Main Warehouse',
            'transaction_date': timezone.now().date().isoformat(),
            'reference_number': 'ADJ-001',
            'notes': 'Physical count adjustment'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
    
    def test_stock_transfer(self, authenticated_client, company, stock_item, stock_balance):
        """Test stock transfer between warehouses."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'transfer_out',
            'quantity': '25.00',
            'warehouse_name': 'Main Warehouse',
            'to_warehouse': 'Secondary Warehouse',
            'transaction_date': timezone.now().date().isoformat(),
            'reference_number': 'TRF-001'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
    
    def test_list_stock_transactions(self, authenticated_client, company, stock_item):
        """Test listing stock transactions."""
        # Create a transaction first
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='receipt',
            quantity=Decimal('50.00'),
            warehouse_name='Main Warehouse',
            transaction_date=timezone.now().date(),
            reference_number='TEST-001'
        )
        
        url = '/api/inventory/stock-transactions/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert len(data) >= 1
    
    def test_filter_transactions_by_item(self, authenticated_client, company, stock_item):
        """Test filtering transactions by stock item."""
        # Create transaction
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='receipt',
            quantity=Decimal('50.00'),
            warehouse_name='Main Warehouse',
            transaction_date=timezone.now().date()
        )
        
        url = f'/api/inventory/stock-transactions/?stock_item_id={stock_item.id}'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['stock_item_id'] == str(stock_item.id) for item in data)
    
    def test_filter_transactions_by_type(self, authenticated_client, company, stock_item):
        """Test filtering transactions by type."""
        # Create transactions of different types
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='receipt',
            quantity=Decimal('50.00'),
            warehouse_name='Main Warehouse',
            transaction_date=timezone.now().date()
        )
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='issue',
            quantity=Decimal('20.00'),
            warehouse_name='Main Warehouse',
            transaction_date=timezone.now().date()
        )
        
        url = '/api/inventory/stock-transactions/?transaction_type=receipt'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['transaction_type'] == 'receipt' for item in data)


@pytest.mark.fifo
@pytest.mark.django_db
class TestFIFOValuation:
    """Test FIFO stock valuation logic."""
    
    @pytest.fixture
    def stock_item(self, db, company):
        """Create test stock item."""
        return StockItem.objects.create(
            company=company,
            name='FIFO Test Item',
            item_code='FIFO-001',
            uom='PCS'
        )
    
    def test_fifo_cost_calculation(self, company, stock_item):
        """Test FIFO cost calculation with multiple receipts."""
        # Receipt 1: 100 units @ 50
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='receipt',
            quantity=Decimal('100.00'),
            unit_cost=Decimal('50.00'),
            warehouse_name='Main',
            transaction_date=timezone.now().date()
        )
        
        # Receipt 2: 50 units @ 60
        StockMovement.objects.create(
            company=company,
            stock_item=stock_item,
            transaction_type='receipt',
            quantity=Decimal('50.00'),
            unit_cost=Decimal('60.00'),
            warehouse_name='Main',
            transaction_date=timezone.now().date()
        )
        
        # Issue 120 units (should consume 100@50 + 20@60)
        # Expected cost = (100*50 + 20*60) / 120 = 6200/120 = 51.67
        
        # Test would verify FIFO logic here
        # This is a placeholder for actual FIFO implementation test
        pass
    
    def test_fifo_maintains_cost_layers(self, company, stock_item):
        """Test FIFO maintains separate cost layers."""
        # This would test the cost layer tracking mechanism
        pass


@pytest.mark.api
@pytest.mark.django_db
class TestInventoryValidation:
    """Test inventory validation rules."""
    
    @pytest.fixture
    def stock_item(self, db, company):
        """Create test stock item."""
        return StockItem.objects.create(
            company=company,
            name='Validation Test Item',
            item_code='VAL-001',
            uom='PCS'
        )
    
    def test_cannot_issue_more_than_available(self, authenticated_client, company, stock_item):
        """Test issuing more than available quantity fails."""
        # Create balance with limited quantity
        StockBalance.objects.create(
            company=company,
            stock_item=stock_item,
            warehouse_name='Main',
            quantity_on_hand=Decimal('10.00'),
            quantity_available=Decimal('10.00')
        )
        
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'issue',
            'quantity': '50.00',  # More than available
            'warehouse_name': 'Main',
            'transaction_date': timezone.now().date().isoformat()
        }
        response = authenticated_client.post(url, data, format='json')
        
        # Should fail with validation error
        assert response.status_code == 400
    
    def test_negative_quantity_not_allowed(self, authenticated_client, company, stock_item):
        """Test negative quantities are rejected."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'receipt',
            'quantity': '-10.00',  # Negative
            'warehouse_name': 'Main',
            'transaction_date': timezone.now().date().isoformat()
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 400
    
    def test_zero_quantity_not_allowed(self, authenticated_client, company, stock_item):
        """Test zero quantities are rejected."""
        url = '/api/inventory/stock-transactions/'
        data = {
            'stock_item_id': str(stock_item.id),
            'transaction_type': 'receipt',
            'quantity': '0.00',  # Zero
            'warehouse_name': 'Main',
            'transaction_date': timezone.now().date().isoformat()
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 400


