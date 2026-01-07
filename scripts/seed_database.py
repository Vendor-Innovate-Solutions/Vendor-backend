"""
Database seeding script for initial data setup.
Creates essential groups, roles, and default configurations.
"""
import os
import sys
import django

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.db import transaction


def seed_groups():
    """Create user groups for role-based access control."""
    groups_data = [
        {
            'name': 'admin',
            'permissions': []  # Admins get all permissions via is_superuser
        },
        {
            'name': 'accountant',
            'permissions': []
        },
        {
            'name': 'manager',
            'permissions': []
        },
        {
            'name': 'employee',
            'permissions': []
        },
        {
            'name': 'retailer',
            'permissions': []
        },
    ]
    
    created_count = 0
    for group_data in groups_data:
        group, created = Group.objects.get_or_create(
            name=group_data['name']
        )
        if created:
            created_count += 1
            print(f"  ✅ Created group: {group_data['name']}")
        else:
            print(f"  ℹ️  Group already exists: {group_data['name']}")
    
    return created_count


def seed_default_company():
    """Create a default company with currency and address if none exists."""
    from apps.company.models import Company, Address, Currency
    
    if not Company.objects.exists():
        # Get or create currency first
        currency, _ = Currency.objects.get_or_create(
            code="INR",
            defaults={
                'name': "Indian Rupee",
                'symbol': "₹",
                'decimal_places': 2
            }
        )
        
        # Create company with correct fields
        company = Company.objects.create(
            code="DEMO001",
            name="Demo Company Pvt Ltd",
            legal_name="Demo Company Private Limited",
            company_type="PRIVATE_LIMITED",
            timezone="Asia/Kolkata",
            language="en",
            base_currency=currency,
            is_active=True
        )
        
        # Create registered office address
        Address.objects.create(
            company=company,
            address_type="REGISTERED",
            line1="123 Business Street",
            line2="",
            city="Mumbai",
            state="Maharashtra",
            country="India",
            pincode="400001"
        )
        
        print(f"  ✅ Created default company: {company.name}")
        return company
    else:
        company = Company.objects.first()
        print(f"  ℹ️  Company already exists: {company.name}")
        return company


def seed_currency():
    """Create default currency."""
    from apps.company.models import Currency
    
    currency, created = Currency.objects.get_or_create(
        code="INR",
        defaults={
            'name': "Indian Rupee",
            'symbol': "₹"
        }
    )
    
    if created:
        print(f"  ✅ Created currency: {currency.code}")
    else:
        print(f"  ℹ️  Currency already exists: {currency.code}")
    
    return currency


def seed_financial_year():
    """Create default financial year."""
    from apps.company.models import FinancialYear
    from datetime import date
    
    company = seed_default_company()
    
    fy, created = FinancialYear.objects.get_or_create(
        company=company,
        name="FY 2025-26",
        defaults={
            'start_date': date(2025, 4, 1),
            'end_date': date(2026, 3, 31),
            'is_closed': False
        }
    )
    
    if created:
        print(f"  ✅ Created financial year: {fy.name}")
    else:
        print(f"  ℹ️  Financial year already exists: {fy.name}")
    
    return fy


