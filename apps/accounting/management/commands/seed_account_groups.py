"""
Management command to seed default account groups.
"""
from django.core.management.base import BaseCommand
from apps.accounting.models import AccountGroup
from apps.company.models import Company


class Command(BaseCommand):
    help = 'Seed default account groups for all companies'

    def handle(self, *args, **options):
        companies = Company.objects.all()
        
        if not companies.exists():
            self.stdout.write(self.style.ERROR('No companies found. Please create a company first.'))
            return
        
        default_groups = [
            # Assets
            {'code': 'CA', 'name': 'Current Assets', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            {'code': 'BA', 'name': 'Bank Accounts', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            {'code': 'CASH', 'name': 'Cash in Hand', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            {'code': 'SD', 'name': 'Sundry Debtors', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            {'code': 'FA', 'name': 'Fixed Assets', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            {'code': 'INV', 'name': 'Inventory', 'nature': 'ASSET', 'report_type': 'BS', 'parent': None},
            
            # Liabilities
            {'code': 'CL', 'name': 'Current Liabilities', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent': None},
            {'code': 'SC', 'name': 'Sundry Creditors', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent': None},
            {'code': 'LOAN', 'name': 'Loans', 'nature': 'LIABILITY', 'report_type': 'BS', 'parent': None},
            
            # Equity
            {'code': 'CAP', 'name': 'Capital', 'nature': 'EQUITY', 'report_type': 'BS', 'parent': None},
            {'code': 'RES', 'name': 'Reserves', 'nature': 'EQUITY', 'report_type': 'BS', 'parent': None},
            
            # Income
            {'code': 'SALES', 'name': 'Sales', 'nature': 'INCOME', 'report_type': 'PL', 'parent': None},
            {'code': 'OI', 'name': 'Other Income', 'nature': 'INCOME', 'report_type': 'PL', 'parent': None},
            
            # Expenses
            {'code': 'PURCH', 'name': 'Purchases', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
            {'code': 'DE', 'name': 'Direct Expenses', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
            {'code': 'IE', 'name': 'Indirect Expenses', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
            {'code': 'ADMIN', 'name': 'Administrative Expenses', 'nature': 'EXPENSE', 'report_type': 'PL', 'parent': None},
        ]
        
        created_count = 0
        for company in companies:
            self.stdout.write(f'\nSeeding account groups for company: {company.name}')
            
            for group_data in default_groups:
                group, created = AccountGroup.objects.get_or_create(
                    company=company,
                    code=group_data['code'],
                    defaults={
                        'name': group_data['name'],
                        'nature': group_data['nature'],
                        'report_type': group_data['report_type'],
                        'parent': group_data['parent']
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {group.code} - {group.name}'))
                else:
                    self.stdout.write(f'  - Already exists: {group.code} - {group.name}')
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Seeding complete! Created {created_count} new account groups.'))
