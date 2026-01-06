"""
pytest configuration for Vendor ERP Backend

This file configures pytest for running tests with:
- Django settings
- Database setup
- Fixtures
- Markers
"""

import os
import sys
import django
from decimal import Decimal
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')

# Setup Django
django.setup()


def pytest_configure(config):
    """
    Configure pytest with custom markers and settings
    """
    config.addinivalue_line(
        "markers", 
        "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers",
        "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers",
        "api: marks tests as API tests"
    )
    config.addinivalue_line(
        "markers",
        "concurrent: marks tests that test concurrent operations"
    )
    config.addinivalue_line(
        "markers",
        "fifo: marks tests related to FIFO stock valuation"
    )


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================

@pytest.fixture
def api_client():
    """Unauthenticated API client."""
    return APIClient()


@pytest.fixture
def user(db, company):
    """Create a test user with company access."""
    from apps.company.models import CompanyUser
    User = get_user_model()
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User',
        is_internal_user=True,
        active_company=company
    )
    # Create CompanyUser relationship
    CompanyUser.objects.create(
        user=user,
        company=company,
        is_active=True
    )
    return user


@pytest.fixture
def admin_user(db, company):
    """Create an admin user with company access."""
    from apps.company.models import CompanyUser
    User = get_user_model()
    admin = User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        is_internal_user=True,
        active_company=company
    )
    # Create CompanyUser relationship
    CompanyUser.objects.create(
        user=admin,
        company=company,
        is_active=True
    )
    return admin


@pytest.fixture
def auth_token(user):
    """Generate JWT token for test user."""
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


@pytest.fixture
def admin_token(admin_user):
    """Generate JWT token for admin user."""
    refresh = RefreshToken.for_user(admin_user)
    return str(refresh.access_token)


