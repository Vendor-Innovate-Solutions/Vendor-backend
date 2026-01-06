"""
Add ledger field to Party.objects.create() in test files.
This is a complex fix that requires creating AccountGroup, Ledger, and FinancialYear.
"""

files_to_fix = {
    "tests/test_company_scope.py": [
        (67, "Retailer Party", "CUSTOMER"),
        (257, "Party A", "CUSTOMER"),
        (262, "Party B", "CUSTOMER")
    ],
    "tests/test_credit_guards.py": [
        (79, None, "CUSTOMER"),  # Name from context
        (90, None, "CUSTOMER")   # Name from context
    ],
    "tests/test_invoice_outstanding.py": [
        (77, None, "CUSTOMER"),  # Name from context
        (428, None, "CUSTOMER")  # Name from context
    ],
    "tests/api/test_orders_api.py": [
        (479, "Other Party", "CUSTOMER")
    ],
    "tests/test_accounting_apis.py": [
        (75, None, "CUSTOMER")  # Name from context
    ]
}

print("Files that need Party ledger fixes:")
for file, occurrences in files_to_fix.items():
    print(f"  {file}: {len(occurrences)} occurrences")

print("\nThese files need manual intervention:")
print("  - Add AccountGroup import")
print("  - Add Ledger import")
print("  - Create ledger before Party")
print("  - Pass ledger=ledger_obj to Party.objects.create()")
