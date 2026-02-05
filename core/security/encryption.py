"""
Encryption Module - AES, RSA, and Hybrid Encryption Implementation.

This module provides secure encryption services including:
- Symmetric encryption (AES-256 in GCM mode)
- Asymmetric encryption (RSA-2048/4096)
- Hybrid encryption (RSA + AES combined)
- Secure key exchange mechanisms

Security Requirements Covered:
- Key Exchange Mechanism
- Encryption & Decryption (AES, RSA, hybrid approach)

Security Features:
- AES-256-GCM for authenticated encryption
- RSA-2048/4096 for key exchange and asymmetric operations
- Hybrid encryption for large data
- Secure random key generation
- IV/Nonce handling for each encryption
"""

import os
import base64
import secrets
import hashlib
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import logging

logger = logging.getLogger(__name__)


@dataclass
class EncryptedData:
    """Container for encrypted data with metadata."""
    ciphertext: bytes
    iv: bytes  # Initialization Vector / Nonce
    tag: Optional[bytes] = None  # Authentication tag for GCM mode
    algorithm: str = "AES-256-GCM"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary with base64-encoded values."""
        return {
            'ciphertext': base64.b64encode(self.ciphertext).decode('utf-8'),
            'iv': base64.b64encode(self.iv).decode('utf-8'),
            'tag': base64.b64encode(self.tag).decode('utf-8') if self.tag else None,
            'algorithm': self.algorithm,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'EncryptedData':
        """Create from dictionary with base64-encoded values."""
        return cls(
            ciphertext=base64.b64decode(data['ciphertext']),
            iv=base64.b64decode(data['iv']),
            tag=base64.b64decode(data['tag']) if data.get('tag') else None,
            algorithm=data.get('algorithm', 'AES-256-GCM'),
        )


class AESCipher:
    """
    AES-256 encryption in GCM mode.
    
    GCM (Galois/Counter Mode) provides both confidentiality and authenticity.
    This is the recommended mode for modern applications.
    
    Features:
    - 256-bit key (32 bytes)
    - 96-bit IV/nonce (12 bytes)
    - 128-bit authentication tag
    - Authenticated encryption (AEAD)
    
    Example Usage:
        cipher = AESCipher()
        key = cipher.generate_key()
        encrypted = cipher.encrypt(b"secret message", key)
        decrypted = cipher.decrypt(encrypted, key)
    """
    
    KEY_SIZE = 32  # 256 bits
    IV_SIZE = 12   # 96 bits for GCM
    TAG_SIZE = 16  # 128 bits
    
    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically secure random AES key."""
        return secrets.token_bytes(AESCipher.KEY_SIZE)
    
    @staticmethod
    def derive_key(password: str, salt: Optional[bytes] = None, 
                   iterations: int = 100000) -> Tuple[bytes, bytes]:
        """
        Derive an AES key from a password using PBKDF2.
        
        Args:
            password: Password string
            salt: Optional salt (generated if not provided)
            iterations: PBKDF2 iterations (minimum 100,000 recommended)
            
        Returns:
            Tuple of (derived_key, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=AESCipher.KEY_SIZE,
            salt=salt,
            iterations=iterations,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode('utf-8'))
        return key, salt
    
    def encrypt(self, plaintext: bytes, key: bytes) -> EncryptedData:
        """
        Encrypt data using AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
            key: 256-bit encryption key
            
        Returns:
            EncryptedData containing ciphertext, IV, and auth tag
        """
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")
        
        # Generate random IV
        iv = secrets.token_bytes(self.IV_SIZE)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        
        # Encrypt
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        
        logger.debug(f"AES encrypted {len(plaintext)} bytes -> {len(ciphertext)} bytes")
        
        return EncryptedData(
            ciphertext=ciphertext,
            iv=iv,
            tag=encryptor.tag,
            algorithm="AES-256-GCM"
        )
    
    def decrypt(self, encrypted: EncryptedData, key: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM.
        
        Args:
            encrypted: EncryptedData object with ciphertext, IV, and tag
            key: 256-bit encryption key
            
        Returns:
            Decrypted plaintext bytes
            
        Raises:
            ValueError: If decryption or authentication fails
        """
        if len(key) != self.KEY_SIZE:
            raise ValueError(f"Key must be {self.KEY_SIZE} bytes")
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(encrypted.iv, encrypted.tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        plaintext = decryptor.update(encrypted.ciphertext) + decryptor.finalize()
        
        logger.debug(f"AES decrypted {len(encrypted.ciphertext)} bytes -> {len(plaintext)} bytes")
        
        return plaintext
    
    def encrypt_string(self, plaintext: str, key: bytes) -> EncryptedData:
        """Encrypt a string."""
        return self.encrypt(plaintext.encode('utf-8'), key)
    
    def decrypt_string(self, encrypted: EncryptedData, key: bytes) -> str:
        """Decrypt to a string."""
        return self.decrypt(encrypted, key).decode('utf-8')


@dataclass
class RSAKeyPair:
    """Container for RSA key pair."""
    private_key: rsa.RSAPrivateKey
    public_key: rsa.RSAPublicKey
    key_size: int
    
    def get_private_pem(self, password: Optional[str] = None) -> bytes:
        """Export private key as PEM format."""
        encryption = (
            serialization.BestAvailableEncryption(password.encode())
            if password else serialization.NoEncryption()
        )
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption
        )
    
    def get_public_pem(self) -> bytes:
        """Export public key as PEM format."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )


class RSACipher:
    """
    RSA asymmetric encryption.
    
    Features:
    - RSA-2048 or RSA-4096 key sizes
    - OAEP padding with SHA-256
    - Suitable for encrypting small data (like AES keys)
    
    Note: RSA can only encrypt data smaller than the key size minus padding.
    For RSA-2048 with OAEP-SHA256, max plaintext is ~190 bytes.
    Use HybridEncryption for larger data.
    
    Example Usage:
        cipher = RSACipher()
        key_pair = cipher.generate_key_pair()
        encrypted = cipher.encrypt(b"secret", key_pair.public_key)
        decrypted = cipher.decrypt(encrypted, key_pair.private_key)
    """
    
    DEFAULT_KEY_SIZE = 2048
    
    def generate_key_pair(self, key_size: int = DEFAULT_KEY_SIZE) -> RSAKeyPair:
        """
        Generate RSA key pair.
        
        Args:
            key_size: Key size in bits (2048 or 4096 recommended)
            
        Returns:
            RSAKeyPair containing private and public keys
        """
        if key_size < 2048:
            raise ValueError("Key size must be at least 2048 bits for security")
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        logger.info(f"Generated RSA-{key_size} key pair")
        
        return RSAKeyPair(
            private_key=private_key,
            public_key=public_key,
            key_size=key_size
        )
    
    @staticmethod
    def load_private_key(pem_data: bytes, password: Optional[str] = None) -> rsa.RSAPrivateKey:
        """Load private key from PEM format."""
        return serialization.load_pem_private_key(
            pem_data,
            password=password.encode() if password else None,
            backend=default_backend()
        )
    
    @staticmethod
    def load_public_key(pem_data: bytes) -> rsa.RSAPublicKey:
        """Load public key from PEM format."""
        return serialization.load_pem_public_key(
            pem_data,
            backend=default_backend()
        )
    
    def encrypt(self, plaintext: bytes, public_key: rsa.RSAPublicKey) -> bytes:
        """
        Encrypt data using RSA public key.
        
        Uses OAEP padding with SHA-256 for security.
        
        Args:
            plaintext: Data to encrypt (limited by key size)
            public_key: RSA public key
            
        Returns:
            Encrypted ciphertext
        """
        ciphertext = public_key.encrypt(
            plaintext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        logger.debug(f"RSA encrypted {len(plaintext)} bytes -> {len(ciphertext)} bytes")
        
        return ciphertext
    
    def decrypt(self, ciphertext: bytes, private_key: rsa.RSAPrivateKey) -> bytes:
        """
        Decrypt data using RSA private key.
        
        Args:
            ciphertext: Encrypted data
            private_key: RSA private key
            
        Returns:
            Decrypted plaintext
        """
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        
        logger.debug(f"RSA decrypted {len(ciphertext)} bytes -> {len(plaintext)} bytes")
        
        return plaintext


@dataclass
class HybridEncryptedData:
    """Container for hybrid encrypted data."""
    encrypted_key: bytes  # AES key encrypted with RSA
    encrypted_data: EncryptedData  # Data encrypted with AES
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'encrypted_key': base64.b64encode(self.encrypted_key).decode('utf-8'),
            'encrypted_data': self.encrypted_data.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HybridEncryptedData':
        """Create from dictionary."""
        return cls(
            encrypted_key=base64.b64decode(data['encrypted_key']),
            encrypted_data=EncryptedData.from_dict(data['encrypted_data']),
        )


class HybridEncryption:
    """
    Hybrid encryption combining RSA and AES.
    
    This approach:
    1. Generates a random AES session key
    2. Encrypts the data with AES (fast, supports large data)
    3. Encrypts the AES key with RSA (secure key exchange)
    
    This is the recommended approach for encrypting large amounts of data
    securely to a recipient's public key.
    
    Example Usage:
        hybrid = HybridEncryption()
        key_pair = RSACipher().generate_key_pair()
        
        # Encrypt with public key
        encrypted = hybrid.encrypt(b"large data...", key_pair.public_key)
        
        # Decrypt with private key
        decrypted = hybrid.decrypt(encrypted, key_pair.private_key)
    """
    
    def __init__(self):
        self.aes = AESCipher()
        self.rsa = RSACipher()
    
    def encrypt(self, plaintext: bytes, public_key: rsa.RSAPublicKey) -> HybridEncryptedData:
        """
        Encrypt data using hybrid encryption.
        
        Args:
            plaintext: Data to encrypt (any size)
            public_key: Recipient's RSA public key
            
        Returns:
            HybridEncryptedData containing encrypted key and data
        """
        # Generate random AES session key
        session_key = self.aes.generate_key()
        
        # Encrypt data with AES
        encrypted_data = self.aes.encrypt(plaintext, session_key)
        
        # Encrypt AES key with RSA
        encrypted_key = self.rsa.encrypt(session_key, public_key)
        
        logger.info(f"Hybrid encrypted {len(plaintext)} bytes")
        
        return HybridEncryptedData(
            encrypted_key=encrypted_key,
            encrypted_data=encrypted_data
        )
    
    def decrypt(self, encrypted: HybridEncryptedData, 
                private_key: rsa.RSAPrivateKey) -> bytes:
        """
        Decrypt hybrid encrypted data.
        
        Args:
            encrypted: HybridEncryptedData object
            private_key: Recipient's RSA private key
            
        Returns:
            Decrypted plaintext
        """
        # Decrypt AES key with RSA
        session_key = self.rsa.decrypt(encrypted.encrypted_key, private_key)
        
        # Decrypt data with AES
        plaintext = self.aes.decrypt(encrypted.encrypted_data, session_key)
        
        logger.info(f"Hybrid decrypted to {len(plaintext)} bytes")
        
        return plaintext


class KeyExchange:
    """
    Secure key exchange mechanisms.
    
    Provides methods for securely exchanging symmetric keys between parties:
    1. RSA-based key exchange (one party generates, encrypts to recipient)
    2. Diffie-Hellman style key derivation from shared secrets
    
    Example Usage:
        # RSA-based key exchange
        exchange = KeyExchange()
        recipient_keys = exchange.generate_recipient_keys()
        
        # Sender creates and encrypts session key
        session_key, encrypted_key = exchange.create_session_key(recipient_keys.public_key)
        
        # Recipient decrypts session key
        recovered_key = exchange.recover_session_key(encrypted_key, recipient_keys.private_key)
        
        # Both parties now have the same session_key
        assert session_key == recovered_key
    """
    
    def __init__(self):
        self.rsa = RSACipher()
        self.aes = AESCipher()
    
    def generate_recipient_keys(self, key_size: int = 2048) -> RSAKeyPair:
        """
        Generate RSA key pair for a key exchange recipient.
        
        The recipient shares their public key with senders.
        """
        return self.rsa.generate_key_pair(key_size)
    
    def create_session_key(self, recipient_public_key: rsa.RSAPublicKey
                          ) -> Tuple[bytes, bytes]:
        """
        Create a session key and encrypt it for the recipient.
        
        Args:
            recipient_public_key: Recipient's public RSA key
            
        Returns:
            Tuple of (session_key, encrypted_session_key)
        """
        # Generate random session key
        session_key = self.aes.generate_key()
        
        # Encrypt for recipient
        encrypted_key = self.rsa.encrypt(session_key, recipient_public_key)
        
        logger.info("Created and encrypted new session key")
        
        return session_key, encrypted_key
    
    def recover_session_key(self, encrypted_key: bytes,
                           private_key: rsa.RSAPrivateKey) -> bytes:
        """
        Recover a session key that was encrypted to our public key.
        
        Args:
            encrypted_key: RSA-encrypted session key
            private_key: Our RSA private key
            
        Returns:
            Decrypted session key
        """
        session_key = self.rsa.decrypt(encrypted_key, private_key)
        
        logger.info("Recovered session key from encrypted key exchange")
        
        return session_key
    
    def derive_key_from_shared_secret(self, shared_secret: bytes,
                                      salt: Optional[bytes] = None,
                                      info: bytes = b"encryption key") -> bytes:
        """
        Derive an encryption key from a shared secret using HKDF.
        
        This can be used after a Diffie-Hellman exchange or from any
        pre-shared secret.
        
        Args:
            shared_secret: The shared secret (e.g., from DH exchange)
            salt: Optional salt (random bytes recommended)
            info: Context info for key derivation
            
        Returns:
            Derived AES-256 key
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=AESCipher.KEY_SIZE,
            salt=salt,
            info=info,
            backend=default_backend()
        )
        
        key = hkdf.derive(shared_secret)
        
        logger.info("Derived encryption key from shared secret")
        
        return key


