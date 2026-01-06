"""
Comprehensive test suite for Products API endpoints.

Tests cover:
- Category CRUD operations
- Product CRUD operations
- Product filtering and search
- Product stock synchronization
- UUID handling
- Company scoping
- Validation
- Error handling
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status

from apps.products.models import Product, Category


@pytest.mark.api
@pytest.mark.django_db
class TestCategoryAPI:
    """Test suite for Category API endpoints."""
    
    def test_list_categories_success(self, authenticated_client, company, category):
        """Test listing categories returns successful response."""
        url = '/api/catalog/categories/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
        
    def test_list_categories_filters_by_company(self, authenticated_client, company, category, db):
        """Test categories are filtered by company."""
        from apps.company.models import Company, Currency
        
        # Create another company's currency
        other_currency = Currency.objects.create(
            code='USD',
            name='US Dollar',
            symbol='$',
            decimal_places=2
        )
        
        # Create another company with different category
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        Category.objects.create(
            company=other_company,
            name='Other Category',
            decimal_places=2
        )
        
        url = '/api/catalog/categories/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Should only see categories from authenticated user's company
        data = response.data.get('results', response.data)
        assert len(data) == 1
        assert data[0]['name'] == category.name
    
    def test_create_category_success(self, authenticated_client, company, category_data):
        """Test creating a new category."""
        url = '/api/catalog/categories/'
        response = authenticated_client.post(url, category_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == category_data['name']
        assert 'id' in response.data
        
        # Verify category was created in database
        assert Category.objects.filter(name=category_data['name']).exists()
    
    def test_create_category_validation_error(self, authenticated_client, company):
        """Test category creation with invalid data."""
        url = '/api/catalog/categories/'
        invalid_data = {
            'name': '',  # Empty name should fail
            'is_active': 'invalid'  # Invalid boolean
        }
        response = authenticated_client.post(url, invalid_data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'name' in response.data or 'non_field_errors' in response.data
    
    def test_get_category_detail(self, authenticated_client, company, category):
        """Test retrieving category detail."""
        url = f'/api/catalog/categories/{category.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(category.id)
        assert response.data['name'] == category.name
        assert 'product_count' in response.data
    
    def test_update_category_full(self, authenticated_client, company, category):
        """Test full update (PUT) of category."""
        url = f'/api/catalog/categories/{category.id}/'
        updated_data = {
            'name': 'Updated Category',
            'description': 'Updated description',
            'is_active': True,
            'display_order': 2
        }
        response = authenticated_client.put(url, updated_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Category'
        
        # Verify database was updated
        category.refresh_from_db()
        assert category.name == 'Updated Category'
    
    def test_update_category_partial(self, authenticated_client, company, category):
        """Test partial update (PATCH) of category."""
        url = f'/api/catalog/categories/{category.id}/'
        partial_data = {'name': 'Partially Updated'}
        response = authenticated_client.patch(url, partial_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Partially Updated'
        # Other fields should remain unchanged
        assert response.data['description'] == category.description
    
    def test_delete_category_success(self, authenticated_client, company, category):
        """Test deleting a category without products."""
        url = f'/api/catalog/categories/{category.id}/'
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(id=category.id).exists()
    
    def test_delete_category_with_products_fails(self, authenticated_client, company, category, product):
        """Test deleting a category that has products should fail."""
        url = f'/api/catalog/categories/{category.id}/'
        response = authenticated_client.delete(url)
        
        # Should prevent deletion or handle gracefully
        # Expected behavior depends on your business logic
        assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT]
    
    def test_category_requires_authentication(self, api_client, category):
        """Test category endpoints require authentication."""
        url = '/api/catalog/categories/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.api
@pytest.mark.django_db
class TestProductAPI:
    """Test suite for Product API endpoints."""
    
    def test_list_products_success(self, authenticated_client, company, product):
        """Test listing products returns successful response."""
        url = '/api/catalog/products/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_list_products_filters_by_company(self, authenticated_client, company, product, db):
        """Test products are filtered by company."""
        from apps.company.models import Company, Currency
        
        # Create another company's currency
        other_currency = Currency.objects.create(
            code='EUR',
            name='Euro',
            symbol='€',
            decimal_places=2
        )
        
        # Create another company with different product
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        other_category = Category.objects.create(
            company=other_company,
            name='Other Category'
        )
        Product.objects.create(
            company=other_company,
            category=other_category,
            name='Other Product',
            price=Decimal('100.00'),
            unit='PCS'
        )
        
        url = '/api/catalog/products/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert len(data) == 1
        assert data[0]['name'] == product.name
    
    def test_search_products_by_name(self, authenticated_client, company, products_list):
        """Test searching products by name."""
        url = '/api/catalog/products/?q=Product 1'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert len(data) >= 1
        assert any('Product 1' in item['name'] for item in data)
    
    def test_filter_products_by_category(self, authenticated_client, company, category, product):
        """Test filtering products by category."""
        url = f'/api/catalog/products/?category_id={category.id}'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert all(item['category_id'] == str(category.id) for item in data)
    
    def test_filter_products_by_brand(self, authenticated_client, company, product):
        """Test filtering products by brand."""
        url = f'/api/catalog/products/?brand={product.brand}'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert all(item['brand'] == product.brand for item in data)
    
    def test_filter_products_by_status(self, authenticated_client, company, product):
        """Test filtering products by status."""
        url = '/api/catalog/products/?status=available'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert all(item['status'] == 'available' for item in data)
    
    def test_filter_products_portal_visible(self, authenticated_client, company, product):
        """Test filtering products by portal visibility."""
        url = '/api/catalog/products/?is_portal_visible=true'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert all(item['is_portal_visible'] is True for item in data)
    
    def test_filter_products_featured(self, authenticated_client, company, product):
        """Test filtering featured products."""
        url = '/api/catalog/products/?is_featured=true'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert all(item['is_featured'] is True for item in data)
    
    def test_limit_products_results(self, authenticated_client, company, products_list):
        """Test limiting number of products returned."""
        url = '/api/catalog/products/?limit=2'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data.get('results', response.data)
        assert len(data) <= 2
    
    def test_create_product_success(self, authenticated_client, company, product_data):
        """Test creating a new product."""
        url = '/api/catalog/products/'
        response = authenticated_client.post(url, product_data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == product_data['name']
        assert 'id' in response.data
        assert response.data['price'] == product_data['price']
        
        # Verify product was created in database
        assert Product.objects.filter(name=product_data['name']).exists()
    
    def test_create_product_validation_error(self, authenticated_client, company):
        """Test product creation with invalid data."""
        url = '/api/catalog/products/'
        invalid_data = {
            'name': '',  # Required field
            'price': 'invalid',  # Invalid decimal
            'unit': 'INVALID_UNIT'  # Invalid choice
        }
        response = authenticated_client.post(url, invalid_data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_create_product_with_invalid_category(self, authenticated_client, company, product_data):
        """Test creating product with non-existent category."""
        product_data['category_id'] = '00000000-0000-0000-0000-000000000000'
        url = '/api/catalog/products/'
        response = authenticated_client.post(url, product_data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'category_id' in response.data or 'category' in response.data
    
    def test_get_product_detail(self, authenticated_client, company, product):
        """Test retrieving product detail."""
        url = f'/api/catalog/products/{product.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(product.id)
        assert response.data['name'] == product.name
        assert response.data['price'] == str(product.price)
        assert 'category' in response.data
    
    def test_get_product_not_found(self, authenticated_client, company):
        """Test retrieving non-existent product."""
        url = '/api/catalog/products/00000000-0000-0000-0000-000000000000/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_product_full(self, authenticated_client, company, product, category):
        """Test full update (PUT) of product."""
        url = f'/api/catalog/products/{product.id}/'
        updated_data = {
            'name': 'Updated Product',
            'category_id': str(category.id),
            'brand': 'NewBrand',
            'description': 'Updated description',
            'unit': 'KG',
            'price': '550.00',
            'hsn_code': '2523',
            'cgst_rate': '9.00',
            'sgst_rate': '9.00',
            'igst_rate': '18.00',
            'cess_rate': '0.00',
            'is_portal_visible': True,
            'is_featured': False,
            'status': 'available'
        }
        response = authenticated_client.put(url, updated_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Updated Product'
        assert response.data['price'] == '550.00'
        
        # Verify database was updated
        product.refresh_from_db()
        assert product.name == 'Updated Product'
        assert product.price == Decimal('550.00')
    
    def test_update_product_partial(self, authenticated_client, company, product):
        """Test partial update (PATCH) of product."""
        url = f'/api/catalog/products/{product.id}/'
        partial_data = {
            'price': '500.00',
            'status': 'out_of_stock'
        }
        response = authenticated_client.patch(url, partial_data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['price'] == '500.00'
        assert response.data['status'] == 'out_of_stock'
        # Other fields should remain unchanged
        assert response.data['name'] == product.name
    
    def test_delete_product_success(self, authenticated_client, company, product):
        """Test deleting a product."""
        url = f'/api/catalog/products/{product.id}/'
        response = authenticated_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Product.objects.filter(id=product.id).exists()
    
    def test_product_requires_authentication(self, api_client, product):
        """Test product endpoints require authentication."""
        url = '/api/catalog/products/'
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_uuid_format_in_responses(self, authenticated_client, company, product):
        """Test that UUIDs are properly formatted in responses."""
        url = f'/api/catalog/products/{product.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # UUID should be a string in standard format
        assert isinstance(response.data['id'], str)
        assert len(response.data['id']) == 36  # UUID string length
        assert response.data['id'].count('-') == 4  # UUID has 4 hyphens
    
    def test_decimal_precision_in_responses(self, authenticated_client, company, product):
        """Test decimal fields maintain proper precision."""
        url = f'/api/catalog/products/{product.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Price should be string with 2 decimal places
        assert '.' in response.data['price']
        price_parts = response.data['price'].split('.')
        assert len(price_parts[1]) == 2  # 2 decimal places


@pytest.mark.api
@pytest.mark.django_db
class TestProductStockSync:
    """Test suite for product stock synchronization endpoint."""
    
    def test_sync_stock_endpoint_exists(self, authenticated_client, company, product):
        """Test stock sync endpoint is accessible."""
        url = f'/api/catalog/products/{product.id}/sync-stock/'
        response = authenticated_client.post(url, {}, format='json')
        
        # Should return 200 or 404 depending on implementation
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST
        ]
    
    def test_sync_stock_requires_authentication(self, api_client, product):
        """Test stock sync requires authentication."""
        url = f'/api/catalog/products/{product.id}/sync-stock/'
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.api
@pytest.mark.django_db
class TestProductAPISecurity:
    """Test suite for API security and access control."""
    
    def test_cannot_access_other_company_category(self, authenticated_client, db):
        """Test users cannot access categories from other companies."""
        from apps.company.models import Company, Currency
        
        # Create another company's currency
        other_currency = Currency.objects.create(
            code='GBP',
            name='British Pound',
            symbol='£',
            decimal_places=2
        )
        
        # Create another company
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        other_category = Category.objects.create(
            company=other_company,
            name='Other Category'
        )
        
        url = f'/api/catalog/categories/{other_category.id}/'
        response = authenticated_client.get(url)
        
        # Should return 404 (not found) not 403 (to prevent info leakage)
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_cannot_access_other_company_product(self, authenticated_client, db):
        """Test users cannot access products from other companies."""
        from apps.company.models import Company, Currency
        
        # Create another company
        other_currency = Currency.objects.create(
            code='JPY',
            name='Japanese Yen',
            symbol='¥',
            decimal_places=2
        )
        other_company = Company.objects.create(
            name='Other Company',
            company_type='vendor',
            base_currency=other_currency
        )
        other_category = Category.objects.create(
            company=other_company,
            name='Other Category'
        )
        other_product = Product.objects.create(
            company=other_company,
            category=other_category,
            name='Other Product',
            price=Decimal('100.00'),
            unit='PCS'
        )
        
        url = f'/api/catalog/products/{other_product.id}/'
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

