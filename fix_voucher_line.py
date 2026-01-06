import re
import os
import glob

def fix_voucher_line(content):
    """
    Convert VoucherLine.objects.create from:
        debit_amount=Decimal('1000.00'),
        credit_amount=Decimal('0.00')
    To:
        amount=Decimal('1000.00'),
        entry_type='DR'
    Or:
        amount=Decimal('1000.00'),
        entry_type='CR'
    """
    
    # Pattern 1: debit_amount with non-zero, credit_amount with zero
    pattern1 = r'(\s+)debit_amount=([^,\n]+),\s*\n\s*credit_amount=Decimal\([\'"]0\.00[\'"]\)'
    replacement1 = r'\1amount=\2,\n\1entry_type=\'DR\''
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: credit_amount with non-zero, debit_amount with zero
    pattern2 = r'(\s+)debit_amount=Decimal\([\'"]0\.00[\'"]\),\s*\n\s*credit_amount=([^,\n]+)'
    replacement2 = r'\1amount=\2,\n\1entry_type=\'CR\''
    content = re.sub(pattern2, replacement2, content)
    
    # Pattern 3: credit_amount comes first (non-zero), debit_amount zero
    pattern3 = r'(\s+)credit_amount=([^,\n]+),\s*\n\s*debit_amount=Decimal\([\'"]0\.00[\'"]\)'
    replacement3 = r'\1amount=\2,\n\1entry_type=\'CR\''
    content = re.sub(pattern3, replacement3, content)
    
    # Pattern 4: debit_amount zero, credit_amount non-zero (different order)
    pattern4 = r'(\s+)debit_amount=Decimal\([\'"]0\.00[\'"]\),\s*\n\s*credit_amount=([^,\n]+)'
    replacement4 = r'\1amount=\2,\n\1entry_type=\'CR\''
    content = re.sub(pattern4, replacement4, content)
    
    return content

# Find all test files
test_files = []
test_files.extend(glob.glob("tests/*.py"))
test_files.extend(glob.glob("tests/**/*.py", recursive=True))
test_files.extend(glob.glob("apps/*/tests/*.py", recursive=True))

fixed_count = 0
for filepath in test_files:
    if not os.path.isfile(filepath):
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        new_content = fix_voucher_line(original_content)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
            print(f"Fixed VoucherLine in: {filepath}")
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

print(f"\nTotal files fixed: {fixed_count}")
print("Done!")
