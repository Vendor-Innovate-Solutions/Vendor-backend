"""
Management command to seed default sequences for voucher numbering.
Usage: python manage.py seed_sequences
"""
from django.core.management.base import BaseCommand
from apps.company.models import Company, Sequence, ResetPeriod


class Command(BaseCommand):
    help = 'Seeds default sequences for voucher numbering'

    def handle(self, *args, **options):
        """Create default sequences for each company"""
        
        # Define default sequence keys
        default_sequences = [
            # Voucher sequences
            {'key': 'VOUCHER_PAYMENT', 'prefix': 'PAY', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_RECEIPT', 'prefix': 'REC', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_JOURNAL', 'prefix': 'JV', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_CONTRA', 'prefix': 'CON', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_SALES', 'prefix': 'SAL', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_PURCHASE', 'prefix': 'PUR', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_DEBIT_NOTE', 'prefix': 'DN', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'VOUCHER_CREDIT_NOTE', 'prefix': 'CN', 'reset_period': ResetPeriod.YEARLY},
            
            # Invoice sequences
            {'key': 'INVOICE', 'prefix': 'INV', 'reset_period': ResetPeriod.YEARLY},
            
            # Order sequences
            {'key': 'SALES_ORDER', 'prefix': 'SO', 'reset_period': ResetPeriod.YEARLY},
            {'key': 'PURCHASE_ORDER', 'prefix': 'PO', 'reset_period': ResetPeriod.YEARLY},
        ]
        
        companies = Company.objects.all()
        
        if not companies.exists():
            self.stdout.write(self.style.ERROR('No companies found. Please create a company first.'))
            return
        
        total_created = 0
        total_existing = 0
        
        for company in companies:
            self.stdout.write(f'\nProcessing company: {company.name}')
            
            for seq_data in default_sequences:
                sequence, created = Sequence.objects.get_or_create(
                    company=company,
                    key=seq_data['key'],
                    defaults={
                        'prefix': seq_data['prefix'],
                        'last_value': 0,
                        'reset_period': seq_data['reset_period'],
                    }
                )
                
                if created:
                    total_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'  ✓ Created: {sequence.key} (prefix: {sequence.prefix})')
                    )
                else:
                    total_existing += 1
                    self.stdout.write(
                        self.style.WARNING(f'  → Already exists: {sequence.key} (prefix: {sequence.prefix})')
                    )
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(self.style.SUCCESS(f'  Companies processed: {companies.count()}'))
        self.stdout.write(self.style.SUCCESS(f'  Sequences created: {total_created}'))
        self.stdout.write(self.style.WARNING(f'  Already existing: {total_existing}'))
        self.stdout.write(self.style.SUCCESS(f'\n✓ Sequences seeding completed!\n'))
