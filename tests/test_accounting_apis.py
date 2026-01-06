"""
Test suite for Ledger & Account APIs.

Tests comprehensive scenarios for financial reporting APIs including:
- Ledger CRUD operations with company scoping
- Balance queries and calculations
- Financial reports (Trial Balance, P&L, Balance Sheet)
- Role-based permission enforcement
- Financial year filtering
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.company.models import Company, CompanyUser, FinancialYear, Currency
from apps.portal.models import RetailerCompanyAccess  
from apps.party.models import Party
from apps.accounting.models import AccountGroup, Ledger, LedgerBalance

User = get_user_model()


@pytest.fixture
def currency(db):
    """Create a test currency."""
    return Currency.objects.create(
        code="USD",
        name="US Dollar",
        symbol="$",
        decimal_places=2
    )


@pytest.fixture
def company(db, currency):
    """Create a test company."""
    return Company.objects.create(
        name="Test Company",
        legal_name="Test Company Ltd",
        code="TST001",
        base_currency=currency,
        is_active=True
    )


@pytest.fixture
def other_company(db, currency):
    """Create another company for isolation testing."""
    return Company.objects.create(
        name="Other Company",
        legal_name="Other Company Ltd",
        code="OTH001",
        base_currency=currency,
        is_active=True
    )


@pytest.fixture
def financial_year(db, company):
    """Create a financial year."""
    return FinancialYear.objects.create(
        company=company,
        year_code="FY2024",
        start_date="2024-04-01",
        end_date="2025-03-31",
        is_active=True
    )


@pytest.fixture
def retailer(db, company, financial_year):
    """Create a retailer party."""
    from apps.accounting.models import Ledger, AccountGroup
    from decimal import Decimal
    
    # Create account group
    debtors_group, _ = AccountGroup.objects.get_or_create(
        company=company,
        code='SUNDRY_DEBTORS',
        defaults={
            'name': 'Sundry Debtors',
            'nature': 'ASSET',
            'report_type': 'BS',
            'path': '/SUNDRY_DEBTORS'
        }
    )
    
    # Create ledger
    retailer_ledger = Ledger.objects.create(
        company=company,
        code='LED_RETAILER',
        name='Test Retailer',
        group=debtors_group,
        account_type='DEBTOR',
        opening_balance=Decimal('0.00'),
        opening_balance_fy=financial_year,
        opening_balance_type='DR',
        is_active=True
    )
    
    return Party.objects.create(
        company=company,
        name="Test Retailer",
        party_type="RETAILER",
        ledger=retailer_ledger,
        is_active=True
    )


@pytest.fixture
def admin_user(db, company, retailer):
    """Create an admin user with ADMIN role."""
    user = User.objects.create_user(
        username="admin@test.com",
        email="admin@test.com",
        password="testpass123",
        is_active=True
    )
    
    # Create CompanyUser with ADMIN role
    company_user = CompanyUser.objects.create(
        user=user,
        company=company,
        role="ADMIN"
    )
    
    # Create retailer access
    RetailerCompanyAccess.objects.create(
        retailer=retailer,
        company=company,
        user=user,
        status="APPROVED"
    )
    
    # Set active company
    user.active_company = company
    user.save()
    
    return user


@pytest.fixture
def accountant_user(db, company, retailer):
    """Create an accountant user with ACCOUNTANT role."""
    user = User.objects.create_user(
        username="accountant@test.com",
        email="accountant@test.com",
        password="testpass123",
        is_active=True
    )
    
    company_user = CompanyUser.objects.create(
        user=user,
        company=company,
        role="ACCOUNTANT"
    )
    
    RetailerCompanyAccess.objects.create(
        retailer=retailer,
        company=company,
        user=user,
        status="APPROVED"
    )
    
    user.active_company = company
    user.save()
    
    return user


@pytest.fixture
def sales_user(db, company, retailer):
    """Create a sales user without accounting permissions."""
    user = User.objects.create_user(
        username="sales@test.com",
        email="sales@test.com",
        password="testpass123",
        is_active=True
    )
    
    company_user = CompanyUser.objects.create(
        user=user,
        company=company,
        role="SALES"
    )
    
    RetailerCompanyAccess.objects.create(
        retailer=retailer,
        company=company,
        user=user,
        status="APPROVED"
    )
    
    user.active_company = company
    user.save()
    
    return user


@pytest.fixture
def authenticated_client(admin_user):
    """Create an authenticated API client with admin user."""
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def accountant_client(accountant_user):
    """Create an authenticated API client with accountant user."""
    client = APIClient()
    refresh = RefreshToken.for_user(accountant_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def sales_client(sales_user):
    """Create an authenticated API client with sales user."""
    client = APIClient()
    refresh = RefreshToken.for_user(sales_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def account_groups(db, company):
    """Create standard account groups."""
    groups = {}
    
    # Assets
    groups['assets'] = AccountGroup.objects.create(
        company=company,
        name="Assets",
        code="AS",
        nature="ASSET",
        report_type="BS",
        path="AS",
        is_active=True
    )
    
    # Liabilities
    groups['liabilities'] = AccountGroup.objects.create(
        company=company,
        name="Liabilities",
        code="LI",
        nature="LIABILITY",
        report_type="BS",
        path="LI",
        is_active=True
    )
    
    # Income
    groups['income'] = AccountGroup.objects.create(
        company=company,
        name="Income",
        code="IN",
        nature="INCOME",
        report_type="PL",
        path="IN",
        is_active=True
    )
    
    # Expense
    groups['expense'] = AccountGroup.objects.create(
        company=company,
        name="Expense",
        code="EX",
        nature="EXPENSE",
        report_type="PL",
        path="EX",
        is_active=True
    )
    
    return groups


@pytest.fixture
def ledgers(db, company, account_groups):
    """Create test ledgers."""
    ledgers = {}
    
    # Cash (Asset)
    ledgers['cash'] = Ledger.objects.create(
        company=company,
        group=account_groups['assets'],
        name="Cash",
        code="CASH",
        is_active=True
    )
    
    # Bank (Asset)
    ledgers['bank'] = Ledger.objects.create(
        company=company,
        group=account_groups['assets'],
        name="Bank Account",
        code="BANK",
        is_active=True
    )
    
    # Capital (Liability)
    ledgers['capital'] = Ledger.objects.create(
        company=company,
        group=account_groups['liabilities'],
        name="Capital",
        code="CAP",
        is_active=True
    )
    
    # Sales (Income)
    ledgers['sales'] = Ledger.objects.create(
        company=company,
        group=account_groups['income'],
        name="Sales",
        code="SALES",
        is_active=True
    )
    
    # Rent (Expense)
    ledgers['rent'] = Ledger.objects.create(
        company=company,
        group=account_groups['expense'],
        name="Rent Expense",
        code="RENT",
        is_active=True
    )
    
    return ledgers


@pytest.fixture
def ledger_balances(db, company, financial_year, ledgers):
    """Create ledger balances for testing reports."""
    balances = []
    
    # Cash: 50,000 DR
    balances.append(LedgerBalance.objects.create(
        company=company,
        financial_year=financial_year,
        ledger=ledgers['cash'],
        balance=Decimal('50000.00')
    ))
    
    # Bank: 100,000 DR
    balances.append(LedgerBalance.objects.create(
        company=company,
        financial_year=financial_year,
        ledger=ledgers['bank'],
        balance=Decimal('100000.00')
    ))
    
    # Capital: -150,000 CR
    balances.append(LedgerBalance.objects.create(
        company=company,
        financial_year=financial_year,
        ledger=ledgers['capital'],
        balance=Decimal('-150000.00')
    ))
    
    # Sales: -100,000 CR
    balances.append(LedgerBalance.objects.create(
        company=company,
        financial_year=financial_year,
        ledger=ledgers['sales'],
        balance=Decimal('-100000.00')
    ))
    
    # Rent: 100,000 DR
    balances.append(LedgerBalance.objects.create(
        company=company,
        financial_year=financial_year,
        ledger=ledgers['rent'],
        balance=Decimal('100000.00')
    ))
    
    return balances


# ============================================================================
# LEDGER CRUD TESTS
# ============================================================================

@pytest.mark.django_db
class TestLedgerCRUD:
    """Test Ledger CRUD operations."""
    
    def test_list_ledgers(self, authenticated_client, company, ledgers):
        """Test listing ledgers filters by company."""
        response = authenticated_client.get('/api/accounting/ledgers/')
        
        assert response.status_code == 200
        assert len(response.data['results']) == 5
        
        # Verify all ledgers belong to the user's company
        for ledger in response.data['results']:
            assert ledger['company'] == company.id
    
    def test_create_ledger(self, authenticated_client, company, account_groups):
        """Test creating a new ledger."""
        data = {
            'name': 'New Ledger',
            'code': 'NEWLED',
            'group': account_groups['assets'].id,
            'is_active': True
        }
        
        response = authenticated_client.post('/api/accounting/ledgers/', data)
        
        assert response.status_code == 201
        assert response.data['name'] == 'New Ledger'
        assert response.data['code'] == 'NEWLED'
        assert response.data['company'] == company.id
    
    def test_update_ledger(self, authenticated_client, ledgers):
        """Test updating a ledger."""
        data = {
            'name': 'Updated Cash',
            'is_active': False
        }
        
        response = authenticated_client.patch(
            f'/api/accounting/ledgers/{ledgers["cash"].id}/',
            data
        )
        
        assert response.status_code == 200
        assert response.data['name'] == 'Updated Cash'
        assert response.data['is_active'] is False
    
    def test_delete_ledger(self, authenticated_client, company, account_groups):
        """Test deleting a ledger."""
        # Create a new ledger to delete
        ledger = Ledger.objects.create(
            company=company,
            group=account_groups['expense'],
            name='Temp Ledger',
            code='TEMP'
        )
        
        response = authenticated_client.delete(f'/api/accounting/ledgers/{ledger.id}/')
        
        assert response.status_code == 204
        assert not Ledger.objects.filter(id=ledger.id).exists()
    
    def test_company_isolation(self, authenticated_client, other_company, account_groups):
        """Test that users cannot access ledgers from other companies."""
        # Create ledger in other company
        other_group = AccountGroup.objects.create(
            company=other_company,
            name="Other Assets",
            code="OAS",
            nature="ASSET",
            report_type="BS",
            path="OAS"
        )
        
        other_ledger = Ledger.objects.create(
            company=other_company,
            group=other_group,
            name="Other Cash",
            code="OCASH"
        )
        
        # Try to access
        response = authenticated_client.get(f'/api/accounting/ledgers/{other_ledger.id}/')
        
        assert response.status_code == 404


# ============================================================================
# LEDGER BALANCE TESTS
# ============================================================================

@pytest.mark.django_db
class TestLedgerBalance:
    """Test ledger balance queries."""
    
    def test_get_ledger_balance(
        self, authenticated_client, ledgers, ledger_balances, financial_year
    ):
        """Test retrieving balance for a specific ledger."""
        response = authenticated_client.get(
            f'/api/accounting/ledgers/{ledgers["cash"].id}/balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        assert Decimal(response.data['balance_dr']) == Decimal('50000.00')
        assert Decimal(response.data['balance_cr']) == Decimal('0.00')
        assert Decimal(response.data['net']) == Decimal('50000.00')
    
    def test_get_ledger_balance_credit(
        self, authenticated_client, ledgers, ledger_balances, financial_year
    ):
        """Test retrieving balance for a credit ledger."""
        response = authenticated_client.get(
            f'/api/accounting/ledgers/{ledgers["sales"].id}/balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        assert Decimal(response.data['balance_dr']) == Decimal('0.00')
        assert Decimal(response.data['balance_cr']) == Decimal('100000.00')
        assert Decimal(response.data['net']) == Decimal('-100000.00')
    
    def test_get_ledger_balance_no_year(self, authenticated_client, ledgers):
        """Test balance query requires financial year."""
        response = authenticated_client.get(
            f'/api/accounting/ledgers/{ledgers["cash"].id}/balance/'
        )
        
        assert response.status_code == 400
        assert 'financial_year_id' in str(response.data)


# ============================================================================
# TRIAL BALANCE TESTS
# ============================================================================

@pytest.mark.django_db
class TestTrialBalance:
    """Test Trial Balance report generation."""
    
    def test_trial_balance_calculation(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test trial balance shows correct DR/CR totals."""
        response = authenticated_client.get(
            '/api/accounting/reports/trial-balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        data = response.data
        
        # Verify totals
        # DR: Cash (50k) + Bank (100k) + Rent (100k) = 250k
        # CR: Capital (150k) + Sales (100k) = 250k
        assert Decimal(data['total_debit']) == Decimal('250000.00')
        assert Decimal(data['total_credit']) == Decimal('250000.00')
        assert Decimal(data['difference']) == Decimal('0.00')
        assert data['is_balanced'] is True
    
    def test_trial_balance_ledger_details(
        self, authenticated_client, financial_year, ledgers, ledger_balances
    ):
        """Test trial balance includes all ledgers with balances."""
        response = authenticated_client.get(
            '/api/accounting/reports/trial-balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        ledgers_data = response.data['ledgers']
        
        assert len(ledgers_data) == 5
        
        # Find cash ledger
        cash = next(l for l in ledgers_data if l['name'] == 'Cash')
        assert Decimal(cash['balance_dr']) == Decimal('50000.00')
        assert Decimal(cash['balance_cr']) == Decimal('0.00')
        
        # Find capital ledger
        capital = next(l for l in ledgers_data if l['name'] == 'Capital')
        assert Decimal(capital['balance_dr']) == Decimal('0.00')
        assert Decimal(capital['balance_cr']) == Decimal('150000.00')
    
    def test_trial_balance_permission_denied(self, sales_client, financial_year):
        """Test that non-accounting users cannot access trial balance."""
        response = sales_client.get(
            '/api/accounting/reports/trial-balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 403
    
    def test_trial_balance_accountant_access(
        self, accountant_client, financial_year, ledger_balances
    ):
        """Test that accountants can access trial balance."""
        response = accountant_client.get(
            '/api/accounting/reports/trial-balance/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        assert 'total_debit' in response.data


# ============================================================================
# PROFIT & LOSS TESTS
# ============================================================================

@pytest.mark.django_db
class TestProfitLoss:
    """Test Profit & Loss report generation."""
    
    def test_pl_calculation(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test P&L shows correct profit/loss."""
        response = authenticated_client.get(
            '/api/accounting/reports/pl/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        data = response.data
        
        # Income: Sales (100k)
        assert Decimal(data['total_income']) == Decimal('100000.00')
        
        # Expense: Rent (100k)
        assert Decimal(data['total_expense']) == Decimal('100000.00')
        
        # Net: Income - Expense = 0
        assert Decimal(data['net_profit']) == Decimal('0.00')
    
    def test_pl_income_breakdown(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test P&L shows income ledger breakdown."""
        response = authenticated_client.get(
            '/api/accounting/reports/pl/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        income_ledgers = response.data['income_ledgers']
        
        assert len(income_ledgers) == 1
        assert income_ledgers[0]['name'] == 'Sales'
        assert Decimal(income_ledgers[0]['amount']) == Decimal('100000.00')
    
    def test_pl_expense_breakdown(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test P&L shows expense ledger breakdown."""
        response = authenticated_client.get(
            '/api/accounting/reports/pl/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        expense_ledgers = response.data['expense_ledgers']
        
        assert len(expense_ledgers) == 1
        assert expense_ledgers[0]['name'] == 'Rent Expense'
        assert Decimal(expense_ledgers[0]['amount']) == Decimal('100000.00')


# ============================================================================
# BALANCE SHEET TESTS
# ============================================================================

@pytest.mark.django_db
class TestBalanceSheet:
    """Test Balance Sheet report generation."""
    
    def test_balance_sheet_equation(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test balance sheet satisfies Assets = Liabilities + Equity."""
        response = authenticated_client.get(
            '/api/accounting/reports/bs/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        data = response.data
        
        # Assets: Cash (50k) + Bank (100k) = 150k
        assert Decimal(data['total_assets']) == Decimal('150000.00')
        
        # Liabilities: Capital (150k)
        assert Decimal(data['total_liabilities']) == Decimal('150000.00')
        
        # Equity: 0 (no profit for this period since income = expense)
        assert Decimal(data['total_equity']) == Decimal('0.00')
        
        # Difference should be 0 (balanced)
        assert Decimal(data['difference']) == Decimal('0.00')
        assert data['balance_check'] is True
    
    def test_balance_sheet_asset_breakdown(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test balance sheet shows asset ledger breakdown."""
        response = authenticated_client.get(
            '/api/accounting/reports/bs/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        asset_ledgers = response.data['asset_ledgers']
        
        assert len(asset_ledgers) == 2
        
        # Verify assets
        cash = next(l for l in asset_ledgers if l['name'] == 'Cash')
        assert Decimal(cash['amount']) == Decimal('50000.00')
        
        bank = next(l for l in asset_ledgers if l['name'] == 'Bank Account')
        assert Decimal(bank['amount']) == Decimal('100000.00')
    
    def test_balance_sheet_liability_breakdown(
        self, authenticated_client, financial_year, ledger_balances
    ):
        """Test balance sheet shows liability ledger breakdown."""
        response = authenticated_client.get(
            '/api/accounting/reports/bs/',
            {'financial_year_id': financial_year.id}
        )
        
        assert response.status_code == 200
        liability_ledgers = response.data['liability_ledgers']
        
        assert len(liability_ledgers) == 1
        assert liability_ledgers[0]['name'] == 'Capital'
        assert Decimal(liability_ledgers[0]['amount']) == Decimal('150000.00')


# ============================================================================
# FINANCIAL YEAR TESTS
# ============================================================================

@pytest.mark.django_db
class TestFinancialYear:
    """Test Financial Year management."""
    
    def test_list_financial_years(
        self, authenticated_client, company, financial_year
    ):
        """Test listing financial years filtered by company."""
        response = authenticated_client.get('/api/accounting/financial-years/')
        
        assert response.status_code == 200
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['year_code'] == 'FY2024'
    
    def test_create_financial_year(self, authenticated_client, company):
        """Test creating a new financial year."""
        data = {
            'year_code': 'FY2025',
            'start_date': '2025-04-01',
            'end_date': '2026-03-31',
            'is_active': True
        }
        
        response = authenticated_client.post('/api/accounting/financial-years/', data)
        
        assert response.status_code == 201
        assert response.data['year_code'] == 'FY2025'
        assert response.data['company'] == company.id


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_trial_balance_missing_year(self, authenticated_client):
        """Test trial balance requires financial year."""
        response = authenticated_client.get('/api/accounting/reports/trial-balance/')
        
        assert response.status_code == 400
    
    def test_trial_balance_invalid_year(self, authenticated_client):
        """Test trial balance with invalid financial year ID."""
        response = authenticated_client.get(
            '/api/accounting/reports/trial-balance/',
            {'financial_year_id': 99999}
        )
        
        assert response.status_code == 404
    
    def test_unauthenticated_access(self):
        """Test that unauthenticated users cannot access APIs."""
        client = APIClient()
        response = client.get('/api/accounting/ledgers/')
        
        assert response.status_code == 401
    
    def test_ledger_duplicate_code(
        self, authenticated_client, company, account_groups, ledgers
    ):
        """Test that duplicate ledger codes are prevented."""
        data = {
            'name': 'Another Cash',
            'code': 'CASH',  # Duplicate code
            'group': account_groups['assets'].id,
            'is_active': True
        }
        
        response = authenticated_client.post('/api/accounting/ledgers/', data)
        
        # Should fail with unique constraint error
        assert response.status_code == 400
