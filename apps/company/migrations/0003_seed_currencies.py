# Generated migration to seed default currencies

from django.db import migrations


def seed_currencies(apps, schema_editor):
    """Seed default currencies into the database."""
    Currency = apps.get_model('company', 'Currency')
    
    currencies = [
        # Major World Currencies
        {'code': 'INR', 'name': 'Indian Rupee', 'symbol': '₹', 'decimal_places': 2},
        {'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'decimal_places': 2},
        {'code': 'EUR', 'name': 'Euro', 'symbol': '€', 'decimal_places': 2},
        {'code': 'GBP', 'name': 'British Pound', 'symbol': '£', 'decimal_places': 2},
        {'code': 'JPY', 'name': 'Japanese Yen', 'symbol': '¥', 'decimal_places': 0},
        {'code': 'CNY', 'name': 'Chinese Yuan', 'symbol': '¥', 'decimal_places': 2},
        {'code': 'AUD', 'name': 'Australian Dollar', 'symbol': 'A$', 'decimal_places': 2},
        {'code': 'CAD', 'name': 'Canadian Dollar', 'symbol': 'C$', 'decimal_places': 2},
        {'code': 'CHF', 'name': 'Swiss Franc', 'symbol': 'CHF', 'decimal_places': 2},
        {'code': 'SGD', 'name': 'Singapore Dollar', 'symbol': 'S$', 'decimal_places': 2},
        {'code': 'HKD', 'name': 'Hong Kong Dollar', 'symbol': 'HK$', 'decimal_places': 2},
        {'code': 'NZD', 'name': 'New Zealand Dollar', 'symbol': 'NZ$', 'decimal_places': 2},
        # Asian Currencies
        {'code': 'KRW', 'name': 'South Korean Won', 'symbol': '₩', 'decimal_places': 0},
        {'code': 'THB', 'name': 'Thai Baht', 'symbol': '฿', 'decimal_places': 2},
        {'code': 'MYR', 'name': 'Malaysian Ringgit', 'symbol': 'RM', 'decimal_places': 2},
        {'code': 'IDR', 'name': 'Indonesian Rupiah', 'symbol': 'Rp', 'decimal_places': 0},
        {'code': 'PHP', 'name': 'Philippine Peso', 'symbol': '₱', 'decimal_places': 2},
        {'code': 'VND', 'name': 'Vietnamese Dong', 'symbol': '₫', 'decimal_places': 0},
        {'code': 'BDT', 'name': 'Bangladeshi Taka', 'symbol': '৳', 'decimal_places': 2},
        {'code': 'PKR', 'name': 'Pakistani Rupee', 'symbol': '₨', 'decimal_places': 2},
        {'code': 'LKR', 'name': 'Sri Lankan Rupee', 'symbol': 'Rs', 'decimal_places': 2},
        {'code': 'NPR', 'name': 'Nepalese Rupee', 'symbol': 'रू', 'decimal_places': 2},
        # Middle Eastern Currencies
        {'code': 'AED', 'name': 'UAE Dirham', 'symbol': 'د.إ', 'decimal_places': 2},
        {'code': 'SAR', 'name': 'Saudi Riyal', 'symbol': '﷼', 'decimal_places': 2},
        {'code': 'QAR', 'name': 'Qatari Riyal', 'symbol': '﷼', 'decimal_places': 2},
        {'code': 'KWD', 'name': 'Kuwaiti Dinar', 'symbol': 'د.ك', 'decimal_places': 3},
        {'code': 'BHD', 'name': 'Bahraini Dinar', 'symbol': 'BD', 'decimal_places': 3},
        {'code': 'OMR', 'name': 'Omani Rial', 'symbol': '﷼', 'decimal_places': 3},
        # African Currencies
        {'code': 'ZAR', 'name': 'South African Rand', 'symbol': 'R', 'decimal_places': 2},
        {'code': 'EGP', 'name': 'Egyptian Pound', 'symbol': 'E£', 'decimal_places': 2},
        {'code': 'NGN', 'name': 'Nigerian Naira', 'symbol': '₦', 'decimal_places': 2},
        {'code': 'KES', 'name': 'Kenyan Shilling', 'symbol': 'KSh', 'decimal_places': 2},
        # American Currencies
        {'code': 'MXN', 'name': 'Mexican Peso', 'symbol': 'Mex$', 'decimal_places': 2},
        {'code': 'BRL', 'name': 'Brazilian Real', 'symbol': 'R$', 'decimal_places': 2},
        {'code': 'ARS', 'name': 'Argentine Peso', 'symbol': 'AR$', 'decimal_places': 2},
        {'code': 'CLP', 'name': 'Chilean Peso', 'symbol': 'CLP$', 'decimal_places': 0},
        {'code': 'COP', 'name': 'Colombian Peso', 'symbol': 'COL$', 'decimal_places': 0},
        # European Currencies (non-Euro)
        {'code': 'SEK', 'name': 'Swedish Krona', 'symbol': 'kr', 'decimal_places': 2},
        {'code': 'NOK', 'name': 'Norwegian Krone', 'symbol': 'kr', 'decimal_places': 2},
        {'code': 'DKK', 'name': 'Danish Krone', 'symbol': 'kr', 'decimal_places': 2},
        {'code': 'PLN', 'name': 'Polish Zloty', 'symbol': 'zł', 'decimal_places': 2},
        {'code': 'CZK', 'name': 'Czech Koruna', 'symbol': 'Kč', 'decimal_places': 2},
        {'code': 'HUF', 'name': 'Hungarian Forint', 'symbol': 'Ft', 'decimal_places': 0},
        {'code': 'RUB', 'name': 'Russian Ruble', 'symbol': '₽', 'decimal_places': 2},
        {'code': 'TRY', 'name': 'Turkish Lira', 'symbol': '₺', 'decimal_places': 2},
    ]
    
    for currency_data in currencies:
        Currency.objects.get_or_create(
            code=currency_data['code'],
            defaults={
                'name': currency_data['name'],
                'symbol': currency_data['symbol'],
                'decimal_places': currency_data['decimal_places'],
            }
        )


def reverse_currencies(apps, schema_editor):
    """Remove seeded currencies (optional reverse operation)."""
    Currency = apps.get_model('company', 'Currency')
    currency_codes = [
        'INR', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'AUD', 'CAD', 'CHF', 'SGD',
        'HKD', 'NZD', 'KRW', 'THB', 'MYR', 'IDR', 'PHP', 'VND', 'BDT', 'PKR',
        'LKR', 'NPR', 'AED', 'SAR', 'QAR', 'KWD', 'BHD', 'OMR', 'ZAR', 'EGP',
        'NGN', 'KES', 'MXN', 'BRL', 'ARS', 'CLP', 'COP', 'SEK', 'NOK', 'DKK',
        'PLN', 'CZK', 'HUF', 'RUB', 'TRY',
    ]
    Currency.objects.filter(code__in=currency_codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0002_alter_sequence_key'),
    ]

    operations = [
        migrations.RunPython(seed_currencies, reverse_currencies),
    ]
