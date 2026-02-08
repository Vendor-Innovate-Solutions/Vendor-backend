# Generated migration for sales features (credit notes, price lists)

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_salesorder_assigned_employee'),
        ('invoice', '0001_initial'),
        ('party', '0001_initial'),
        ('products', '0001_initial'),
        ('company', '0004_add_company_settings_fields'),
        ('users', '0001_initial'),
    ]

    operations = [
        # Credit Note model
        migrations.CreateModel(
            name='CreditNote',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('credit_note_number', models.CharField(max_length=50, unique=True)),
                ('credit_note_date', models.DateField()),
                ('reason', models.TextField(help_text='Reason for credit note')),
                ('reference_type', models.CharField(choices=[('INVOICE', 'Against Invoice'), ('GENERAL', 'General Credit')], default='INVOICE', max_length=20)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('APPROVED', 'Approved'), ('APPLIED', 'Applied'), ('CANCELLED', 'Cancelled')], default='DRAFT', max_length=20)),
                ('subtotal', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('tax_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('total_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('notes', models.TextField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='credit_notes', to='company.company')),
                ('party', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='credit_notes', to='party.party')),
                ('reference_invoice', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='credit_notes', to='invoice.invoice')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_credit_notes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-credit_note_date', '-created_at'],
                'indexes': [
                    models.Index(fields=['company', 'status'], name='orders_cn_comp_stat'),
                    models.Index(fields=['company', 'credit_note_date'], name='orders_cn_comp_date'),
                    models.Index(fields=['party', 'status'], name='orders_cn_party_stat'),
                ],
            },
        ),
        
        # Credit Note Line model
        migrations.CreateModel(
            name='CreditNoteLine',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('line_no', models.PositiveSmallIntegerField()),
                ('description', models.CharField(max_length=500)),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=12)),
                ('unit_rate', models.DecimalField(decimal_places=2, max_digits=15)),
                ('taxable_value', models.DecimalField(decimal_places=2, max_digits=15)),
                ('cgst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('cgst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('sgst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('sgst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('igst_rate', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('igst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('line_total', models.DecimalField(decimal_places=2, max_digits=15)),
                ('credit_note', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='orders.creditnote')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='products.product')),
            ],
            options={
                'ordering': ['line_no'],
                'unique_together': [('credit_note', 'line_no')],
            },
        ),
        
        # Price List model
        migrations.CreateModel(
            name='PriceList',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('price_list_type', models.CharField(choices=[('STANDARD', 'Standard Price'), ('WHOLESALE', 'Wholesale'), ('RETAIL', 'Retail'), ('SPECIAL', 'Special Offer')], default='STANDARD', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('valid_from', models.DateField(blank=True, null=True)),
                ('valid_to', models.DateField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_lists', to='company.company')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['company', 'is_active'], name='orders_pl_comp_active'),
                    models.Index(fields=['company', 'price_list_type'], name='orders_pl_comp_type'),
                ],
            },
        ),
        
        # Price List Item model
        migrations.CreateModel(
            name='PriceListItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=15)),
                ('min_quantity', models.DecimalField(decimal_places=3, default=1, max_digits=12, help_text='Minimum quantity for this price')),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('is_active', models.BooleanField(default=True)),
                ('price_list', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='orders.pricelist')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_list_items', to='products.product')),
            ],
            options={
                'ordering': ['product', 'min_quantity'],
                'unique_together': [('price_list', 'product', 'min_quantity')],
                'indexes': [
                    models.Index(fields=['price_list', 'is_active'], name='orders_pli_pl_active'),
                    models.Index(fields=['product', 'is_active'], name='orders_pli_prod_active'),
                ],
            },
        ),
    ]
