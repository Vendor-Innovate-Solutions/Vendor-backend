"""
Hashing and Digital Signature Module.

This module provides secure hashing and digital signature services including:
- Password hashing with salt (using Argon2, bcrypt, PBKDF2)
- Cryptographic hashing (SHA-256, SHA-512, BLAKE2)
- HMAC (Hash-based Message Authentication Code)
- Digital signatures using RSA
- Data integrity verification

Security Requirements Covered:
- Hashing with Salt: Secure storage of passwords/data using hashing with salt
- Digital Signature using Hash: Demonstrate data integrity and authenticity 
  using hash-based digital signatures

Security Features:
- Argon2 for password hashing (winner of Password Hashing Competition)
- HMAC-SHA256 for message authentication
- RSA signatures with PSS padding
- Secure random salt generation
"""

import os
import hmac
import hashlib
import secrets
import base64
from typing import Tuple, Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import logging

logger = logging.getLogger(__name__)

# Try to import argon2, fall back to PBKDF2 if not available
try:
    import argon2
    from argon2 import PasswordHasher as Argon2Hasher
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False
    logger.warning("argon2-cffi not installed, falling back to PBKDF2 for password hashing")


class HashAlgorithm(Enum):
    """Available hash algorithms."""
    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE2B = "blake2b"
    BLAKE2S = "blake2s"
    SHA3_256 = "sha3_256"
    SHA3_512 = "sha3_512"