@pytest.fixture
def authenticated_client(api_client, auth_token, company, user):
    """API client with authentication and company context."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token}')
    # Simulate company middleware
    api_client.defaults['HTTP_X_COMPANY_ID'] = str(company.id)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_token, company):
    """API client with admin authentication and company context."""
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
    api_client.defaults['HTTP_X_COMPANY_ID'] = str(company.id)
    return api_client


# ============================================================================
# COMPANY FIXTURES
# ============================================================================

@pytest.fixture
def company(db):
    """Create a test company."""
    from apps.company.models import Company, Currency
    
    # Create base currency if not exists
    currency, _ = Currency.objects.get_or_create(
        code='INR',
        defaults={
            'name': 'Indian Rupee',
            'symbol': '₹',
            'decimal_places': 2
        }
    )
    
    return Company.objects.create(
        code='TEST01',
        name='Test Company Ltd',
        legal_name='Test Company Private Limited',
        company_type='PRIVATE_LIMITED',
        timezone='Asia/Kolkata',
        language='en',
        base_currency=currency,
        is_active=True,
        is_deleted=False
    )


# ============================================================================
# PRODUCTS FIXTURES
# ============================================================================

@pytest.fixture
def uom(db):
    """Create a test unit of measure."""
    from apps.inventory.models import UnitOfMeasure
    return UnitOfMeasure.objects.create(
        name='Pieces',
        symbol='PCS',
        category='QUANTITY'
    )


@pytest.fixture
def category(db, company):
    """Create a test category."""
    from apps.products.models import Category
    return Category.objects.create(
        company=company,
        name='Building Materials',
        description='Construction and building materials',
        is_active=True,
        display_order=1
    )


@pytest.fixture
def product(db, company, category, user):
    """Create a test product."""
    from apps.products.models import Product
    return Product.objects.create(
        company=company,
        category=category,
        name='Portland Cement 53 Grade',
        brand='UltraTech',
        description='High-strength Portland cement',
        price=Decimal('450.00'),
        unit='BAG',
        hsn_code='2523',
        cgst_rate=Decimal('9.00'),
        sgst_rate=Decimal('9.00'),
        igst_rate=Decimal('18.00'),
        is_portal_visible=True,
        is_featured=True,
        status='available',
        created_by=user
    )


@pytest.fixture
def products_list(db, company, category, user):
    """Create multiple products for list testing."""
    from apps.products.models import Product
    products = []
    for i in range(5):
        products.append(
            Product.objects.create(
                company=company,
                category=category,
                name=f'Product {i+1}',
                brand=f'Brand{i+1}',
                price=Decimal(f'{100 + i*50}.00'),
                unit='PCS',
                hsn_code='0000',
                is_portal_visible=True,
                status='available',
                created_by=user
            )
        )
    return products


# ============================================================================
# ACCOUNTING FIXTURES
# ============================================================================

@pytest.fixture
def account_group(db, company):
    """Create a test account group."""
    from apps.accounting.models import AccountGroup
    return AccountGroup.objects.create(
        company=company,
        code='SUNDRY_DEBTORS',
        name='Sundry Debtors',
        nature='ASSET',
        report_type='BS',
        path='/SUNDRY_DEBTORS'
    )


@pytest.fixture
def ledger(db, company, account_group, financial_year):
    """Create a test ledger."""
    from apps.accounting.models import Ledger
    return Ledger.objects.create(
        company=company,
        code='TEST_LEDGER',
        name='Test Ledger',
        group=account_group,
        account_type='CUSTOMER',
        opening_balance=Decimal('0.00'),
        opening_balance_type='DR',
        opening_balance_fy=financial_year,
        is_active=True
    )


@pytest.fixture
def cash_ledger(db, company, financial_year):
    """Create a cash ledger."""
    return create_ledger_with_group(
        company=company,
        code='CASH001',
        name='Cash',
        group_code='CASH',
        group_name='Cash Accounts',
        nature='ASSET',
        account_type='CASH',
        financial_year=financial_year
    )


@pytest.fixture
def bank_ledger(db, company, financial_year):
    """Create a bank ledger."""
    return create_ledger_with_group(
        company=company,
        code='BANK001',
        name='Bank Account',
        group_code='BANK',
        group_name='Bank Accounts',
        nature='ASSET',
        account_type='BANK',
        financial_year=financial_year
    )


@pytest.fixture
def expense_ledger(db, company, financial_year):
    """Create an expense ledger."""
    return create_ledger_with_group(
        company=company,
        code='EXP001',
        name='Office Expenses',
        group_code='EXPENSES',
        group_name='Direct Expenses',
        nature='EXPENSE',
        account_type='EXPENSE',
        financial_year=financial_year
    )


@pytest.fixture
def sales_ledger(db, company, financial_year):
    """Create a sales ledger."""
    return create_ledger_with_group(
        company=company,
        code='SALES001',
        name='Sales',
        group_code='SALES',
        group_name='Sales Accounts',
        nature='INCOME',
        account_type='INCOME',
        financial_year=financial_year
    )


@pytest.fixture
def financial_year(db, company):
    """Create a test financial year."""
    from apps.company.models import FinancialYear
    from datetime import date
    return FinancialYear.objects.create(
        company=company,
        name='FY 2024-25',
        start_date=date(2024, 4, 1),
        end_date=date(2025, 3, 31),
        is_current=True,
        is_closed=False
    )


@pytest.fixture
def create_sequence(db):
    """Helper to create sequence for voucher numbering."""
    from apps.company.models import Sequence
    
    def _create_sequence(company, voucher_type, financial_year):
        """Create sequence with proper key format."""
        key = f"{company.id}:{voucher_type.code}:{financial_year.id}"
        return Sequence.objects.get_or_create(
            company=company,
            key=key,
            defaults={
                'prefix': voucher_type.code,
                'last_value': 0,
                'reset_period': 'YEARLY'
            }
        )[0]
    
    return _create_sequence


@pytest.fixture
def party_with_ledger(db, company, financial_year):
    """Create a party with associated ledger."""
    from apps.party.models import Party
    from apps.accounting.models import Ledger, AccountGroup
    from decimal import Decimal
    
    def _create_party(name, party_type='CUSTOMER'):
        # Create account group for party
        if party_type == 'CUSTOMER':
            group_code = 'SUNDRY_DEBTORS'
            group_name = 'Sundry Debtors'
            nature = 'ASSET'
            account_type = 'DEBTOR'
        else:
            group_code = 'SUNDRY_CREDITORS'
            group_name = 'Sundry Creditors'
            nature = 'LIABILITY'
            account_type = 'CREDITOR'
        
        group, _ = AccountGroup.objects.get_or_create(
            company=company,
            code=group_code,
            defaults={
                'name': group_name,
                'nature': nature,
                'report_type': 'BS',
                'path': f'/{group_code}'
            }
        )
        
        # Create ledger
        ledger = Ledger.objects.create(
            company=company,
            code=f'LED_{name[:10].upper().replace(" ", "_")}',
            name=name,
            group=group,
            account_type=account_type,
            opening_balance=Decimal('0.00'),
            opening_balance_fy=financial_year,
            opening_balance_type='DR' if party_type == 'CUSTOMER' else 'CR',
            is_active=True
        )
        
        # Create party
        party = Party.objects.create(
            company=company,
            name=name,
            party_type=party_type,
            ledger=ledger,
            is_active=True
        )
        
        return party
    
    return _create_party


def create_ledger_with_group(company, code, name, group_code, group_name, nature, account_type, financial_year):
    """Helper to create a ledger with its account group."""
    from apps.accounting.models import AccountGroup, Ledger
    
    # Create or get account group
    group, _ = AccountGroup.objects.get_or_create(
        company=company,
        code=group_code,
        defaults={
            'name': group_name,
            'nature': nature,
            'report_type': 'BS' if nature in ['ASSET', 'LIABILITY', 'EQUITY'] else 'PL',
            'path': f'/{group_code}'
        }
    )
    
    # Create ledger
    return Ledger.objects.create(
        company=company,
        code=code,
        name=name,
        group=group,
        account_type=account_type,
        opening_balance=Decimal('0.00'),
        opening_balance_type='DR' if nature == 'ASSET' else 'CR',
        opening_balance_fy=financial_year,
        is_active=True
    )


# ============================================================================
# PARTY FIXTURES
# ============================================================================

@pytest.fixture
def party(db, company, ledger):
    """Create a test party (customer/supplier)."""
    from apps.party.models import Party
    return Party.objects.create(
        company=company,
        name='ABC Traders',
        party_type='CUSTOMER',
        ledger=ledger,
        gstin='29XYZAB1234C1Z5',
        pan='XYZAB1234C',
        email='party@test.com',
        phone='+919876543211',
        credit_limit=Decimal('100000.00'),
        credit_days=30,
        is_retailer=False,
        is_active=True
    )


# ============================================================================
# INVENTORY FIXTURES
# ============================================================================

@pytest.fixture
def godown(db, company):
    """Create a test godown/warehouse."""
    from apps.inventory.models import Godown
    return Godown.objects.create(
        company=company,
        code='MAIN',
        name='Main Warehouse',
        is_active=True
    )


@pytest.fixture
def stock_item(db, company, uom):
    """Create a test stock item."""
    from apps.inventory.models import StockItem
    return StockItem.objects.create(
        company=company,
        sku='TEST-SKU-001',
        name='Test Stock Item',
        description='Test item for inventory',
        uom=uom,
        is_stock_item=True,
        is_active=True
    )


# ============================================================================
# VOUCHER FIXTURES
# ============================================================================

@pytest.fixture
def voucher_type(db, company):
    """Create a test voucher type."""
    from apps.voucher.models import VoucherType
    return VoucherType.objects.create(
        company=company,
        code='JV',
        name='Journal Voucher',
        category='JOURNAL',
        is_accounting=True,
        is_inventory=False,
        is_active=True
    )


# ============================================================================
# API REQUEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def category_data():
    """Sample category creation data."""
    return {
        'name': 'Test Category',
        'description': 'Test category description',
        'is_active': True,
        'display_order': 1
    }


@pytest.fixture
def product_data(category):
    """Sample product creation data."""
    return {
        'name': 'Test Product',
        'category_id': str(category.id),
        'description': 'Test product description',
        'brand': 'TestBrand',
        'unit': 'PCS',
        'price': '100.00',
        'hsn_code': '0000',
        'cgst_rate': '9.00',
        'sgst_rate': '9.00',
        'igst_rate': '18.00',
        'cess_rate': '0.00',
        'is_portal_visible': True,
        'is_featured': False,
        'status': 'available'
    }
