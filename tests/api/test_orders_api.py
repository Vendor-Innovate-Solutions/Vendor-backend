"""
Comprehensive test suite for Orders API endpoints.

Tests cover:
- Order creation and validation
- Order status transitions
- Order line items
- Order fulfillment
- Order cancellation
- Pricing calculations
- Tax calculations
- Company scoping
"""
import pytest
from decimal import Decimal
from django.utils import timezone

from apps.orders.models import SalesOrder, OrderItem


@pytest.mark.api
@pytest.mark.django_db
class TestOrderCreation:
    """Test suite for order creation."""
    
    @pytest.fixture
    def order_data(self, party, product):
        """Sample order creation data."""
        return {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'delivery_date': (timezone.now().date() + timezone.timedelta(days=7)).isoformat(),
            'order_type': 'sales',
            'status': 'pending',
            'items': [
                {
                    'product_id': str(product.id),
                    'quantity': '10.00',
                    'unit_price': '450.00',
                    'discount_percent': '5.00'
                }
            ],
            'notes': 'Test order'
        }
    
    def test_create_order_success(self, authenticated_client, company, order_data):
        """Test creating a new order."""
        url = '/api/orders/'
        response = authenticated_client.post(url, order_data, format='json')
        
        assert response.status_code == 201
        assert 'id' in response.data
        assert response.data['order_type'] == 'sales'
        assert len(response.data['items']) == 1
    
    def test_create_order_calculates_totals(self, authenticated_client, company, order_data):
        """Test order creation calculates totals correctly."""
        url = '/api/orders/'
        response = authenticated_client.post(url, order_data, format='json')
        
        assert response.status_code == 201
        # Verify calculated fields
        assert 'subtotal' in response.data
        assert 'tax_amount' in response.data
        assert 'total_amount' in response.data
        
        # Subtotal = quantity * unit_price * (1 - discount/100)
        # 10 * 450 * 0.95 = 4275
        expected_subtotal = Decimal('4275.00')
        assert Decimal(response.data['subtotal']) == expected_subtotal
    
    def test_create_order_without_items_fails(self, authenticated_client, company, party):
        """Test creating order without items fails."""
        url = '/api/orders/'
        data = {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': []  # Empty items
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 400
    
    def test_create_order_with_invalid_party_fails(self, authenticated_client, company, product):
        """Test creating order with invalid party fails."""
        url = '/api/orders/'
        data = {
            'party_id': '00000000-0000-0000-0000-000000000000',
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': [
                {
                    'product_id': str(product.id),
                    'quantity': '10.00',
                    'unit_price': '100.00'
                }
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 400
    
    def test_create_order_with_invalid_product_fails(self, authenticated_client, company, party):
        """Test creating order with invalid product fails."""
        url = '/api/orders/'
        data = {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': [
                {
                    'product_id': '00000000-0000-0000-0000-000000000000',
                    'quantity': '10.00',
                    'unit_price': '100.00'
                }
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 400


@pytest.mark.api
@pytest.mark.django_db
class TestOrderRetrieval:
    """Test suite for order retrieval."""
    
    @pytest.fixture
    def order(self, db, company, party, user):
        """Create test order."""
        return SalesOrder.objects.create(
            company=company,
            party=party,
            order_number='SO-001',
            order_date=timezone.now().date(),
            order_type='sales',
            status='pending',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('180.00'),
            total_amount=Decimal('1180.00'),
            created_by=user
        )
    
    @pytest.fixture
    def order_item(self, db, order, product):
        """Create test order item."""
        return OrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('0.00'),
            line_total=Decimal('1000.00')
        )
    
    def test_list_orders(self, authenticated_client, company, order):
        """Test listing orders."""
        url = '/api/orders/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert len(data) >= 1
    
    def test_get_order_detail(self, authenticated_client, company, order, order_item):
        """Test retrieving order detail."""
        url = f'/api/orders/{order.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        assert response.data['id'] == str(order.id)
        assert response.data['order_number'] == 'SO-001'
        assert 'items' in response.data
        assert len(response.data['items']) == 1
    
    def test_filter_orders_by_status(self, authenticated_client, company, order):
        """Test filtering orders by status."""
        url = '/api/orders/?status=pending'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['status'] == 'pending' for item in data)
    
    def test_filter_orders_by_party(self, authenticated_client, company, order, party):
        """Test filtering orders by party."""
        url = f'/api/orders/?party_id={party.id}'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert all(item['party_id'] == str(party.id) for item in data)
    
    def test_filter_orders_by_date_range(self, authenticated_client, company, order):
        """Test filtering orders by date range."""
        today = timezone.now().date()
        url = f'/api/orders/?date_from={today}&date_to={today}'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        # Should include today's orders
        data = response.data.get('results', response.data)
        assert len(data) >= 1
    
    def test_search_orders_by_number(self, authenticated_client, company, order):
        """Test searching orders by order number."""
        url = '/api/orders/?search=SO-001'
        response = authenticated_client.get(url)
        
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        assert any(item['order_number'] == 'SO-001' for item in data)


@pytest.mark.api
@pytest.mark.django_db
class TestOrderStatusTransitions:
    """Test suite for order status transitions."""
    
    @pytest.fixture
    def order(self, db, company, party, product, user):
        """Create test order with items."""
        order = SalesOrder.objects.create(
            company=company,
            party=party,
            order_number='SO-002',
            order_date=timezone.now().date(),
            order_type='sales',
            status='pending',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('180.00'),
            total_amount=Decimal('1180.00'),
            created_by=user
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=Decimal('10.00'),
            unit_price=Decimal('100.00'),
            line_total=Decimal('1000.00')
        )
        return order
    
    def test_confirm_order(self, authenticated_client, company, order):
        """Test confirming a pending order."""
        url = f'/api/orders/{order.id}/confirm/'
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == 200
        assert response.data['status'] == 'confirmed'
        
        # Verify database updated
        order.refresh_from_db()
        assert order.status == 'confirmed'
    
    def test_cancel_order(self, authenticated_client, company, order):
        """Test cancelling an order."""
        url = f'/api/orders/{order.id}/cancel/'
        data = {'reason': 'Customer request'}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['status'] == 'cancelled'
        
        order.refresh_from_db()
        assert order.status == 'cancelled'
    
    def test_complete_order(self, authenticated_client, company, order):
        """Test completing an order."""
        # First confirm the order
        order.status = 'confirmed'
        order.save()
        
        url = f'/api/orders/{order.id}/complete/'
        response = authenticated_client.post(url, {}, format='json')
        
        assert response.status_code == 200
        assert response.data['status'] == 'completed'
    
    def test_cannot_confirm_cancelled_order(self, authenticated_client, company, order):
        """Test cannot confirm a cancelled order."""
        # Cancel the order first
        order.status = 'cancelled'
        order.save()
        
        url = f'/api/orders/{order.id}/confirm/'
        response = authenticated_client.post(url, {}, format='json')
        
        # Should fail with 400
        assert response.status_code == 400
    
    def test_cannot_cancel_completed_order(self, authenticated_client, company, order):
        """Test cannot cancel a completed order."""
        # Complete the order first
        order.status = 'completed'
        order.save()
        
        url = f'/api/orders/{order.id}/cancel/'
        response = authenticated_client.post(url, {'reason': 'Test'}, format='json')
        
        # Should fail
        assert response.status_code == 400


@pytest.mark.api
@pytest.mark.django_db
class TestOrderUpdate:
    """Test suite for order updates."""
    
    @pytest.fixture
    def order(self, db, company, party, user):
        """Create test order."""
        return SalesOrder.objects.create(
            company=company,
            party=party,
            order_number='SO-003',
            order_date=timezone.now().date(),
            order_type='sales',
            status='pending',
            subtotal=Decimal('1000.00'),
            tax_amount=Decimal('180.00'),
            total_amount=Decimal('1180.00'),
            created_by=user
        )
    
    def test_update_order_notes(self, authenticated_client, company, order):
        """Test updating order notes."""
        url = f'/api/orders/{order.id}/'
        data = {'notes': 'Updated notes'}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['notes'] == 'Updated notes'
    
    def test_update_order_delivery_date(self, authenticated_client, company, order):
        """Test updating delivery date."""
        new_date = (timezone.now().date() + timezone.timedelta(days=10)).isoformat()
        url = f'/api/orders/{order.id}/'
        data = {'delivery_date': new_date}
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == 200
        assert response.data['delivery_date'] == new_date
    
    def test_cannot_update_completed_order(self, authenticated_client, company, order):
        """Test cannot update completed order."""
        order.status = 'completed'
        order.save()
        
        url = f'/api/orders/{order.id}/'
        data = {'notes': 'Try to update'}
        response = authenticated_client.patch(url, data, format='json')
        
        # Should fail or be restricted
        assert response.status_code in [400, 403]


@pytest.mark.api
@pytest.mark.django_db
class TestOrderCalculations:
    """Test suite for order calculation logic."""
    
    def test_line_total_calculation(self, authenticated_client, company, party, product):
        """Test line total calculation with discount."""
        url = '/api/orders/'
        data = {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': [
                {
                    'product_id': str(product.id),
                    'quantity': '10.00',
                    'unit_price': '100.00',
                    'discount_percent': '10.00'
                }
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        # Line total = 10 * 100 * 0.9 = 900
        line_total = Decimal(response.data['items'][0]['line_total'])
        assert line_total == Decimal('900.00')
    
    def test_tax_calculation(self, authenticated_client, company, party, product):
        """Test tax calculation on order."""
        url = '/api/orders/'
        data = {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': [
                {
                    'product_id': str(product.id),
                    'quantity': '10.00',
                    'unit_price': '100.00',
                    'discount_percent': '0.00'
                }
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        # Subtotal = 1000
        # Tax (18%) = 180
        # Total = 1180
        assert Decimal(response.data['subtotal']) == Decimal('1000.00')
        tax_amount = Decimal(response.data['tax_amount'])
        assert tax_amount == Decimal('180.00')
        assert Decimal(response.data['total_amount']) == Decimal('1180.00')
    
    def test_multiple_items_calculation(self, authenticated_client, company, party, product, category, user):
        """Test calculation with multiple items."""
        from apps.products.models import Product
        
        # Create second product
        product2 = Product.objects.create(
            company=company,
            category=category,
            name='Product 2',
            price=Decimal('200.00'),
            unit='PCS',
            cgst_rate=Decimal('9.00'),
            sgst_rate=Decimal('9.00'),
            igst_rate=Decimal('18.00'),
            created_by=user
        )
        
        url = '/api/orders/'
        data = {
            'party_id': str(party.id),
            'order_date': timezone.now().date().isoformat(),
            'order_type': 'sales',
            'items': [
                {
                    'product_id': str(product.id),
                    'quantity': '5.00',
                    'unit_price': '100.00',
                    'discount_percent': '0.00'
                },
                {
                    'product_id': str(product2.id),
                    'quantity': '3.00',
                    'unit_price': '200.00',
                    'discount_percent': '0.00'
                }
            ]
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == 201
        # Subtotal = (5*100) + (3*200) = 500 + 600 = 1100
        assert Decimal(response.data['subtotal']) == Decimal('1100.00')


@pytest.mark.api
@pytest.mark.django_db
class TestOrderSecurity:
    """Test suite for order security and access control."""
    
    def test_cannot_access_other_company_order(self, authenticated_client, db):
        """Test users cannot access orders from other companies."""
        from apps.company.models import Company, Currency
        from apps.party.models import Party
        
        # Create another company
        other_currency = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€'
        )
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        
        # Create financial year for other company
        from apps.company.models import FinancialYear
        other_fy = FinancialYear.objects.create(
            company=other_company,
            name='2024-25',
            start_date=timezone.now().date().replace(month=4, day=1),
            end_date=timezone.now().date().replace(year=timezone.now().year + 1, month=3, day=31),
            is_current=True
        )
        
        # Create account group and ledger
        from apps.accounting.models import Ledger, AccountGroup
        
        debtors_group, _ = AccountGroup.objects.get_or_create(
            company=other_company,
            code='SUNDRY_DEBTORS',
            defaults={
                'name': 'Sundry Debtors',
                'nature': 'ASSET',
                'report_type': 'BS',
                'path': '/SUNDRY_DEBTORS'
            }
        )
        
        other_ledger = Ledger.objects.create(
            company=other_company,
            code='LED_OTHER_PARTY',
            name='Other Party',
            group=debtors_group,
            account_type='DEBTOR',
            opening_balance=Decimal('0.00'),
            opening_balance_fy=other_fy,
            opening_balance_type='DR',
            is_active=True
        )
        
        other_party = Party.objects.create(
            company=other_company,
            name='Other Party',
            party_type='customer',
            ledger=other_ledger
        )
        other_order = SalesOrder.objects.create(
            company=other_company,
            party=other_party,
            order_number='OTHER-001',
            order_date=timezone.now().date(),
            order_type='sales',
            status='pending',
            total_amount=Decimal('1000.00')
        )
        
        url = f'/api/orders/{other_order.id}/'
        response = authenticated_client.get(url)
        
        # Should return 404 (not found)
        assert response.status_code == 404
    
    def test_orders_require_authentication(self, api_client):
        """Test order endpoints require authentication."""
        url = '/api/orders/'
        response = api_client.get(url)
        
        assert response.status_code == 401



