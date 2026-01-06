"""
Script to fix all Sequence creations to use compound keys
Compound key format: {company_id}:{code}:{fy_id}
"""
import re
import sys

def fix_sequence_in_file(filepath):
    """Fix Sequence creation patterns in a file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    changes = []
    
    # Pattern 1: Single Sequence.objects.create with simple key
    # Sequence.objects.create(company=self.company, key="JV", prefix="JV", last_value=0)
    pattern1 = r'Sequence\.objects\.create\(\s*company=self\.company,\s*key="([A-Z_]+)",\s*prefix="([A-Z_]+)",\s*last_value=0\s*\)'
    
    def replace1(match):
        code = match.group(1)
        prefix = match.group(2)
        return f'Sequence.objects.create(\n            company=self.company,\n            key=f"{{self.company.id}}:{code}:{{self.fy.id}}",\n            prefix="{prefix}",\n            last_value=0\n        )'
    
    content, count1 = re.subn(pattern1, replace1, content)
    if count1:
        changes.append(f"Fixed {count1} single Sequence creations")
    
    # Pattern 2: Loop-based Sequence creation
    # for key in ['JV', 'PAY']:
    #     Sequence.objects.create(company=self.company, key=key, ...)
    pattern2 = r"for key in \['([A-Z_, ]+)'\]:\s*\n\s*Sequence\.objects\.create\(\s*company=self\.company,\s*key=key,\s*prefix=key,\s*last_value=0\s*\)"
    
    def replace2(match):
        keys_str = match.group(1)
        keys = [k.strip().strip("'") for k in keys_str.split(',')]
        codes_list = "', '".join(keys)
        result = f"# Create sequences with compound keys (company_id:code:fy_id)\n        "
        result += f"for code in ['{codes_list}']:\n            "
        result += 'compound_key = f"{self.company.id}:{code}:{self.fy.id}"\n            '
        result += 'Sequence.objects.create(\n                company=self.company,\n                '
        result += 'key=compound_key,\n                prefix=code,\n                last_value=0\n            )'
        return result
    
    content, count2 = re.subn(pattern2, replace2, content)
    if count2:
        changes.append(f"Fixed {count2} loop-based Sequence creations")
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ {filepath}")
        for change in changes:
            print(f"  - {change}")
        return True
    else:
        print(f"✗ {filepath} - No changes needed")
        return False

# List of files to process
files = [
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\accounting\tests\test_concurrent_posting.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\company\tests\test_financial_year.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\inventory\tests\test_fifo_stock_movement.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\party\tests\test_party_ledger.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\system\tests\test_idempotency.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\apps\voucher\tests\test_voucher_posting.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\tests\test_integration.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\tests\conftest_helpers.py',
    r'c:\Users\91902\Documents\startup\Vendor\Vendor-backend\tests\unit\services\test_posting_service.py',
]

print("Fixing Sequence creations to use compound keys...")
print("=" * 60)

total_fixed = 0
for filepath in files:
    try:
        if fix_sequence_in_file(filepath):
            total_fixed += 1
    except Exception as e:
        print(f"ERROR in {filepath}: {e}")

print("=" * 60)
print(f"Total files modified: {total_fixed}/{len(files)}")
