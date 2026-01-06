"""
Script to remove 'company=' parameter from all VoucherLine.objects.create() calls in test files
"""
import re
from pathlib import Path

# Pattern to find VoucherLine.objects.create with company parameter
pattern = r'VoucherLine\.objects\.create\(\s*company=self\.company,\s*'
replacement = r'VoucherLine.objects.create('

# Find all test files
test_dirs = [
    Path('apps'),
    Path('tests'),
]

files_to_fix = []
for test_dir in test_dirs:
    if test_dir.exists():
        files_to_fix.extend(test_dir.rglob('**/test_*.py'))

print(f"Found {len(files_to_fix)} test files")

# Fix each file
fixed_count = 0
for file_path in files_to_fix:
    try:
        content = file_path.read_text(encoding='utf-8')
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            file_path.write_text(new_content, encoding='utf-8')
            matches = len(re.findall(pattern, content))
            print(f"Fixed {matches} occurrences in {file_path}")
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print(f"\nFixed {fixed_count} files")
