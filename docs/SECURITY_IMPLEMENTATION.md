# Security Implementation Documentation

## Overview

This document describes the comprehensive security measures implemented in the Vendor ERP Backend system. The implementation covers all required security domains including Authorization, Encryption, Hashing, Digital Signatures, and Encoding.

---

## Table of Contents

1. [Authorization - Access Control](#1-authorization---access-control)
2. [Encryption](#2-encryption)
3. [Hashing & Digital Signature](#3-hashing--digital-signature)
4. [Encoding Techniques](#4-encoding-techniques)
5. [Security Best Practices](#5-security-best-practices)
6. [API Reference](#6-api-reference)
7. [Testing Guide](#7-testing-guide)

---

## 1. Authorization - Access Control

### 1.1 Access Control Matrix (ACM)

**Location**: `core/security/acl.py`

The Access Control Matrix defines who (subjects) can access what (objects) with which permissions. Our implementation includes **7 subjects** and **12 objects**.

#### Subjects (Roles)

| Role | Description | Policy Justification |
|------|-------------|---------------------|
| **OWNER** | Company owner | Full administrative rights to manage all aspects of the business |
| **ADMIN** | Administrator | Can manage day-to-day operations and users but cannot modify sensitive settings |
| **ACCOUNTANT** | Financial staff | Write access to financial documents, limited access to other areas |
| **MANAGER** | Operations manager | Oversees operations and orders with limited financial access |
| **STOCK_KEEPER** | Inventory manager | Manages inventory, no access to financial data |
| **SALES** | Sales team | Create orders and invoices, manage parties |
| **VIEWER** | Read-only user | Read-only access for reporting and monitoring |

#### Objects (Resources)

| Resource Type | Description |
|---------------|-------------|
| COMPANY | Company settings and configuration |
| VOUCHER | Transaction vouchers |
| INVOICE | Sales and purchase invoices |
| PRODUCT | Product catalog |
| ORDER | Sales and purchase orders |
| LEDGER | Account ledgers |
| REPORT | Financial reports |
| USER | User management |
| PARTY | Customers and suppliers |
| STOCK | Inventory stock |
| PAYMENT | Payment records |
| SETTINGS | System settings |

#### Access Control Matrix

```
                | COMPANY | VOUCHER | INVOICE | PRODUCT | LEDGER | REPORT | USER  |
----------------+---------+---------+---------+---------+--------+--------+-------+
OWNER           | ADMIN   | ADMIN   | ADMIN   | ADMIN   | ADMIN  | ADMIN  | ADMIN |
ADMIN           | READ    | WRITE   | WRITE   | WRITE   | READ   | READ   | WRITE |
ACCOUNTANT      | READ    | WRITE   | WRITE   | READ    | WRITE  | READ   | NONE  |
MANAGER         | READ    | READ    | WRITE   | WRITE   | READ   | READ   | READ  |
STOCK_KEEPER    | READ    | NONE    | READ    | WRITE   | NONE   | READ   | NONE  |
SALES           | READ    | READ    | WRITE   | READ    | NONE   | READ   | NONE  |
VIEWER          | READ    | READ    | READ    | READ    | READ   | READ   | NONE  |
```

### 1.2 Implementation Details

#### Access Control List (ACL)

```python
from core.security import AccessControlList, ResourceType, Permission

# Create ACL instance
acl = AccessControlList()

# Grant permissions
acl.grant(
    subject="role:ACCOUNTANT",
    resource_type=ResourceType.INVOICE,
    permission=Permission.WRITE,
    justification="Accountants need to create and modify invoices"
)

# Check permissions
if acl.check_permission("role:ACCOUNTANT", ResourceType.INVOICE, Permission.WRITE):
    # Allow access
    pass
```

#### Access Control Matrix Usage

```python
from core.security import AccessControlMatrix, ResourceType, Permission

# Create ACM instance
acm = AccessControlMatrix(company_id="company-uuid")

# Check access
if acm.check_access("ACCOUNTANT", ResourceType.INVOICE, Permission.WRITE):
    # Process invoice
    pass

# Get all permissions for a role
permissions = acm.get_role_permissions("ACCOUNTANT")

# Print the matrix
print(acm.print_matrix())
```

#### Decorator for Service Functions

```python
from core.security import require_permission, ResourceType, Permission

@require_permission(ResourceType.INVOICE, Permission.WRITE)
def create_invoice(user, invoice_data):
    """Only users with WRITE permission on INVOICE can call this."""
    # Create invoice logic
    pass
```

---

## 2. Encryption

### 2.1 Key Exchange Mechanism

**Location**: `core/security/encryption.py`

The system implements secure key exchange using RSA for asymmetric operations and derives session keys using HKDF.

#### Key Exchange Process

```
┌─────────────────────────────────────────────────────────────────┐
│                        KEY EXCHANGE                             │
├─────────────────────────────────────────────────────────────────┤
│  1. Recipient generates RSA key pair (2048/4096 bits)           │
│  2. Recipient shares public key with sender                     │
│  3. Sender generates random AES-256 session key                 │
│  4. Sender encrypts session key with recipient's public key     │
│  5. Sender sends encrypted session key to recipient             │
│  6. Recipient decrypts session key with private key             │
│  7. Both parties now share the session key for AES encryption   │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
from core.security import KeyExchange, RSACipher

# Key exchange
exchange = KeyExchange()

# Recipient generates keys
recipient_keys = exchange.generate_recipient_keys(key_size=2048)

# Share recipient_keys.public_key with sender...

# Sender creates and encrypts session key
session_key, encrypted_key = exchange.create_session_key(recipient_keys.public_key)

# Recipient recovers session key
recovered_key = exchange.recover_session_key(encrypted_key, recipient_keys.private_key)

assert session_key == recovered_key  # Both have the same key now
```

### 2.2 AES Encryption (Symmetric)

**Algorithm**: AES-256-GCM (Galois/Counter Mode)

| Feature | Value |
|---------|-------|
| Key Size | 256 bits (32 bytes) |
| IV/Nonce Size | 96 bits (12 bytes) |
| Authentication Tag | 128 bits (16 bytes) |
| Mode | GCM (Authenticated Encryption) |

#### Implementation

```python
from core.security import AESCipher

cipher = AESCipher()

# Generate key
key = cipher.generate_key()

# Or derive from password
key, salt = cipher.derive_key("password123", iterations=100000)

# Encrypt
encrypted = cipher.encrypt(b"sensitive data", key)

# Decrypt
decrypted = cipher.decrypt(encrypted, key)
```

### 2.3 RSA Encryption (Asymmetric)

**Algorithm**: RSA with OAEP padding

| Feature | Value |
|---------|-------|
| Key Size | 2048 or 4096 bits |
| Padding | OAEP with SHA-256 |
| Max Plaintext (2048-bit) | ~190 bytes |

#### Implementation

```python
from core.security import RSACipher

cipher = RSACipher()

# Generate key pair
key_pair = cipher.generate_key_pair(key_size=2048)

# Encrypt with public key
encrypted = cipher.encrypt(b"secret", key_pair.public_key)

# Decrypt with private key
decrypted = cipher.decrypt(encrypted, key_pair.private_key)

# Export keys
public_pem = key_pair.get_public_pem()
private_pem = key_pair.get_private_pem(password="key-password")
```

### 2.4 Hybrid Encryption

Combines RSA and AES for encrypting large data securely.

```
┌─────────────────────────────────────────────────────────────────┐
│                     HYBRID ENCRYPTION                           │
├─────────────────────────────────────────────────────────────────┤
│  ENCRYPTION:                                                    │
│  1. Generate random AES-256 session key                         │
│  2. Encrypt data with AES-256-GCM using session key             │
│  3. Encrypt session key with recipient's RSA public key         │
│  4. Package: {encrypted_key, encrypted_data, iv, tag}           │
│                                                                 │
│  DECRYPTION:                                                    │
│  1. Decrypt session key with RSA private key                    │
│  2. Decrypt data with AES-256-GCM using session key             │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
from core.security import HybridEncryption, RSACipher

hybrid = HybridEncryption()
key_pair = RSACipher().generate_key_pair()

# Encrypt large data
large_data = b"x" * 100000  # 100KB
encrypted = hybrid.encrypt(large_data, key_pair.public_key)

# Decrypt
decrypted = hybrid.decrypt(encrypted, key_pair.private_key)
```

### 2.5 High-Level Encryption Service

```python
from core.security import EncryptionService

service = EncryptionService()

# Password-based encryption
encrypted = service.encrypt_with_password("sensitive data", "password123")
decrypted = service.decrypt_with_password(encrypted, "password123")

# Key-based encryption for recipients
keys = service.generate_user_keys()
encrypted = service.encrypt_for_recipient(b"data", keys.public_key)
decrypted = service.decrypt_for_recipient(encrypted, keys.private_key)
```

---

## 3. Hashing & Digital Signature

### 3.1 Hashing with Salt

**Location**: `core/security/hashing.py`

Secure password storage using industry-standard algorithms with automatic salt generation.

#### Supported Algorithms

| Algorithm | Security Level | Use Case |
|-----------|---------------|----------|
| Argon2id | Highest | Password hashing (recommended) |
| PBKDF2-SHA256 | High | Password hashing (fallback) |
| SHA-256 | Standard | Data integrity |
| SHA-512 | Standard | Data integrity |
| BLAKE2b | High | Fast secure hashing |

#### Password Hashing Implementation

```python
from core.security import PasswordHasher

hasher = PasswordHasher()

# Hash a password (salt is automatically generated)
hashed = hasher.hash("user_password")
# Output: $argon2id$v=19$m=65536,t=3,p=4$randomsalt$hashedvalue

# Verify password
is_valid = hasher.verify("user_password", hashed)

# Check if rehash is needed (e.g., security parameters upgraded)
if hasher.needs_rehash(hashed):
    new_hash = hasher.hash("user_password")
    # Update stored hash
```

#### General Hashing with Salt

```python
from core.security import HashingService, HashAlgorithm

hasher = HashingService(algorithm=HashAlgorithm.SHA256)

# Hash with auto-generated salt
hashed = hasher.hash_with_salt(b"data to hash")

# Verify
is_valid = hasher.verify_hash(b"data to hash", hashed)

# Hash a file
file_hash = hasher.hash_file("/path/to/file.pdf")
```

### 3.2 HMAC (Message Authentication)

```python
from core.security import HMACService

hmac_service = HMACService()

# Generate key
key = hmac_service.generate_key()

# Create MAC
mac = hmac_service.create_mac(b"message", key)

# Verify MAC
is_valid = hmac_service.verify_mac(b"message", mac, key)

# Sign structured data
signed = hmac_service.sign_data({"user_id": 123, "action": "login"}, key)

# Verify and decode
data = hmac_service.verify_signed_data(signed, key)
```

### 3.3 Digital Signatures

Hash-based digital signatures using RSA-PSS for data authenticity and integrity.

```
┌─────────────────────────────────────────────────────────────────┐
│                    DIGITAL SIGNATURE                            │
├─────────────────────────────────────────────────────────────────┤
│  SIGNING:                                                       │
│  1. Hash the message (SHA-256)                                  │
│  2. Sign hash with signer's RSA private key (PSS padding)       │
│  3. Output: {signature, algorithm, hash_algorithm}              │
│                                                                 │
│  VERIFICATION:                                                  │
│  1. Hash the message (SHA-256)                                  │
│  2. Verify signature with signer's RSA public key               │
│  3. Returns: True/False                                         │
└─────────────────────────────────────────────────────────────────┘
```

#### Implementation

```python
from core.security import DigitalSignature, RSACipher

signer = DigitalSignature()
key_pair = RSACipher().generate_key_pair()

# Sign a document
document = b"Important contract content..."
signature = signer.sign(document, key_pair.private_key)

# Verify signature
is_valid = signer.verify(document, signature, key_pair.public_key)
print(f"Signature valid: {is_valid}")

# Sign with metadata (for document signing)
signed_doc = signer.sign_document(document, key_pair.private_key)
# Output: {document_hash, signature: {signature, algorithm, hash_algorithm}}

# Verify document
result = signer.verify_document(document, signed_doc, key_pair.public_key)
print(f"Valid: {result['valid']}, Hash OK: {result['hash_valid']}, Sig OK: {result['signature_valid']}")
```

---

## 4. Encoding Techniques

### 4.1 Base64 Encoding

**Location**: `core/security/encoding.py`

Base64 encodes binary data as ASCII text for transport over text-based protocols.

#### ⚠️ Security Warnings

| Risk | Description |
|------|-------------|
| **NOT Encryption** | Base64 is easily decoded by anyone |
| **No Confidentiality** | Data is completely exposed |
| **No Integrity** | No protection against tampering |

#### Implementation

```python
from core.security import Base64Encoder

encoder = Base64Encoder()

# Standard Base64
encoded = encoder.encode(b"Hello, World!")
# Output: "SGVsbG8sIFdvcmxkIQ=="

decoded = encoder.decode(encoded)
# Output: b"Hello, World!"

# URL-safe Base64 (for URLs and filenames)
encoded_url = encoder.encode_urlsafe(b"data?with=special&chars")
decoded_url = encoder.decode_urlsafe(encoded_url)

# Validate Base64
is_valid = encoder.is_valid_base64("SGVsbG8=")  # True
```

### 4.2 QR Code Generation

#### ⚠️ Security Warnings

| Risk | Mitigation |
|------|------------|
| **Phishing** | Validate URLs before following |
| **Malware** | Scan linked content |
| **QRLjacking** | Implement session timeouts |

#### Implementation

```python
from core.security import QRCodeGenerator, QRErrorCorrection

generator = QRCodeGenerator()

# Generate QR code as PNG bytes
qr_bytes = generator.generate(
    "https://example.com/verify?token=abc123",
    error_correction=QRErrorCorrection.HIGH,
    box_size=10,
    border=4
)

# Save to file
generator.save("https://example.com", "qrcode.png")

# Generate for web embedding (base64)
qr_base64 = generator.generate_base64("data")

# Generate as data URI for HTML
qr_uri = generator.generate_data_uri("data")
# Use in HTML: <img src="{qr_uri}">
```

### 4.3 Barcode Generation

```python
from core.security import BarcodeGenerator, BarcodeType

generator = BarcodeGenerator()

# Generate Code128 barcode
barcode_bytes = generator.generate("PRODUCT123", BarcodeType.CODE128)

# Generate EAN-13 barcode
ean_bytes = generator.generate("5901234123457", BarcodeType.EAN13)

# Validate EAN-13
is_valid, message = generator.validate_ean13("5901234123457")

# Save to file
generator.save("ABC123", "barcode.png", BarcodeType.CODE128)
```

### 4.4 High-Level Encoding Service

```python
from core.security import EncodingService

service = EncodingService()

# Base64
encoded = service.base64_encode("Hello, World!")
decoded = service.base64_decode(encoded)

# URL-safe Base64
url_safe = service.base64_encode_urlsafe("query=value&other=param")

# Hex encoding
hex_str = service.hex_encode(b"\x00\x01\x02\x03")
bytes_data = service.hex_decode(hex_str)

# Secure encoding with integrity check
secured = service.secure_encode(b"important data", include_checksum=True)
original = service.secure_decode(secured, verify_checksum=True)

# QR Code (if available)
if service.is_qr_available():
    qr = service.generate_qr_code("https://example.com")
    qr_uri = service.generate_qr_code_data_uri("data")

# Barcode (if available)
if service.is_barcode_available():
    bc = service.generate_barcode("PRODUCT123")
```

---

## 5. Security Best Practices

### 5.1 Access Control Best Practices

1. **Principle of Least Privilege**: Grant minimum permissions required
2. **Separation of Duties**: Financial access separated from operational
3. **Regular Audits**: Review access control matrix periodically
4. **Logging**: Log all permission checks and access decisions

### 5.2 Encryption Best Practices

1. **Key Management**: Store keys securely, never in code
2. **Key Rotation**: Regularly rotate encryption keys
3. **Algorithm Selection**: Use AES-256-GCM for symmetric, RSA-2048+ for asymmetric
4. **Hybrid Approach**: Use hybrid encryption for large data

### 5.3 Hashing Best Practices

1. **Password Storage**: Always use Argon2 or PBKDF2 with salt
2. **Never Store Plaintext**: Hash passwords immediately
3. **Upgrade Hashes**: Rehash when security parameters change
4. **Constant-Time Comparison**: Prevent timing attacks

### 5.4 Encoding Security

1. **Never Encode Secrets**: Base64 is not encryption
2. **Encrypt First**: Always encrypt sensitive data before encoding
3. **Validate Decoded Data**: Check for malicious content
4. **Add Integrity Checks**: Use HMAC or checksums

---

## 6. API Reference

### 6.1 Access Control Module

| Class | Description |
|-------|-------------|
| `Permission` | Enum: NONE, READ, WRITE, DELETE, ADMIN |
| `ResourceType` | Enum: COMPANY, VOUCHER, INVOICE, etc. |
| `ACLEntry` | Single ACL entry with subject, resource, permission |
| `AccessControlList` | ACL implementation with grant/revoke/check |
| `AccessControlMatrix` | Matrix view of access control |
| `require_permission()` | Decorator for service functions |

### 6.2 Encryption Module

| Class | Description |
|-------|-------------|
| `AESCipher` | AES-256-GCM encryption |
| `RSACipher` | RSA asymmetric encryption |
| `HybridEncryption` | Combined RSA + AES |
| `KeyExchange` | Secure key exchange |
| `EncryptionService` | High-level encryption interface |

### 6.3 Hashing Module

| Class | Description |
|-------|-------------|
| `HashingService` | General cryptographic hashing |
| `PasswordHasher` | Secure password hashing with salt |
| `HMACService` | Message authentication codes |
| `DigitalSignature` | RSA-PSS digital signatures |

### 6.4 Encoding Module

| Class | Description |
|-------|-------------|
| `Base64Encoder` | Standard and URL-safe Base64 |
| `HexEncoder` | Hexadecimal encoding |
| `QRCodeGenerator` | QR code image generation |
| `BarcodeGenerator` | Barcode image generation |
| `EncodingService` | Unified encoding interface |

---

## 7. Testing Guide

### 7.1 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-django

# Run all security tests
python -m pytest tests/test_security.py -v

# Run specific test module
python -m pytest tests/test_security.py::test_acl -v
```

### 7.2 Example Test Cases

```python
# Test Access Control
def test_acl_permission_check():
    acm = AccessControlMatrix()
    
    # OWNER should have ADMIN on everything
    assert acm.check_access("OWNER", ResourceType.INVOICE, Permission.ADMIN)
    
    # VIEWER should only have READ
    assert acm.check_access("VIEWER", ResourceType.INVOICE, Permission.READ)
    assert not acm.check_access("VIEWER", ResourceType.INVOICE, Permission.WRITE)

# Test Encryption
def test_aes_encryption():
    cipher = AESCipher()
    key = cipher.generate_key()
    
    plaintext = b"Secret message"
    encrypted = cipher.encrypt(plaintext, key)
    decrypted = cipher.decrypt(encrypted, key)
    
    assert decrypted == plaintext

# Test Password Hashing
def test_password_hashing():
    hasher = PasswordHasher()
    
    password = "secure_password_123"
    hashed = hasher.hash(password)
    
    assert hasher.verify(password, hashed)
    assert not hasher.verify("wrong_password", hashed)

# Test Digital Signature
def test_digital_signature():
    signer = DigitalSignature()
    key_pair = RSACipher().generate_key_pair()
    
    document = b"Important contract"
    signature = signer.sign(document, key_pair.private_key)
    
    assert signer.verify(document, signature, key_pair.public_key)
    assert not signer.verify(b"Modified", signature, key_pair.public_key)
```

---

## 8. Dependencies

### Required Packages

```txt
cryptography>=41.0.0    # AES, RSA, hashing
```

### Optional Packages

```txt
argon2-cffi>=21.0.0     # Argon2 password hashing
qrcode[pil]>=7.0        # QR code generation
python-barcode[images]  # Barcode generation
```

### Installation

```bash
# Core security features
pip install cryptography

# All features
pip install cryptography argon2-cffi qrcode[pil] python-barcode[images]
```

---

## 9. Changelog

### v1.0.0 (February 2026)

- Initial implementation of security module
- Access Control Matrix with 7 subjects and 12 objects
- AES-256-GCM encryption
- RSA-2048/4096 encryption
- Hybrid encryption (RSA + AES)
- Key exchange mechanism
- Password hashing with Argon2/PBKDF2
- HMAC message authentication
- RSA-PSS digital signatures
- Base64 encoding (standard and URL-safe)
- QR code generation
- Barcode generation (Code128, EAN13, etc.)

---

## 10. Contact & Support

For security-related questions or to report vulnerabilities:

- Review the implementation in `core/security/`
- Check the inline documentation for each module
- Follow secure coding guidelines in this document

---

*This document is auto-generated from the security implementation. Last updated: February 2026*