@dataclass
class HashedData:
    """Container for hashed data with metadata."""
    hash: bytes
    salt: Optional[bytes]
    algorithm: str
    iterations: Optional[int] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary with base64-encoded values."""
        return {
            'hash': base64.b64encode(self.hash).decode('utf-8'),
            'salt': base64.b64encode(self.salt).decode('utf-8') if self.salt else None,
            'algorithm': self.algorithm,
            'iterations': self.iterations,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HashedData':
        """Create from dictionary."""
        return cls(
            hash=base64.b64decode(data['hash']),
            salt=base64.b64decode(data['salt']) if data.get('salt') else None,
            algorithm=data['algorithm'],
            iterations=data.get('iterations'),
        )
    
    def to_string(self) -> str:
        """
        Convert to a single string format for storage.
        Format: $algorithm$iterations$salt$hash
        """
        salt_b64 = base64.b64encode(self.salt).decode() if self.salt else ""
        hash_b64 = base64.b64encode(self.hash).decode()
        iterations = self.iterations or 0
        return f"${self.algorithm}${iterations}${salt_b64}${hash_b64}"
    
    @classmethod
    def from_string(cls, encoded: str) -> 'HashedData':
        """Parse from string format."""
        parts = encoded.split('$')
        if len(parts) != 5:
            raise ValueError("Invalid hash string format")
        
        _, algorithm, iterations, salt_b64, hash_b64 = parts
        
        return cls(
            hash=base64.b64decode(hash_b64),
            salt=base64.b64decode(salt_b64) if salt_b64 else None,
            algorithm=algorithm,
            iterations=int(iterations) if iterations != "0" else None,
        )


class HashingService:
    """
    General-purpose cryptographic hashing service.
    
    Provides secure hash functions for data integrity verification
    and general hashing needs (NOT for passwords - use PasswordHasher).
    
    Example Usage:
        hasher = HashingService()
        
        # Simple hash
        hash_value = hasher.hash(b"data to hash")
        
        # Hash with salt
        hashed = hasher.hash_with_salt(b"data", salt_length=16)
        
        # Verify hash
        is_valid = hasher.verify_hash(b"data", hashed)
    """
    
    DEFAULT_SALT_LENGTH = 16  # 128 bits
    
    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256):
        """
        Initialize hashing service.
        
        Args:
            algorithm: Hash algorithm to use (default: SHA-256)
        """
        self.algorithm = algorithm
    
    def hash(self, data: bytes, algorithm: Optional[HashAlgorithm] = None) -> bytes:
        """
        Compute hash of data.
        
        Args:
            data: Data to hash
            algorithm: Optional override of default algorithm
            
        Returns:
            Hash digest as bytes
        """
        algo = algorithm or self.algorithm
        
        if algo == HashAlgorithm.BLAKE2B:
            return hashlib.blake2b(data).digest()
        elif algo == HashAlgorithm.BLAKE2S:
            return hashlib.blake2s(data).digest()
        else:
            hasher = hashlib.new(algo.value)
            hasher.update(data)
            return hasher.digest()
    
    def hash_hex(self, data: bytes, algorithm: Optional[HashAlgorithm] = None) -> str:
        """Compute hash and return as hex string."""
        return self.hash(data, algorithm).hex()
    
    def hash_with_salt(self, data: bytes, salt: Optional[bytes] = None,
                       salt_length: int = DEFAULT_SALT_LENGTH,
                       algorithm: Optional[HashAlgorithm] = None) -> HashedData:
        """
        Compute hash with a salt prepended.
        
        The salt is prepended to the data before hashing:
        hash(salt || data)
        
        Args:
            data: Data to hash
            salt: Optional salt (generated if not provided)
            salt_length: Length of salt to generate if not provided
            algorithm: Optional override of default algorithm
            
        Returns:
            HashedData containing hash, salt, and algorithm info
        """
        algo = algorithm or self.algorithm
        
        if salt is None:
            salt = secrets.token_bytes(salt_length)
        
        # Hash: salt || data
        salted_data = salt + data
        hash_value = self.hash(salted_data, algo)
        
        logger.debug(f"Created salted hash using {algo.value}")
        
        return HashedData(
            hash=hash_value,
            salt=salt,
            algorithm=algo.value,
        )
    
    def verify_hash(self, data: bytes, hashed: HashedData) -> bool:
        """
        Verify that data matches a salted hash.
        
        Args:
            data: Original data
            hashed: HashedData to verify against
            
        Returns:
            True if hash matches
        """
        algo = HashAlgorithm(hashed.algorithm)
        
        if hashed.salt:
            salted_data = hashed.salt + data
            computed = self.hash(salted_data, algo)
        else:
            computed = self.hash(data, algo)
        
        # Use constant-time comparison
        return hmac.compare_digest(computed, hashed.hash)
    
    def hash_file(self, filepath: str, algorithm: Optional[HashAlgorithm] = None,
                  chunk_size: int = 8192) -> str:
        """
        Compute hash of a file.
        
        Args:
            filepath: Path to file
            algorithm: Optional override of default algorithm
            chunk_size: Size of chunks to read
            
        Returns:
            Hash as hex string
        """
        algo = algorithm or self.algorithm
        
        if algo == HashAlgorithm.BLAKE2B:
            hasher = hashlib.blake2b()
        elif algo == HashAlgorithm.BLAKE2S:
            hasher = hashlib.blake2s()
        else:
            hasher = hashlib.new(algo.value)
        
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        
        return hasher.hexdigest()


class PasswordHasher:
    """
    Secure password hashing with salt.
    
    Uses Argon2 (preferred) or PBKDF2 for secure password storage.
    Argon2 is the winner of the Password Hashing Competition and provides
    resistance against GPU and ASIC attacks.
    
    Features:
    - Automatic salt generation
    - Configurable work factors
    - Constant-time verification
    - Hash format includes algorithm metadata
    
    Example Usage:
        hasher = PasswordHasher()
        
        # Hash a password
        hashed = hasher.hash("user_password")
        
        # Verify password
        is_valid = hasher.verify("user_password", hashed)
        
        # Check if rehash is needed (e.g., work factors changed)
        needs_rehash = hasher.needs_rehash(hashed)
    """
    
    # PBKDF2 settings
    PBKDF2_ITERATIONS = 260000  # OWASP 2023 recommendation
    PBKDF2_SALT_LENGTH = 16
    PBKDF2_HASH_LENGTH = 32
    
    def __init__(self, use_argon2: bool = True):
        """
        Initialize password hasher.
        
        Args:
            use_argon2: Use Argon2 if available (recommended)
        """
        self.use_argon2 = use_argon2 and ARGON2_AVAILABLE
        
        if self.use_argon2:
            # Argon2id with recommended settings
            self._argon2 = Argon2Hasher(
                time_cost=3,      # iterations
                memory_cost=65536, # 64 MB
                parallelism=4,
                hash_len=32,
                salt_len=16,
                type=argon2.Type.ID
            )
            logger.info("Using Argon2 for password hashing")
        else:
            logger.info("Using PBKDF2 for password hashing")
    
    def hash(self, password: str) -> str:
        """
        Hash a password for storage.
        
        Args:
            password: Plain text password
            
        Returns:
            Encoded hash string suitable for database storage
        """
        if self.use_argon2:
            # Argon2 handles salt internally
            return self._argon2.hash(password)
        else:
            return self._hash_pbkdf2(password)
    
    def _hash_pbkdf2(self, password: str) -> str:
        """Hash using PBKDF2."""
        salt = secrets.token_bytes(self.PBKDF2_SALT_LENGTH)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.PBKDF2_HASH_LENGTH,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        
        hash_value = kdf.derive(password.encode('utf-8'))
        
        # Format: $pbkdf2-sha256$iterations$salt$hash
        salt_b64 = base64.b64encode(salt).decode('ascii')
        hash_b64 = base64.b64encode(hash_value).decode('ascii')
        
        return f"$pbkdf2-sha256${self.PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"
    
    def verify(self, password: str, hashed: str) -> bool:
        """
        Verify a password against a hash.
        
        Uses constant-time comparison to prevent timing attacks.
        
        Args:
            password: Plain text password to verify
            hashed: Stored hash to verify against
            
        Returns:
            True if password matches
        """
        try:
            if hashed.startswith('$argon2'):
                if not self.use_argon2:
                    raise ValueError("Argon2 hash but Argon2 not available")
                return self._argon2.verify(hashed, password)
            elif hashed.startswith('$pbkdf2'):
                return self._verify_pbkdf2(password, hashed)
            else:
                logger.warning("Unknown hash format")
                return False
        except Exception as e:
            logger.warning(f"Password verification failed: {e}")
            return False
    
    def _verify_pbkdf2(self, password: str, hashed: str) -> bool:
        """Verify PBKDF2 hash."""
        try:
            parts = hashed.split('$')
            if len(parts) != 5 or parts[1] != 'pbkdf2-sha256':
                return False
            
            _, _, iterations_str, salt_b64, hash_b64 = parts
            iterations = int(iterations_str)
            salt = base64.b64decode(salt_b64)
            expected_hash = base64.b64decode(hash_b64)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=len(expected_hash),
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            
            computed_hash = kdf.derive(password.encode('utf-8'))
            
            return hmac.compare_digest(computed_hash, expected_hash)
        except Exception:
            return False
    
    def needs_rehash(self, hashed: str) -> bool:
        """
        Check if a hash should be rehashed.
        
        This is useful when upgrading security parameters.
        
        Args:
            hashed: Stored hash
            
        Returns:
            True if hash should be updated
        """
        if self.use_argon2:
            if not hashed.startswith('$argon2'):
                # Upgrade from PBKDF2 to Argon2
                return True
            return self._argon2.check_needs_rehash(hashed)
        else:
            if hashed.startswith('$argon2'):
                # Downgrade not supported
                return False
            if not hashed.startswith('$pbkdf2'):
                return True
            # Check iterations
            parts = hashed.split('$')
            if len(parts) >= 3:
                try:
                    iterations = int(parts[2])
                    return iterations < self.PBKDF2_ITERATIONS
                except ValueError:
                    return True
            return True


class HMACService:
    """
    HMAC (Hash-based Message Authentication Code) service.
    
    HMAC provides message authentication and integrity verification
    using a shared secret key.
    
    Example Usage:
        hmac_service = HMACService()
        
        # Generate a key
        key = hmac_service.generate_key()
        
        # Create MAC for a message
        mac = hmac_service.create_mac(b"message", key)
        
        # Verify MAC
        is_valid = hmac_service.verify_mac(b"message", mac, key)
    """
    
    KEY_SIZE = 32  # 256 bits
    
    def __init__(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256):
        """
        Initialize HMAC service.
        
        Args:
            algorithm: Hash algorithm for HMAC
        """
        self.algorithm = algorithm
    
    @staticmethod
    def generate_key(length: int = KEY_SIZE) -> bytes:
        """Generate a cryptographically secure random key."""
        return secrets.token_bytes(length)
    
    def create_mac(self, message: bytes, key: bytes,
                   algorithm: Optional[HashAlgorithm] = None) -> bytes:
        """
        Create HMAC for a message.
        
        Args:
            message: Message to authenticate
            key: Secret key
            algorithm: Optional override of default algorithm
            
        Returns:
            HMAC digest
        """
        algo = algorithm or self.algorithm
        
        return hmac.new(key, message, algo.value).digest()
    
    def create_mac_hex(self, message: bytes, key: bytes,
                       algorithm: Optional[HashAlgorithm] = None) -> str:
        """Create HMAC and return as hex string."""
        return self.create_mac(message, key, algorithm).hex()
    
    def verify_mac(self, message: bytes, mac: bytes, key: bytes,
                   algorithm: Optional[HashAlgorithm] = None) -> bool:
        """
        Verify HMAC for a message.
        
        Uses constant-time comparison to prevent timing attacks.
        
        Args:
            message: Original message
            mac: HMAC to verify
            key: Secret key
            algorithm: Optional override of default algorithm
            
        Returns:
            True if MAC is valid
        """
        computed_mac = self.create_mac(message, key, algorithm)
        return hmac.compare_digest(computed_mac, mac)
    
    def sign_data(self, data: Dict[str, Any], key: bytes) -> str:
        """
        Create a signed string from data.
        
        Useful for creating signed tokens or URLs.
        
        Args:
            data: Dictionary data to sign
            key: Secret key
            
        Returns:
            base64(json(data)).signature format
        """
        import json
        
        json_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        payload = base64.urlsafe_b64encode(json_bytes).decode('ascii')
        mac = self.create_mac(json_bytes, key)
        signature = base64.urlsafe_b64encode(mac).decode('ascii')
        
        return f"{payload}.{signature}"
    
    def verify_signed_data(self, signed: str, key: bytes) -> Optional[Dict[str, Any]]:
        """
        Verify and decode signed data.
        
        Args:
            signed: Signed string from sign_data
            key: Secret key
            
        Returns:
            Original data if signature is valid, None otherwise
        """
        import json
        
        try:
            payload, signature = signed.rsplit('.', 1)
            json_bytes = base64.urlsafe_b64decode(payload)
            mac = base64.urlsafe_b64decode(signature)
            
            if self.verify_mac(json_bytes, mac, key):
                return json.loads(json_bytes.decode('utf-8'))
            return None
        except Exception:
            return None


@dataclass
class DigitalSignatureData:
    """Container for digital signature with metadata."""
    signature: bytes
    algorithm: str
    hash_algorithm: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            'signature': base64.b64encode(self.signature).decode('utf-8'),
            'algorithm': self.algorithm,
            'hash_algorithm': self.hash_algorithm,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'DigitalSignatureData':
        """Create from dictionary."""
        return cls(
            signature=base64.b64decode(data['signature']),
            algorithm=data['algorithm'],
            hash_algorithm=data['hash_algorithm'],
        )


class DigitalSignature:
    """
    Digital Signature using RSA with hash.
    
    Provides non-repudiation and integrity verification using
    asymmetric cryptography. The signer uses their private key
    to create a signature that anyone can verify with the public key.
    
    Process:
    1. Hash the message (SHA-256)
    2. Sign the hash with RSA private key (PSS padding)
    3. Verification: hash message, verify signature with public key
    
    Features:
    - RSA-PSS padding (more secure than PKCS#1 v1.5)
    - SHA-256 hashing
    - Signature includes algorithm metadata
    
    Example Usage:
        from core.security.encryption import RSACipher
        
        signer = DigitalSignature()
        key_pair = RSACipher().generate_key_pair()
        
        # Sign a document
        message = b"Important document content"
        signature = signer.sign(message, key_pair.private_key)
        
        # Verify signature
        is_valid = signer.verify(message, signature, key_pair.public_key)
        print(f"Signature valid: {is_valid}")
    """
    
    def __init__(self, hash_algorithm: HashAlgorithm = HashAlgorithm.SHA256):
        """
        Initialize digital signature service.
        
        Args:
            hash_algorithm: Hash algorithm for signing
        """
        self.hash_algorithm = hash_algorithm
        self._hash_service = HashingService(hash_algorithm)
    
    def sign(self, message: bytes, private_key: rsa.RSAPrivateKey) -> DigitalSignatureData:
        """
        Create digital signature for a message.
        
        Args:
            message: Message to sign
            private_key: Signer's RSA private key
            
        Returns:
            DigitalSignatureData containing signature and metadata
        """
        # Get cryptography hash algorithm
        if self.hash_algorithm == HashAlgorithm.SHA256:
            hash_algo = hashes.SHA256()
        elif self.hash_algorithm == HashAlgorithm.SHA384:
            hash_algo = hashes.SHA384()
        elif self.hash_algorithm == HashAlgorithm.SHA512:
            hash_algo = hashes.SHA512()
        else:
            hash_algo = hashes.SHA256()
        
        # Sign using RSA-PSS
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hash_algo),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hash_algo
        )
        
        logger.info(f"Created digital signature for {len(message)} bytes of data")
        
        return DigitalSignatureData(
            signature=signature,
            algorithm="RSA-PSS",
            hash_algorithm=self.hash_algorithm.value,
        )
    
    def verify(self, message: bytes, signature: DigitalSignatureData,
               public_key: rsa.RSAPublicKey) -> bool:
        """
        Verify a digital signature.
        
        Args:
            message: Original message
            signature: Signature to verify
            public_key: Signer's RSA public key
            
        Returns:
            True if signature is valid
        """
        # Get cryptography hash algorithm
        if signature.hash_algorithm == "sha256":
            hash_algo = hashes.SHA256()
        elif signature.hash_algorithm == "sha384":
            hash_algo = hashes.SHA384()
        elif signature.hash_algorithm == "sha512":
            hash_algo = hashes.SHA512()
        else:
            hash_algo = hashes.SHA256()
        
        try:
            public_key.verify(
                signature.signature,
                message,
                padding.PSS(
                    mgf=padding.MGF1(hash_algo),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hash_algo
            )
            logger.info("Digital signature verified successfully")
            return True
        except Exception as e:
            logger.warning(f"Digital signature verification failed: {e}")
            return False
    
    def sign_document(self, document: Union[str, bytes],
                     private_key: rsa.RSAPrivateKey) -> Dict[str, str]:
        """
        Sign a document and return signature with metadata.
        
        Args:
            document: Document content (string or bytes)
            private_key: Signer's private key
            
        Returns:
            Dictionary with signature and document hash
        """
        if isinstance(document, str):
            document = document.encode('utf-8')
        
        # Create document hash
        doc_hash = self._hash_service.hash(document)
        
        # Sign document
        sig_data = self.sign(document, private_key)
        
        return {
            'document_hash': base64.b64encode(doc_hash).decode('utf-8'),
            'signature': sig_data.to_dict(),
        }
    
    def verify_document(self, document: Union[str, bytes],
                       signed_doc: Dict[str, Any],
                       public_key: rsa.RSAPublicKey) -> Dict[str, Any]:
        """
        Verify a signed document.
        
        Args:
            document: Document content
            signed_doc: Dictionary from sign_document
            public_key: Signer's public key
            
        Returns:
            Dictionary with verification result and details
        """
        if isinstance(document, str):
            document = document.encode('utf-8')
        
        # Verify document hash
        expected_hash = base64.b64decode(signed_doc['document_hash'])
        actual_hash = self._hash_service.hash(document)
        hash_valid = hmac.compare_digest(expected_hash, actual_hash)
        
        # Verify signature
        sig_data = DigitalSignatureData.from_dict(signed_doc['signature'])
        sig_valid = self.verify(document, sig_data, public_key)
        
        return {
            'valid': hash_valid and sig_valid,
            'hash_valid': hash_valid,
            'signature_valid': sig_valid,
            'algorithm': sig_data.algorithm,
            'hash_algorithm': sig_data.hash_algorithm,
        }
