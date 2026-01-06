import re
import sys

files = [
    "tests/test_posting_reversal.py",
    "tests/test_payment_allocation.py",
    "tests/test_financial_year_lock.py"
]

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match Voucher.objects.create with company and voucher_type but without financial_year
    pattern = r'(Voucher\.objects\.create\(\s*\n\s*company=[^,]+,\s*\n\s*voucher_type=[^,]+,)(\s*\n\s*(?!financial_year))'
    
    replacement = r'\1\n            financial_year=self.fy,\2'
    
    new_content = re.sub(pattern, replacement, content)
    
    # Remove the backtick-n artifacts
    new_content = new_content.replace('`n', '\n')
    
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        f.write(new_content)
    
    print(f"Fixed: {filepath}")

print("Done!")
