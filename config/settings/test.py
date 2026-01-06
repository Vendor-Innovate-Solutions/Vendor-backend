"""
Test settings for Vendor ERP Backend.
"""
from .base import *

# Use PostgreSQL test database (pytest-django will create test_vendor)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'vendor',  # pytest will prepend 'test_' to make 'test_vendor'
        'USER': 'postgres',
        'PASSWORD': 'venkat*2005',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Disable password validation for tests
AUTH_PASSWORD_VALIDATORS = []

# Use simple password hasher for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Email backend for tests
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
