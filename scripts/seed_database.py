"""
Database seeding script for initial data setup.
Creates essential groups, roles, and default configurations.
"""
import os
import django

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
    """Create a default company if none exists."""
    from apps.company.models import Company
    
    if not Company.objects.exists():
        company = Company.objects.create(
            name="Demo Company Pvt Ltd",
            company_code="DEMO001",
            gstin="29ABCDE1234F1Z5",
            pan="ABCDE1234F",
            address="123 Business Street",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            phone="+91-22-12345678",
            email="info@democompany.com",
            is_active=True
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
        if created:
            created_count += 1
            print(f"  ✅ Created category: {cat_data['name']}")
    
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
    
    print("\n✅ Database seeding completed successfully!\n")


if __name__ == "__main__":
    try:
        run_seed()
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}\n")
        import traceback
        traceback.print_exc()
        exit(1)
