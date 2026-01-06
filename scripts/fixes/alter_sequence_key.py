"""Script to manually alter Sequence.key field length"""
import psycopg2

# Connect to vendor database
conn = psycopg2.connect(
    dbname="vendor",
    user="postgres",
    password="venkat*2005",
    host="localhost",
    port="5432"
)

try:
    cursor = conn.cursor()
    
    # Alter the key field to VARCHAR(100)
    print("Altering company_sequence.key field to VARCHAR(100)...")
    cursor.execute("ALTER TABLE company_sequence ALTER COLUMN key TYPE VARCHAR(100);")
    
    conn.commit()
    print("✓ Successfully altered vendor database")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()

# Connect to test_vendor database
conn_test = psycopg2.connect(
    dbname="test_vendor",
    user="postgres",
    password="venkat*2005",
    host="localhost",
    port="5432"
)

try:
    cursor_test = conn_test.cursor()
    
    # Alter the key field to VARCHAR(100)
    print("Altering company_sequence.key field in test database to VARCHAR(100)...")
    cursor_test.execute("ALTER TABLE company_sequence ALTER COLUMN key TYPE VARCHAR(100);")
    
    conn_test.commit()
    print("✓ Successfully altered test_vendor database")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn_test.rollback()
finally:
    cursor_test.close()
    conn_test.close()

print("\nDone! Both databases updated.")
