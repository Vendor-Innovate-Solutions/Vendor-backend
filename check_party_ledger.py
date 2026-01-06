import re
import os
import glob

def fix_party_fixtures(filepath):
    """
    Add ledger creation before Party.objects.create if ledger is missing.
    This is complex because we need to:
    1. Detect Party.objects.create without ledger=
    2. Insert AccountGroup and Ledger creation before it
    3. Add ledger= parameter to Party.objects.create
    """
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Find Party.objects.create blocks without ledger=
    pattern = r'(\s+)(party|customer|supplier|[a-z_]+\s*=\s*Party\.objects\.create)\(\s*\n(\s+)company=([^,]+),\s*\n(\s+)name="([^"]+)",\s*\n(?:\s+code="[^"]+",\s*\n)?(\s+)party_type=[\'"]([A-Z]+)[\'"]'
    
    def add_ledger(match):
        indent1 = match.group(1)
        party_var = match.group(2)
        indent2 = match.group(3)
        company_var = match.group(4)
        name = match.group(6)
        party_type = match.group(8)
        
        # Determine ledger type based on party_type
        if party_type == 'CUSTOMER':
            account_type = 'DEBTOR'
            group_name = 'Sundry Debtors'
            group_code = 'SUNDRY_DEBTORS'
            nature = 'ASSET'
        elif party_type == 'SUPPLIER':
            account_type = 'CREDITOR'
            group_name = 'Sundry Creditors'
            group_code = 'SUNDRY_CREDITORS'
            nature = 'LIABILITY'
        else:
            account_type = 'DEBTOR'
            group_name = 'Sundry Debtors'
            group_code = 'SUNDRY_DEBTORS'
            nature = 'ASSET'
        
        # Generate safe variable name from party variable
        if '=' in party_var:
            var_name = party_var.split('=')[0].strip()
        else:
            var_name = party_var.strip()
        
        ledger_var = f"{var_name}_ledger"
        group_var = f"{var_name}_group"
        
        # Build the insertion
        insertion = f'''{indent1}# Create account group and ledger for {var_name}
{indent1}{group_var} = AccountGroup.objects.create(
{indent2}company={company_var},
{indent2}code='{group_code}',
{indent2}name='{group_name}',
{indent2}nature='{nature}',
{indent2}report_type='BS'
{indent1})
{indent1}
{indent1}{ledger_var} = Ledger.objects.create(
{indent2}company={company_var},
{indent2}code='{var_name.upper()[:20]}_LED',
{indent2}name="{name}",
{indent2}group={group_var},
{indent2}account_type='{account_type}',
{indent2}opening_balance=Decimal('0.00'),
{indent2}opening_balance_fy=self.fy,
{indent2}opening_balance_type='DR',
{indent2}is_active=True
{indent1})
{indent1}
{indent1}{party_var}(
{indent2}company={company_var},
{indent2}name="{name}",
{indent2}ledger={ledger_var},
{indent2}party_type='{party_type}' '''
        
        return insertion
    
    # This is too complex for regex. Let's use a simpler approach:
    # Just add a comment where ledger is needed
    
    # Check if file has Party.objects.create
    if 'Party.objects.create(' not in content:
        return False
    
    # Check if ledger is imported
    if 'from apps.accounting.models import' in content:
        if 'Ledger' not in content.split('from apps.accounting.models import')[1].split('\n')[0]:
            # Add Ledger to imports
            content = content.replace(
                'from apps.accounting.models import ',
                'from apps.accounting.models import Ledger, AccountGroup, '
            )
    
    # Add Decimal import if missing
    if 'from decimal import Decimal' not in content:
        # Find first import line
        import_pos = content.find('import')
        if import_pos > 0:
            content = content[:import_pos] + 'from decimal import Decimal\n' + content[import_pos:]
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write(content)
        return True
    
    return False

# For now, let's just check which files need manual fixing
test_files = []
test_files.extend(glob.glob("tests/*.py"))
test_files.extend(glob.glob("tests/**/*.py", recursive=True))

files_needing_fix = []
for filepath in test_files:
    if not os.path.isfile(filepath):
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find Party.objects.create without ledger=
        if 'Party.objects.create(' in content:
            # Check if any have ledger= parameter
            party_creates = re.findall(r'Party\.objects\.create\([^)]+\)', content, re.DOTALL)
            for create in party_creates:
                if 'ledger=' not in create:
                    files_needing_fix.append(filepath)
                    print(f"Needs ledger fix: {filepath}")
                    break
    except Exception as e:
        pass

print(f"\n{len(files_needing_fix)} files need Party ledger fixes")
print("\nNote: These files need manual intervention or complex script")
