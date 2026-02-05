"""
Setup Account Groups for Company
Run: python manage.py shell < scripts/setup_account_groups.py
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

from apps.company.models import Company
from apps.accounting.models import AccountGroup

c = Company.objects.get(code='VENDORGZKJ')
print(f"Setting up Account Groups for: {c.name}")

# Create essential account groups
groups = [
    {'code': 'ASSETS', 'name': 'Assets', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS'},
    {'code': 'LIABILITIES', 'name': 'Liabilities', 'nature': 'CREDIT', 'report_type': 'BS', 'path': 'LIABILITIES'},
    {'code': 'INCOME', 'name': 'Income', 'nature': 'CREDIT', 'report_type': 'PL', 'path': 'INCOME'},
    {'code': 'EXPENSES', 'name': 'Expenses', 'nature': 'DEBIT', 'report_type': 'PL', 'path': 'EXPENSES'},
    {'code': 'EQUITY', 'name': 'Equity', 'nature': 'CREDIT', 'report_type': 'BS', 'path': 'EQUITY'},
]

for g in groups:
    obj, created = AccountGroup.objects.get_or_create(
        company=c,
        code=g['code'],
        defaults={
            'name': g['name'],
            'nature': g['nature'],
            'report_type': g['report_type'],
            'path': g['path']
        }
    )
    status = 'Created' if created else 'Exists'
    print(f"  {status}: {obj.code} - {obj.name}")

# Create sub-groups
assets = AccountGroup.objects.get(company=c, code='ASSETS')
liabilities = AccountGroup.objects.get(company=c, code='LIABILITIES')

sub_groups = [
    {'code': 'SUNDRY_DEBTORS', 'name': 'Sundry Debtors', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS/SUNDRY_DEBTORS', 'parent': assets},
    {'code': 'SUNDRY_CREDITORS', 'name': 'Sundry Creditors', 'nature': 'CREDIT', 'report_type': 'BS', 'path': 'LIABILITIES/SUNDRY_CREDITORS', 'parent': liabilities},
    {'code': 'BANK_ACCOUNTS', 'name': 'Bank Accounts', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS/BANK_ACCOUNTS', 'parent': assets},
    {'code': 'CASH_IN_HAND', 'name': 'Cash in Hand', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS/CASH_IN_HAND', 'parent': assets},
    {'code': 'CURRENT_ASSETS', 'name': 'Current Assets', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS/CURRENT_ASSETS', 'parent': assets},
    {'code': 'FIXED_ASSETS', 'name': 'Fixed Assets', 'nature': 'DEBIT', 'report_type': 'BS', 'path': 'ASSETS/FIXED_ASSETS', 'parent': assets},
    {'code': 'CURRENT_LIABILITIES', 'name': 'Current Liabilities', 'nature': 'CREDIT', 'report_type': 'BS', 'path': 'LIABILITIES/CURRENT_LIABILITIES', 'parent': liabilities},
]

for g in sub_groups:
    obj, created = AccountGroup.objects.get_or_create(
        company=c,
        code=g['code'],
        defaults={
            'name': g['name'],
            'nature': g['nature'],
            'report_type': g['report_type'],
            'path': g['path'],
            'parent': g['parent']
        }
    )
    status = 'Created' if created else 'Exists'
    print(f"  {status}: {obj.code} - {obj.name}")

print("\n✅ Account Groups setup complete!")
print(f"   Total groups: {AccountGroup.objects.filter(company=c).count()}")