def seed_account_groups():
    """Create default account groups (Chart of Accounts)."""
    from apps.accounting.models import AccountGroup
    
    company = seed_default_company()
    
    account_groups = [
        # Assets
        {'name': 'Current Assets', 'code': 'CA', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
        {'name': 'Fixed Assets', 'code': 'FA', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
        {'name': 'Cash-in-Hand', 'code': 'CASH', 'nature': 'ASSET', 'report_type': 'BS', 'parent_code': 'CA'},
        {'name': 'Bank Accounts', 'code': 'BANK', 'nature': 'ASSET', 'report_type': 'BS', 'parent_code': 'CA'},
        {'name': 'Sundry Debtors', 'code': 'DEBTORS', 'nature': 'ASSET', 'report_type': 'BS', 'parent_code': 'CA'},
        
        # Liabilities
        {'name': 'Current Liabilities', 'code': 'CL', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent': None},
        {'name': 'Sundry Creditors', 'code': 'CREDITORS', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent_code': 'CL'},
        {'name': 'Capital Account', 'code': 'CAPITAL', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent': None},
        
        # Income
        {'name': 'Sales', 'code': 'SALES', 'nature': 'INCOME', 'report_type': 'PL', 'parent': None},
        {'name': 'Direct Income', 'code': 'DINCOME', 'nature': 'INCOME', 'report_type': 'PL', 'parent': None},
        
        # Expenses
        {'name': 'Purchases', 'code': 'PURCHASE', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
        {'name': 'Direct Expenses', 'code': 'DEXPENSE', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
        {'name': 'Indirect Expenses', 'code': 'IEXPENSE', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
    ]
    
    created_groups = {}
    created_count = 0
    
    # First pass - create parent groups
    for group_data in account_groups:
        if group_data.get('parent') is None and 'parent_code' not in group_data:
            group, created = AccountGroup.objects.get_or_create(
                company=company,
                code=group_data['code'],
                defaults={
                    'name': group_data['name'],
                    'nature': group_data['nature'],
                    'report_type': group_data['report_type'],
                }
            )
            created_groups[group_data['code']] = group
            if created:
                created_count += 1
                print(f"  ✅ Created account group: {group_data['name']}")
    
    # Second pass - create child groups
    for group_data in account_groups:
        if 'parent_code' in group_data:
            parent = created_groups.get(group_data['parent_code'])
            if parent:
                group, created = AccountGroup.objects.get_or_create(
                    company=company,
                    code=group_data['code'],
                    defaults={
                        'name': group_data['name'],
                        'nature': group_data['nature'],
                        'report_type': group_data['report_type'],
                        'parent': parent,
                    }
                )
                if created:
                    created_count += 1
                    print(f"  ✅ Created account group: {group_data['name']}")
    
    return created_count


def seed_product_categories():
    """Create default product categories."""
    from apps.products.models import Category
    
    company = seed_default_company()
    
    categories = [
        {'name': 'Electronics', 'description': 'Electronic items and gadgets', 'display_order': 1},
        {'name': 'Furniture', 'description': 'Office and home furniture', 'display_order': 2},
        {'name': 'Stationery', 'description': 'Office stationery and supplies', 'display_order': 3},
        {'name': 'Hardware', 'description': 'Hardware tools and equipment', 'display_order': 4},
    ]
    
    created_categories = {}
    created_count = 0
    for cat_data in categories:
        category, created = Category.objects.get_or_create(
            company=company,
            name=cat_data['name'],
            defaults={
                'description': cat_data['description'],
                'display_order': cat_data['display_order'],
                'is_active': True
            }
        )
        created_categories[cat_data['name']] = category
        if created:
            created_count += 1
            print(f"  ✅ Created category: {cat_data['name']}")
    
    return created_categories


def seed_products():
    """Create sample products."""
    from apps.products.models import Product
    from decimal import Decimal
    
    company = seed_default_company()
    categories = seed_product_categories()
    
    products_data = [
        {
            'name': 'Laptop HP Pavilion',
            'description': 'HP Pavilion 15.6" Laptop, Intel i5, 8GB RAM, 512GB SSD',
            'category': 'Electronics',
            'brand': 'HP',
            'hsn_code': '84713000',
            'price': Decimal('45000.00'),
            'unit': 'NOS',
            'cgst_rate': Decimal('9.00'),
            'sgst_rate': Decimal('9.00'),
            'igst_rate': Decimal('18.00'),
        },
        {
            'name': 'Office Chair Executive',
            'description': 'Ergonomic office chair with lumbar support',
            'category': 'Furniture',
            'brand': 'Featherlite',
            'hsn_code': '94013000',
            'price': Decimal('8500.00'),
            'unit': 'NOS',
            'cgst_rate': Decimal('9.00'),
            'sgst_rate': Decimal('9.00'),
            'igst_rate': Decimal('18.00'),
        },
        {
            'name': 'A4 Paper Ream',
            'description': 'White A4 copier paper, 500 sheets per ream',
            'category': 'Stationery',
            'brand': 'JK Copier',
            'hsn_code': '48025610',
            'price': Decimal('250.00'),
            'unit': 'PAC',
            'cgst_rate': Decimal('6.00'),
            'sgst_rate': Decimal('6.00'),
            'igst_rate': Decimal('12.00'),
        },
        {
            'name': 'Wireless Mouse Logitech',
            'description': 'Logitech wireless optical mouse',
            'category': 'Electronics',
            'brand': 'Logitech',
            'hsn_code': '84716060',
            'price': Decimal('650.00'),
            'unit': 'NOS',
            'cgst_rate': Decimal('9.00'),
            'sgst_rate': Decimal('9.00'),
            'igst_rate': Decimal('18.00'),
        },
        {
            'name': 'Power Drill Set',
            'description': '13mm chuck power drill with accessories',
            'category': 'Hardware',
            'brand': 'Bosch',
            'hsn_code': '84672210',
            'price': Decimal('3200.00'),
            'unit': 'SET',
            'cgst_rate': Decimal('9.00'),
            'sgst_rate': Decimal('9.00'),
            'igst_rate': Decimal('18.00'),
        },
    ]
    
    created_products = {}
    created_count = 0
    for prod_data in products_data:
        category = categories.get(prod_data['category'])
        if category:
            product, created = Product.objects.get_or_create(
                company=company,
                name=prod_data['name'],
                defaults={
                    'description': prod_data['description'],
                    'category': category,
                    'brand': prod_data['brand'],
                    'hsn_code': prod_data['hsn_code'],
                    'price': prod_data['price'],
                    'unit': prod_data['unit'],
                    'cgst_rate': prod_data['cgst_rate'],
                    'sgst_rate': prod_data['sgst_rate'],
                    'igst_rate': prod_data['igst_rate'],
                    'status': 'ACTIVE',
                    'is_portal_visible': True,
                }
            )
            created_products[prod_data['name']] = product
            if created:
                created_count += 1
                print(f"  ✅ Created product: {prod_data['name']}")
    
    return created_products


def seed_parties():
    """Create sample parties (customers and suppliers)."""
    from apps.party.models import Party
    from apps.accounting.models import AccountGroup, Ledger
    
    company = seed_default_company()
    
    # Get or create account groups for debtors/creditors
    debtors_group = AccountGroup.objects.filter(
        company=company, code='DEBTORS'
    ).first()
    creditors_group = AccountGroup.objects.filter(
        company=company, code='CREDITORS'
    ).first()
    
    parties_data = [
        {
            'name': 'ABC Retailers Pvt Ltd',
            'party_type': 'CUSTOMER',
            'gstin': '29ABCDE1234F1Z5',
            'phone': '+91-9876543210',
            'email': 'rajesh@abcretailers.com',
            'credit_limit': 100000,
            'credit_days': 30,
            'account_group': debtors_group,
        },
        {
            'name': 'XYZ Traders',
            'party_type': 'CUSTOMER',
            'gstin': '27XYZAB5678C2D3',
            'phone': '+91-9988776655',
            'email': 'priya@xyztraders.com',
            'credit_limit': 50000,
            'credit_days': 15,
            'account_group': debtors_group,
        },
        {
            'name': 'Global Suppliers Inc',
            'party_type': 'SUPPLIER',
            'gstin': '29GSUPP1234E1F2',
            'phone': '+91-8877665544',
            'email': 'amit@globalsuppliers.com',
            'credit_limit': 200000,
            'credit_days': 45,
            'account_group': creditors_group,
        },
    ]
    
    created_parties = {}
    created_count = 0
    for party_data in parties_data:
        # Check if party already exists
        existing_party = Party.objects.filter(
            company=company,
            name=party_data['name']
        ).first()
        
        if not existing_party:
            # Create ledger for the party
            ledger = Ledger.objects.create(
                company=company,
                name=party_data['name'],
                account_group=party_data['account_group'],
            )
            
            # Create party
            party = Party.objects.create(
                company=company,
                name=party_data['name'],
                party_type=party_data['party_type'],
                ledger=ledger,
                gstin=party_data['gstin'],
                phone=party_data['phone'],
                email=party_data['email'],
                credit_limit=party_data['credit_limit'],
                credit_days=party_data['credit_days'],
                is_active=True,
            )
            created_parties[party_data['name']] = party
            created_count += 1
            print(f"  ✅ Created party: {party_data['name']}")
        else:
            created_parties[party_data['name']] = existing_party
            print(f"  ℹ️  Party already exists: {party_data['name']}")
    
    return created_parties


def seed_stock_items():
    """Create stock items with opening balances."""
    from apps.inventory.models import StockItem, Warehouse
    from decimal import Decimal
    
    company = seed_default_company()
    products = seed_products()
    
    # Get or create default warehouse
    warehouse, _ = Warehouse.objects.get_or_create(
        company=company,
        code='WH-MAIN',
        defaults={
            'name': 'Main Warehouse',
            'address_line1': '123 Business Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'is_active': True,
        }
    )
    print(f"  ✅ Using warehouse: {warehouse.name}")
    
    stock_data = [
        {'product_name': 'Laptop HP Pavilion', 'quantity': Decimal('50'), 'rate': Decimal('45000.00')},
        {'product_name': 'Office Chair Executive', 'quantity': Decimal('25'), 'rate': Decimal('8500.00')},
        {'product_name': 'A4 Paper Ream', 'quantity': Decimal('500'), 'rate': Decimal('250.00')},
        {'product_name': 'Wireless Mouse Logitech', 'quantity': Decimal('100'), 'rate': Decimal('650.00')},
        {'product_name': 'Power Drill Set', 'quantity': Decimal('30'), 'rate': Decimal('3200.00')},
    ]
    
    created_count = 0
    for stock in stock_data:
        product = products.get(stock['product_name'])
        if product:
            stock_item, created = StockItem.objects.get_or_create(
                company=company,
                product=product,
                warehouse=warehouse,
                defaults={
                    'quantity': stock['quantity'],
                    'rate': stock['rate'],
                }
            )
            if created:
                created_count += 1
                print(f"  ✅ Created stock for: {product.name} (Qty: {stock['quantity']})")
            else:
                # Update quantity if already exists
                stock_item.quantity = stock['quantity']
                stock_item.save()
                print(f"  ✅ Updated stock for: {product.name} (Qty: {stock['quantity']})")
    
    return created_count


def seed_orders():
    """Create sample sales orders."""
    from apps.orders.models import SalesOrder, SalesOrderLine
    from decimal import Decimal
    from datetime import date, timedelta
    
    company = seed_default_company()
    products = seed_products()
    parties = seed_parties()
    fy = seed_financial_year()
    
    orders_data = [
        {
            'party_name': 'ABC Retailers Pvt Ltd',
            'order_date': date.today() - timedelta(days=5),
            'delivery_date': date.today() + timedelta(days=10),
            'status': 'CONFIRMED',
            'lines': [
                {'product_name': 'Laptop HP Pavilion', 'quantity': Decimal('5'), 'rate': Decimal('45000.00')},
                {'product_name': 'Wireless Mouse Logitech', 'quantity': Decimal('10'), 'rate': Decimal('650.00')},
            ]
        },
        {
            'party_name': 'XYZ Traders',
            'order_date': date.today() - timedelta(days=3),
            'delivery_date': date.today() + timedelta(days=7),
            'status': 'PENDING',
            'lines': [
                {'product_name': 'A4 Paper Ream', 'quantity': Decimal('50'), 'rate': Decimal('250.00')},
                {'product_name': 'Office Chair Executive', 'quantity': Decimal('3'), 'rate': Decimal('8500.00')},
            ]
        },
    ]
    
    created_count = 0
    for order_data in orders_data:
        party = parties.get(order_data['party_name'])
        if party and not SalesOrder.objects.filter(
            company=company,
            party=party,
            order_date=order_data['order_date']
        ).exists():
            order = SalesOrder.objects.create(
                company=company,
                financial_year=fy,
                party=party,
                order_date=order_data['order_date'],
                delivery_date=order_data['delivery_date'],
                status=order_data['status'],
                remarks=f"Sample order for {party.name}",
            )
            
            # Create order lines
            for line_data in order_data['lines']:
                product = products.get(line_data['product_name'])
                if product:
                    SalesOrderLine.objects.create(
                        order=order,
                        product=product,
                        quantity=line_data['quantity'],
                        rate=line_data['rate'],
                        amount=line_data['quantity'] * line_data['rate'],
                    )
            
            created_count += 1
            print(f"  ✅ Created order for: {party.name}")
    
    return created_count


@transaction.atomic
def run_seed():
    """Run all seeding operations."""
    print("\n🌱 Starting database seeding...")
    print("\n📋 Seeding Groups...")
    seed_groups()
    
    print("\n🏢 Seeding Company Data...")
    seed_default_company()
    seed_currency()
    seed_financial_year()
    
    print("\n📊 Seeding Account Groups...")
    seed_account_groups()
    
    print("\n📦 Seeding Product Categories...")
    seed_product_categories()
    
    print("\n🛍️ Seeding Products...")
    seed_products()
    
    print("\n👥 Seeding Parties (Customers & Suppliers)...")
    seed_parties()
    
    print("\n📦 Seeding Stock Items...")
    seed_stock_items()
    
    print("\n🛒 Seeding Sales Orders...")
    seed_orders()
    
    print("\n✅ Database seeding completed successfully!\n")


if __name__ == "__main__":
    try:
        run_seed()
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}\n")
        import traceback
        traceback.print_exc()
        exit(1)