class EncryptionService:
    """
    High-level encryption service for application use.
    
    Provides a simple interface for common encryption operations,
    automatically selecting the appropriate algorithm based on use case.
    
    Example Usage:
        service = EncryptionService()
        
        # Encrypt with password
        encrypted = service.encrypt_with_password("sensitive data", "password123")
        decrypted = service.decrypt_with_password(encrypted, "password123")
        
        # Generate keys for a user
        keys = service.generate_user_keys()
        encrypted = service.encrypt_for_recipient(data, keys.public_key)
    """
    
    def __init__(self):
        self.aes = AESCipher()
        self.rsa = RSACipher()
        self.hybrid = HybridEncryption()
        self.key_exchange = KeyExchange()
    
    def encrypt_with_password(self, plaintext: str, password: str,
                              iterations: int = 100000) -> Dict[str, str]:
        """
        Encrypt data using a password.
        
        Derives an AES key from the password using PBKDF2 and encrypts the data.
        
        Args:
            plaintext: String to encrypt
            password: Password to derive key from
            iterations: PBKDF2 iterations
            
        Returns:
            Dictionary with encrypted data and salt (base64 encoded)
        """
        key, salt = self.aes.derive_key(password, iterations=iterations)
        encrypted = self.aes.encrypt_string(plaintext, key)
        
        result = encrypted.to_dict()
        result['salt'] = base64.b64encode(salt).decode('utf-8')
        result['iterations'] = iterations
        
        return result
    
    def decrypt_with_password(self, encrypted_data: Dict[str, str],
                              password: str) -> str:
        """
        Decrypt data that was encrypted with a password.
        
        Args:
            encrypted_data: Dictionary from encrypt_with_password
            password: Password used for encryption
            
        Returns:
            Decrypted string
        """
        salt = base64.b64decode(encrypted_data['salt'])
        iterations = encrypted_data.get('iterations', 100000)
        
        key, _ = self.aes.derive_key(password, salt=salt, iterations=iterations)
        encrypted = EncryptedData.from_dict(encrypted_data)
        
        return self.aes.decrypt_string(encrypted, key)
    
    def generate_user_keys(self, key_size: int = 2048) -> RSAKeyPair:
        """Generate RSA key pair for a user."""
        return self.rsa.generate_key_pair(key_size)
    
    def encrypt_for_recipient(self, plaintext: bytes,
                             recipient_public_key: rsa.RSAPublicKey
                             ) -> Dict[str, Any]:
        """
        Encrypt data for a specific recipient.
        
        Uses hybrid encryption (RSA + AES) for security and efficiency.
        
        Args:
            plaintext: Data to encrypt
            recipient_public_key: Recipient's RSA public key
            
        Returns:
            Dictionary with encrypted data
        """
        encrypted = self.hybrid.encrypt(plaintext, recipient_public_key)
        return encrypted.to_dict()
    
    def decrypt_for_recipient(self, encrypted_data: Dict[str, Any],
                             recipient_private_key: rsa.RSAPrivateKey) -> bytes:
        """
        Decrypt data that was encrypted to our public key.
        
        Args:
            encrypted_data: Dictionary from encrypt_for_recipient
            recipient_private_key: Our RSA private key
            
        Returns:
            Decrypted data
        """
        encrypted = HybridEncryptedData.from_dict(encrypted_data)
        return self.hybrid.decrypt(encrypted, recipient_private_key)
    
    def create_secure_channel(self, recipient_public_key: rsa.RSAPublicKey
                             ) -> Tuple[bytes, bytes]:
        """
        Establish a secure channel with a recipient.
        
        Performs key exchange and returns a shared session key.
        
        Args:
            recipient_public_key: Recipient's RSA public key
            
        Returns:
            Tuple of (session_key, encrypted_key_for_recipient)
        """
        return self.key_exchange.create_session_key(recipient_public_key)
