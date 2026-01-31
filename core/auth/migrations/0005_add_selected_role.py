# Generated migration for adding selected_role to User

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_auth', '0004_remove_user_email_verified'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='selected_role',
            field=models.CharField(
                blank=True,
                choices=[
                    ('MANUFACTURER', 'Manufacturer'),
                    ('RETAILER', 'Retailer'),
                    ('SUPPLIER', 'Supplier'),
                    ('DISTRIBUTOR', 'Distributor'),
                    ('LOGISTICS', 'Logistics Provider'),
                    ('SERVICE_PROVIDER', 'Service Provider')
                ],
                help_text="User's primary business role selected during onboarding",
                max_length=50,
                null=True
            ),
        ),
    ]
