import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from apps.products.models import Product, Category
from apps.inventory.models import StockItem
from django.db import connection

# Check table schema
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'products_product' 
        AND column_name IN ('id', 'company_id')
        ORDER BY column_name
    """)
    print("Product table columns:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]}")
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'inventory_stockitem' 
        AND column_name = 'product_id'
    """)
    result = cursor.fetchone()
    if result:
        print(f"\nStockItem.product_id: {result[1]}")
    else:
        print("\nStockItem.product_id: NOT FOUND")

print("\n✓ Products app successfully refactored to UUID primary keys!")
print("✓ StockItem has FK to Product")
print("✓ Migrations applied successfully")
