# Generated migration for company settings fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0003_seed_currencies'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='gstin',
            field=models.CharField(blank=True, max_length=15, null=True, verbose_name='GSTIN'),
        ),
        migrations.AddField(
            model_name='company',
            name='pan',
            field=models.CharField(blank=True, max_length=10, null=True, verbose_name='PAN'),
        ),
        migrations.AddField(
            model_name='company',
            name='phone',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='website',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='logo',
            field=models.ImageField(blank=True, null=True, upload_to='company_logos/'),
        ),
        migrations.AddField(
            model_name='company',
            name='invoice_footer',
            field=models.TextField(blank=True, null=True, help_text='Footer text to display on invoices'),
        ),
        migrations.AddField(
            model_name='company',
            name='invoice_terms',
            field=models.TextField(blank=True, null=True, help_text='Terms and conditions for invoices'),
        ),
        migrations.AddField(
            model_name='company',
            name='address_line1',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='address_line2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='city',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='state',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='country',
            field=models.CharField(blank=True, default='India', max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='company',
            name='pincode',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
