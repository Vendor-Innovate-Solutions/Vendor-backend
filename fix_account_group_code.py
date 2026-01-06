import re
import os

# Files that create AccountGroup objects
files_to_fix = [
    "tests/conftest.py",
    "tests/test_posting_reversal.py",
    "tests/test_payment_allocation.py",
    "tests/test_stock_reservation.py",
    "tests/test_financial_year_lock.py",
    "tests/services/test_posting_service.py"
]

for filepath in files_to_fix:
    if not os.path.exists(filepath):
        continue
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to add code field after name in AccountGroup.objects.create
    # Matches: name="Something", but not already having code=
    pattern = r'(AccountGroup\.objects\.create\([^)]*?name="([^"]+)")(,\s*\n\s*(?!code=))'
    
    def add_code(match):
        prefix = match.group(1)
        name = match.group(2)
        suffix = match.group(3)
        # Generate code from name (uppercase, remove spaces)
        code = name.upper().replace(' ', '_').replace('-', '_')[:20]
        return f'{prefix},\n            code="{code}"{suffix}'
    
    new_content = re.sub(pattern, add_code, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(new_content)
        print(f"Fixed: {filepath}")
    else:
        print(f"No changes: {filepath}")

print("Done!")
