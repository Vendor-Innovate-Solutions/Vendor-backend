import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

from core.auth.models import User
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.authentication import JWTAuthentication

token_str = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzcwMjAyMjk1LCJpYXQiOjE3NzAxMTU4OTUsImp0aSI6ImNjNjk2NjAzYWMyNDQ1NGViOWJjNzI5YjkzOTJhNTdhIiwidXNlcl9pZCI6IjEiLCJ1c2VybmFtZSI6Impvc2h1YUBnbWFpbC5jb20iLCJlbWFpbCI6Impvc2h1YUBnbWFpbC5jb20iLCJpc19pbnRlcm5hbF91c2VyIjp0cnVlLCJpc19wb3J0YWxfdXNlciI6ZmFsc2UsImFjdGl2ZV9jb21wYW55Ijp7ImlkIjoiM2I5ZGU5M2UtOTBkOS00ZjdjLTliMzItOWE0ODRjYTJmMmE4IiwibmFtZSI6IlZlbmRvciIsImNvZGUiOiJWRU5ET1I4T0xDIn0sInJvbGVzIjpbIk9XTkVSIiwiT1dORVIiLCJPV05FUiJdLCJhdmFpbGFibGVfY29tcGFuaWVzIjpbeyJpZCI6IjkxNTZiMDkxLTAyZjQtNGNlZi1hZjFmLTM0Y2IzNDU0NTJhMCIsIm5hbWUiOiJWZW5kb3IiLCJjb2RlIjoiVkVORE9ST1YxSCIsInJvbGUiOiJPV05FUiJ9LHsiaWQiOiJlMTEyODQxYy05YTkxLTRkMmYtOTRkYy1hY2E3ZjNlNjBhYjMiLCJuYW1lIjoiVmVuZG9yIiwiY29kZSI6IlZFTkRPUlZCMlMiLCJyb2xlIjoiT1dORVIifSx7ImlkIjoiM2I5ZGU5M2UtOTBkOS00ZjdjLTliMzItOWE0ODRjYTJmMmE4IiwibmFtZSI6IlZlbmRvciIsImNvZGUiOiJWRU5ET1I4T0xDIiwicm9sZSI6Ik9XTkVSIn1dLCJyZXRhaWxlciI6bnVsbH0.IDBmTh_msW0WXHzb6jDa5wRhZ4tWCYGjBNfRjK3nkaI'

print("=== Testing JWT Token ===")

# Test 1: Validate token
try:
    token = UntypedToken(token_str)
    print(f"Token is valid!")
    print(f"user_id from token: {token['user_id']} (type: {type(token['user_id'])})")
except Exception as e:
    print(f"Token validation failed: {e}")

# Test 2: Find user by id string "1" vs integer 1  
print("\n=== Testing User Lookup ===")
try:
    u1 = User.objects.get(id=1)
    print(f"User.objects.get(id=1) works: {u1}")
except Exception as e:
    print(f"User.objects.get(id=1) failed: {e}")

try:
    u2 = User.objects.get(id="1")
    print(f"User.objects.get(id='1') works: {u2}")
except Exception as e:
    print(f"User.objects.get(id='1') failed: {e}")

# Test 3: Full JWTAuthentication test
print("\n=== Testing JWTAuthentication ===")
auth = JWTAuthentication()
try:
    validated_token = auth.get_validated_token(token_str)
    print(f"Validated token: {validated_token}")
    user = auth.get_user(validated_token)
    print(f"User from token: {user}")
except Exception as e:
    print(f"JWTAuthentication failed: {e}")
    import traceback
    traceback.print_exc()
