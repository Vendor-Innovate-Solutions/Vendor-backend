"""
Script to add line_no parameter to all VoucherLine.objects.create() calls in test files
"""
import re
from pathlib import Path

def fix_voucher_lines(content):
    """Add line_no to VoucherLine.objects.create calls"""
    lines = content.split('\n')
    new_lines = []
    line_counter = {}
    current_voucher = None
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is a VoucherLine.objects.create line
        if 'VoucherLine.objects.create(' in line:
            # Look ahead to find the voucher parameter
            j = i
            voucher_name = None
            has_line_no = False
            create_block = []
            
            while j < len(lines):
                create_block.append(lines[j])
                if 'voucher=' in lines[j]:
                    match = re.search(r'voucher=(\w+)', lines[j])
                    if match:
                        voucher_name = match.group(1)
                if 'line_no=' in lines[j]:
                    has_line_no = True
                if ')' in lines[j]:
                    break
                j += 1
            
            if voucher_name and not has_line_no:
                # Initialize counter for this voucher if not exists
                if voucher_name not in line_counter:
                    line_counter[voucher_name] = 1
                else:
                    line_counter[voucher_name] += 1
                
                # Add line_no parameter
                # Find the line with voucher= and add line_no after it
                for k, create_line in enumerate(create_block):
                    if 'voucher=' in create_line and not create_line.strip().endswith(','):
                        create_block[k] = create_line + ','
                    if 'voucher=' in create_line:
                        # Add line_no on the next line with proper indentation
                        indent = len(create_line) - len(create_line.lstrip())
                        new_line = ' ' * indent + f'line_no={line_counter[voucher_name]},'
                        create_block.insert(k + 1, new_line)
                        break
                
                # Add the modified block
                new_lines.extend(create_block)
                i = j + 1
                continue
        
        new_lines.append(line)
        i += 1
    
    return '\n'.join(new_lines)

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
        new_content = fix_voucher_lines(content)
        
        if new_content != content:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"Fixed {file_path}")
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print(f"\nFixed {fixed_count} files")
