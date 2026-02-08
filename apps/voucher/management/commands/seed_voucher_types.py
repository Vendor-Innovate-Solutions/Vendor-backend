"""
Management command to seed default voucher types.
Usage: python manage.py seed_voucher_types
"""
from django.core.management.base import BaseCommand
from apps.voucher.models import VoucherType, VoucherCategory
from apps.company.models import Company


class Command(BaseCommand):
    help = 'Seeds default voucher types for all companies'

    def handle(self, *args, **options):
        """Create default voucher types for each company"""
        
        # Define default voucher types
        default_voucher_types = [
            {
                'code': 'PAYMENT',
                'name': 'Payment',
                'category': VoucherCategory.PAYMENT,
                'is_accounting': True,
                'is_inventory': False,
            },
            {
                'code': 'RECEIPT',
                'name': 'Receipt',
                'category': VoucherCategory.RECEIPT,
                'is_accounting': True,
                'is_inventory': False,
            },
            {
                'code': 'JOURNAL',
                'name': 'Journal',
                'category': VoucherCategory.JOURNAL,
                'is_accounting': True,
                'is_inventory': False,
            },
            {
                'code': 'CONTRA',
                'name': 'Contra',
                'category': VoucherCategory.CONTRA,
                'is_accounting': True,
                'is_inventory': False,
            },
            {
                'code': 'SALES',
                'name': 'Sales',
                'category': VoucherCategory.SALES,
                'is_accounting': True,
                'is_inventory': True,
            },
            {
                'code': 'PURCHASE',
                'name': 'Purchase',
                'category': VoucherCategory.PURCHASE,
                'is_accounting': True,
                'is_inventory': True,
            },
            {
                'code': 'DEBIT_NOTE',
                'name': 'Debit Note',
                'category': VoucherCategory.DEBIT_NOTE,
                'is_accounting': True,
                'is_inventory': False,
            },
            {
                'code': 'CREDIT_NOTE',
                'name': 'Credit Note',
                'category': VoucherCategory.CREDIT_NOTE,
                'is_accounting': True,
                'is_inventory': False,
            },
        ]
        
        companies = Company.objects.all()
        
        if not companies.exists():
            self.stdout.write(self.style.ERROR('No companies found. Please create a company first.'))
            return
        
        total_created = 0
        total_existing = 0
        
        for company in companies:
            self.stdout.write(f'\nProcessing company: {company.name}')
            
            for vtype_data in default_voucher_types:
                voucher_type, created = VoucherType.objects.get_or_create(
                    company=company,
                    code=vtype_data['code'],
                    defaults={
                        'name': vtype_data['name'],
                        'category': vtype_data['category'],
                        'is_accounting': vtype_data['is_accounting'],
                        'is_inventory': vtype_data['is_inventory'],
                        'is_active': True,
                    }
                )
                
                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Created: {voucher_type.code} - {voucher_type.name}')
                    )
                else:
                    total_existing += 1
                    self.stdout.write(
                        self.style.WARNING(f'  → Already exists: {voucher_type.code} - {voucher_type.name}')
                    )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(self.style.SUCCESS(f'  Companies processed: {companies.count()}'))
        self.stdout.write(self.style.SUCCESS(f'  Voucher types created: {total_created}'))
        self.stdout.write(self.style.WARNING(f'  Already existing: {total_existing}'))
        self.stdout.write(self.style.SUCCESS(f'\n✓ Voucher types seeding completed!\n'))
