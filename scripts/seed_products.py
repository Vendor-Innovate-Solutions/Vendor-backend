"""
Seed script for Products with Barcodes
Run: python manage.py shell < scripts/seed_products.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

from django.contrib.auth import get_user_model
from apps.company.models import Company
from apps.products.models import Product, Category
from decimal import Decimal

User = get_user_model()

# Get user and company
user = User.objects.get(email='venkatesh.k21062005@gmail.com')
company = Company.objects.get(name='Vendor')

print(f"Seeding products for Company: {company.name} (ID: {company.id})")
print(f"User: {user.email}")

# Create Categories
categories_data = [
    {'name': 'Cement', 'description': 'Building cement and related products', 'display_order': 1},
    {'name': 'Steel', 'description': 'Steel TMT bars, rods, and structural steel', 'display_order': 2},
    {'name': 'Paint', 'description': 'Interior and exterior paints', 'display_order': 3},
    {'name': 'Electrical', 'description': 'Wires, switches, and electrical fittings', 'display_order': 4},
    {'name': 'Plumbing', 'description': 'Pipes, fittings, and sanitary ware', 'display_order': 5},
    {'name': 'Hardware', 'description': 'Tools, fasteners, and hardware items', 'display_order': 6},
]

categories = {}
for cat_data in categories_data:
    cat, created = Category.objects.get_or_create(
        company=company,
        name=cat_data['name'],
        defaults={
            'description': cat_data['description'],
            'display_order': cat_data['display_order'],
            'is_active': True
        }
    )
    categories[cat_data['name']] = cat
    print(f"{'Created' if created else 'Exists'}: Category - {cat.name}")

# Products with proper HSN codes and tax rates
products_data = [
    # Cement Products
    {
        'name': 'UltraTech PPC Cement 50kg',
        'category': 'Cement',
        'brand': 'UltraTech',
        'unit': 'BAG',
        'price': Decimal('380.00'),
        'hsn_code': '2523',
        'cgst_rate': Decimal('14.00'),
        'sgst_rate': Decimal('14.00'),
        'igst_rate': Decimal('28.00'),
        'available_quantity': 500,
    },
    {
        'name': 'ACC Gold Cement 50kg',
        'category': 'Cement',
        'brand': 'ACC',
        'unit': 'BAG',
        'price': Decimal('375.00'),
        'hsn_code': '2523',
        'cgst_rate': Decimal('14.00'),
        'sgst_rate': Decimal('14.00'),
        'igst_rate': Decimal('28.00'),
        'available_quantity': 350,
    },
    {
        'name': 'Ambuja Plus Cement 50kg',
        'category': 'Cement',
        'brand': 'Ambuja',
        'unit': 'BAG',
        'price': Decimal('370.00'),
        'hsn_code': '2523',
        'cgst_rate': Decimal('14.00'),
        'sgst_rate': Decimal('14.00'),
        'igst_rate': Decimal('28.00'),
        'available_quantity': 420,
    },
    
    # Steel Products
    {
        'name': 'Tata Tiscon 8mm TMT Bar',
        'category': 'Steel',
        'brand': 'Tata Steel',
        'unit': 'KGS',
        'price': Decimal('72.00'),
        'hsn_code': '7214',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 5000,
    },
    {
        'name': 'Tata Tiscon 10mm TMT Bar',
        'category': 'Steel',
        'brand': 'Tata Steel',
        'unit': 'KGS',
        'price': Decimal('70.00'),
        'hsn_code': '7214',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 8000,
    },
    {
        'name': 'JSW NeoSteel 12mm TMT Bar',
        'category': 'Steel',
        'brand': 'JSW Steel',
        'unit': 'KGS',
        'price': Decimal('68.00'),
        'hsn_code': '7214',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 6500,
    },
    
    # Paint Products
    {
        'name': 'Asian Paints Apex 20L White',
        'category': 'Paint',
        'brand': 'Asian Paints',
        'unit': 'LTR',
        'price': Decimal('4500.00'),
        'hsn_code': '3209',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 150,
    },
    {
        'name': 'Asian Paints Tractor Emulsion 10L',
        'category': 'Paint',
        'brand': 'Asian Paints',
        'unit': 'LTR',
        'price': Decimal('1800.00'),
        'hsn_code': '3209',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 200,
    },
    {
        'name': 'Berger WeatherCoat 20L',
        'category': 'Paint',
        'brand': 'Berger',
        'unit': 'LTR',
        'price': Decimal('4200.00'),
        'hsn_code': '3209',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 100,
    },
    
    # Electrical Products
    {
        'name': 'Havells Lifeline 1.5 sq mm Wire 90m',
        'category': 'Electrical',
        'brand': 'Havells',
        'unit': 'ROL',
        'price': Decimal('2100.00'),
        'hsn_code': '8544',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 300,
    },
    {
        'name': 'Polycab 2.5 sq mm Wire 90m',
        'category': 'Electrical',
        'brand': 'Polycab',
        'unit': 'ROL',
        'price': Decimal('3200.00'),
        'hsn_code': '8544',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 250,
    },
    {
        'name': 'Anchor Roma Modular Switch 6A',
        'category': 'Electrical',
        'brand': 'Anchor',
        'unit': 'PCS',
        'price': Decimal('85.00'),
        'hsn_code': '8536',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 1000,
    },
    
    # Plumbing Products
    {
        'name': 'Astral CPVC Pipe 1 inch 3m',
        'category': 'Plumbing',
        'brand': 'Astral',
        'unit': 'PCS',
        'price': Decimal('320.00'),
        'hsn_code': '3917',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 500,
    },
    {
        'name': 'Supreme PVC Pipe 4 inch 6m',
        'category': 'Plumbing',
        'brand': 'Supreme',
        'unit': 'PCS',
        'price': Decimal('850.00'),
        'hsn_code': '3917',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 200,
    },
    {
        'name': 'Jaquar Angle Cock Chrome',
        'category': 'Plumbing',
        'brand': 'Jaquar',
        'unit': 'PCS',
        'price': Decimal('650.00'),
        'hsn_code': '8481',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 150,
    },
    
    # Hardware Products
    {
        'name': 'Stanley Hammer 500g',
        'category': 'Hardware',
        'brand': 'Stanley',
        'unit': 'PCS',
        'price': Decimal('450.00'),
        'hsn_code': '8205',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 100,
    },
    {
        'name': 'Taparia Screwdriver Set 6pcs',
        'category': 'Hardware',
        'brand': 'Taparia',
        'unit': 'SET',
        'price': Decimal('380.00'),
        'hsn_code': '8205',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 80,
    },
    {
        'name': 'GI Nails 2 inch 1kg Pack',
        'category': 'Hardware',
        'brand': 'Generic',
        'unit': 'PAC',
        'price': Decimal('120.00'),
        'hsn_code': '7317',
        'cgst_rate': Decimal('9.00'),
        'sgst_rate': Decimal('9.00'),
        'igst_rate': Decimal('18.00'),
        'available_quantity': 500,
    },
]

# Create products
created_products = []
for prod_data in products_data:
    category = categories[prod_data.pop('category')]
    
    product, created = Product.objects.get_or_create(
        company=company,
        name=prod_data['name'],
        defaults={
            'category': category,
            'brand': prod_data['brand'],
            'unit': prod_data['unit'],
            'price': prod_data['price'],
            'hsn_code': prod_data['hsn_code'],
            'cgst_rate': prod_data['cgst_rate'],
            'sgst_rate': prod_data['sgst_rate'],
            'igst_rate': prod_data['igst_rate'],
            'cess_rate': Decimal('0.00'),
            'available_quantity': prod_data['available_quantity'],
            'is_portal_visible': True,
            'is_featured': False,
            'status': 'available',
            'created_by': user,
            'description': f"High quality {prod_data['brand']} product for construction and building needs."
        }
    )
    created_products.append(product)
    print(f"{'Created' if created else 'Exists'}: Product - {product.name} (ID: {product.id})")

print(f"\n✅ Seeding complete!")
print(f"   Categories: {len(categories)}")
print(f"   Products: {len(created_products)}")

# Print sample barcode URLs
print(f"\n📊 Sample Barcode URLs:")
for product in created_products[:3]:
    print(f"   GET /api/catalog/products/{product.id}/barcode/")
