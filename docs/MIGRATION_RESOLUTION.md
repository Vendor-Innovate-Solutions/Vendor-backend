# Migration Conflict Resolution Summary

## Issue Encountered
When attempting to run migrations, Django detected conflicting migrations with multiple leaf nodes:
- `0002_add_selected_role` (newly created)
- `0004_remove_user_email_verified` (existing)

Error:
```
CommandError: Conflicting migrations detected; multiple leaf nodes in the migration graph: 
(0002_add_selected_role, 0004_remove_user_email_verified in core_auth)
```

## Root Cause
The new migration was incorrectly numbered as `0002_add_selected_role.py` when there was already a `0002_user_active_company.py` migration in the app, creating divergent migration branches.

Additionally, the migration referenced the wrong app name (`auth` instead of `core_auth`).

## Solution Applied

### Step 1: Identified Existing Migration Order
```
0001_initial.py
0002_user_active_company.py
0003_user_created_at_user_updated_at.py
0004_remove_user_email_verified.py
```

### Step 2: Removed Conflicting Migration
Deleted the incorrectly numbered `0002_add_selected_role.py` file.

### Step 3: Created Correct Migration
Created new file: `0005_add_selected_role.py` with:
- **Correct numbering**: 0005 (after 0004)
- **Correct dependency**: `('core_auth', '0004_remove_user_email_verified')`
- **Same operations**: Add CharField with UserRole choices

### Step 4: Verified and Applied
```bash
$ python manage.py makemigrations --dry-run
No changes detected  ✓

$ python manage.py migrate core_auth --plan
Planned operations:
  core_auth.0005_add_selected_role
    Add field selected_role to user

$ python manage.py migrate core_auth
Operations to perform:
  Apply all migrations: core_auth
Running migrations:
  Applying core_auth.0005_add_selected_role... OK ✓
```

## Result
✅ Migration conflict resolved
✅ New field `User.selected_role` added to database
✅ All migrations in correct linear order
✅ Database schema updated successfully

## Migration Chain (Final)
```
0001_initial.py
    ↓
0002_user_active_company.py
    ↓
0003_user_created_at_user_updated_at.py
    ↓
0004_remove_user_email_verified.py
    ↓
0005_add_selected_role.py ← NEW (APPLIED ✓)
```

## Next Steps
- Continue with other app migrations as needed
- All core_auth migrations are now in sync
- Role-based access control system is database-ready

