"""
Core Security Module for Vendor ERP Backend.

This module provides comprehensive security features including:
- Access Control Matrix (ACL)
- Encryption (AES/RSA hybrid)
- Hashing with Salt
- Digital Signatures
- Encoding (Base64, QR Code)
"""

from .acl import AccessControlMatrix, AccessControlList, Permission, ACLEntry
from .encryption import (
    EncryptionService,
    KeyExchange,
    AESCipher,
    RSACipher,
    HybridEncryption,
)
from .hashing import (
    HashingService,
    PasswordHasher,
    DigitalSignature,
    HMACService,
)
from .encoding import (
    EncodingService,
    Base64Encoder,
    QRCodeGenerator,
)

__all__ = [
    # ACL
    'AccessControlMatrix',
    'AccessControlList',
    'Permission',
    'ACLEntry',
    # Encryption
    'EncryptionService',
    'KeyExchange',
    'AESCipher',
    'RSACipher',
    'HybridEncryption',
    # Hashing
    'HashingService',
    'PasswordHasher',
    'DigitalSignature',
    'HMACService',
    # Encoding
    'EncodingService',
    'Base64Encoder',
    'QRCodeGenerator',
]
