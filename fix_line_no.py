import re
import os
import glob

def add_line_no_to_voucher_lines(content):
    """
    Add line_no to VoucherLine.objects.create if missing.
    Tracks line numbers within each voucher context.
    """
    # Find all VoucherLine.objects.create blocks
    # We'll add line_no=1, line_no=2, etc. based on position
    
    # This is complex, so let's use a simpler approach:
    # Add line_no=1 after voucher= if line_no is not present
    pattern = r'(VoucherLine\.objects\.create\(\s*\n\s*voucher=[^,]+,)(\s*\n\s*(?!line_no))'
    
    # We need to track context to number lines correctly
    # For now, let's just add line_no=1 to all (can be fixed manually if needed)
    
    lines = content.split('\n')
    new_lines = []
    line_counter = {}
    current_voucher = None
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        # Detect voucher creation
        if 'voucher = Voucher.objects.create(' in line:
            current_voucher = 'voucher'
            line_counter[current_voucher] = 0
        
        # Detect VoucherLine.objects.create with voucher parameter
        if 'VoucherLine.objects.create(' in line:
            # Look ahead to see if line_no is already there
            has_line_no = False
            for j in range(i+1, min(i+10, len(lines))):
                if 'line_no=' in lines[j]:
                    has_line_no = True
                    break
                if ')' in lines[j] and '=' not in lines[j]:
                    break
            
            if not has_line_no:
                # Find the line with voucher= and add line_no after it
                for j in range(i+1, min(i+10, len(lines))):
                    if 'voucher=' in lines[j]:
                        # Add line_no on next line
                        line_counter[current_voucher] = line_counter.get(current_voucher, 0) + 1
                        indent = len(lines[j]) - len(lines[j].lstrip())
                        new_lines.append(' ' * indent + f'line_no={line_counter[current_voucher]},')
                        break
    
    return '\n'.join(new_lines)

# Find all test files
test_files = []
test_files.extend(glob.glob("tests/*.py"))
test_files.extend(glob.glob("tests/**/*.py", recursive=True))

fixed_count = 0
for filepath in test_files:
    if not os.path.isfile(filepath):
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Simple pattern: add line_no=1 after voucher= if missing
        pattern = r'(VoucherLine\.objects\.create\(\s*\n\s*voucher=[^,]+,)(\s*\n\s*(?!line_no)ledger=)'
        replacement = r'\1\n            line_no=1,\2'
        new_content = re.sub(pattern, replacement, original_content)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
            print(f"Added line_no to: {filepath}")
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

print(f"\nTotal files fixed: {fixed_count}")
print("Done!")
