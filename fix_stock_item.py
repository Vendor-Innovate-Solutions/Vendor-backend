import re
import os
import glob

def fix_stock_item_fields(content):
    """
    Fix StockItem.objects.create:
    - code= -> sku=
    - unit= -> uom=
    """
    
    # Pattern 1: code= in StockItem context
    content = re.sub(
        r'(StockItem\.objects\.create\([^)]*\n[^)]*)\bcode=',
        r'\1sku=',
        content,
        flags=re.DOTALL
    )
    
    # Pattern 2: unit= in StockItem context (but be careful not to replace 'unit' in other contexts)
    # More precise: find StockItem.objects.create blocks and replace unit= with uom=
    pattern = r'(StockItem\.objects\.create\([^)]*)\bunit='
    replacement = r'\1uom='
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
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
        
        new_content = fix_stock_item_fields(original_content)
        
        if new_content != original_content:
            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
            print(f"Fixed StockItem in: {filepath}")
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

print(f"\nTotal files fixed: {fixed_count}")
print("Done!")
