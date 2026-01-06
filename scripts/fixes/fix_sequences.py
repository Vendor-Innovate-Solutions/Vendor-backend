"""
Script to add Sequence creation to test setUp methods that call post_voucher
"""
import re
from pathlib import Path

def needs_sequence_setup(content):
    """Check if file calls post_voucher but doesn't create Sequence"""
    has_post_voucher = 'post_voucher(' in content or 'PostingService()' in content
    has_sequence_create = 'Sequence.objects.create' in content
    return has_post_voucher and not has_sequence_create

def add_sequence_to_setup(content):
    """Add Sequence creation to setUp method"""
    lines = content.split('\n')
    new_lines = []
    in_setup = False
    added_sequence = False
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # Detect setUp method
        if 'def setUp(self):' in line:
            in_setup = True
            continue
        
        # Look for voucher_type creation (good place to add sequence)
        if in_setup and not added_sequence and 'VoucherType.objects.create(' in line:
            # Find the end of this VoucherType.objects.create block
            j = i
            while j < len(lines) and ')' not in lines[j]:
                new_lines.append(lines[j + 1])
                j += 1
            
            # Add empty line and sequence creation after voucher type
            indent = ' ' * 8
            new_lines.append('')
            new_lines.append(f'{indent}# Create sequences for auto-numbering')
            new_lines.append(f'{indent}for vt in VoucherType.objects.filter(company=self.company):')
            new_lines.append(f'{indent}    Sequence.objects.get_or_create(')
            new_lines.append(f'{indent}        company=self.company,')
            new_lines.append(f'{indent}        key=vt.code,')
            new_lines.append(f'{indent}        defaults={{\'prefix\': vt.code, \'last_value\': 0}}')
            new_lines.append(f'{indent}    )')
            
            added_sequence = True
            
            # Skip the lines we already added
            i = j
    
    return '\n'.join(new_lines) if added_sequence else content

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
        
        if needs_sequence_setup(content):
            new_content = add_sequence_to_setup(content)
            
            if new_content != content:
                file_path.write_text(new_content, encoding='utf-8')
                print(f"Added Sequence setup to {file_path}")
                fixed_count += 1
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print(f"\nFixed {fixed_count} files")
