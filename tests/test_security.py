"""
Tests for the core security module.

Tests cover:
- Access Control List and Matrix
- AES and RSA Encryption
- Hybrid Encryption
- Key Exchange
- Password Hashing with Salt
- Digital Signatures
- HMAC
- Base64 Encoding
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAccessControl:
    """Tests for Access Control List and Matrix."""
    
    def test_permission_comparison(self):
        """Test permission level comparisons."""
        from core.security.acl import Permission
        
        assert Permission.ADMIN > Permission.WRITE
        assert Permission.WRITE > Permission.READ
        assert Permission.READ > Permission.NONE
        assert Permission.ADMIN >= Permission.ADMIN
        assert Permission.READ <= Permission.WRITE
    
    def test_acl_grant_and_check(self):
        """Test granting and checking permissions in ACL."""
        from core.security.acl import AccessControlList, ResourceType, Permission
        
        acl = AccessControlList()
        
        # Grant permission
        acl.grant(
            subject="role:ADMIN",
            resource_type=ResourceType.INVOICE,
            permission=Permission.WRITE,
            justification="Admin write access"
        )
        
        # Check permission - should pass
        assert acl.check_permission(
            "role:ADMIN", 
            ResourceType.INVOICE, 
            Permission.WRITE
        )
        
        # Check lower permission - should also pass
        assert acl.check_permission(
            "role:ADMIN", 
            ResourceType.INVOICE, 
            Permission.READ
        )
        
        # Check higher permission - should fail
        assert not acl.check_permission(
            "role:ADMIN", 
            ResourceType.INVOICE, 
            Permission.ADMIN
        )
    
    def test_acl_revoke(self):
        """Test revoking permissions."""
        from core.security.acl import AccessControlList, ResourceType, Permission
        
        acl = AccessControlList()
        
        # Grant and then revoke
        acl.grant("user:john", ResourceType.VOUCHER, Permission.READ)
        assert acl.check_permission("user:john", ResourceType.VOUCHER, Permission.READ)
        
        acl.revoke("user:john", ResourceType.VOUCHER)
        assert not acl.check_permission("user:john", ResourceType.VOUCHER, Permission.READ)
    
    def test_access_control_matrix_default_permissions(self):
        """Test default ACM permissions."""
        from core.security.acl import AccessControlMatrix, ResourceType, Permission
        
        acm = AccessControlMatrix()
        
        # OWNER should have ADMIN on everything
        assert acm.check_access("OWNER", ResourceType.INVOICE, Permission.ADMIN)
        assert acm.check_access("OWNER", ResourceType.VOUCHER, Permission.ADMIN)
        assert acm.check_access("OWNER", ResourceType.LEDGER, Permission.ADMIN)
        
        # ACCOUNTANT should have WRITE on financial resources
        assert acm.check_access("ACCOUNTANT", ResourceType.INVOICE, Permission.WRITE)
        assert acm.check_access("ACCOUNTANT", ResourceType.VOUCHER, Permission.WRITE)
        assert acm.check_access("ACCOUNTANT", ResourceType.LEDGER, Permission.WRITE)
        
        # ACCOUNTANT should NOT have access to users
        assert not acm.check_access("ACCOUNTANT", ResourceType.USER, Permission.READ)
        
        # VIEWER should only have READ
        assert acm.check_access("VIEWER", ResourceType.INVOICE, Permission.READ)
        assert not acm.check_access("VIEWER", ResourceType.INVOICE, Permission.WRITE)
    
    def test_access_control_matrix_print(self):
        """Test printing the access control matrix."""
        from core.security.acl import AccessControlMatrix
        
        acm = AccessControlMatrix()
        matrix_str = acm.print_matrix()
        
        assert "OWNER" in matrix_str
        assert "ADMIN" in matrix_str
        assert "ACCOUNTANT" in matrix_str
    
    def test_policy_justification(self):
        """Test policy justifications are defined."""
        from core.security.acl import AccessControlMatrix
        
        acm = AccessControlMatrix()
        
        assert "full administrative" in acm.get_policy_justification("OWNER").lower()
        assert "financial" in acm.get_policy_justification("ACCOUNTANT").lower()
        assert "read-only" in acm.get_policy_justification("VIEWER").lower()


class TestAESEncryption:
    """Tests for AES encryption."""
    
    def test_key_generation(self):
        """Test AES key generation."""
        from core.security.encryption import AESCipher
        
        cipher = AESCipher()
        key = cipher.generate_key()
        
        assert len(key) == 32  # 256 bits
        
        # Keys should be different each time
        key2 = cipher.generate_key()
        assert key != key2
    
    def test_encrypt_decrypt(self):
        """Test AES encryption and decryption."""
        from core.security.encryption import AESCipher
        
        cipher = AESCipher()
        key = cipher.generate_key()
        
        plaintext = b"This is a secret message!"
        encrypted = cipher.encrypt(plaintext, key)
        decrypted = cipher.decrypt(encrypted, key)
        
        assert decrypted == plaintext
        assert encrypted.ciphertext != plaintext
    
    def test_encrypt_string(self):
        """Test string encryption."""
        from core.security.encryption import AESCipher
        
        cipher = AESCipher()
        key = cipher.generate_key()
        
        plaintext = "Hello, World! 🔐"
        encrypted = cipher.encrypt_string(plaintext, key)
        decrypted = cipher.decrypt_string(encrypted, key)
        
        assert decrypted == plaintext
    
    def test_key_derivation(self):
        """Test key derivation from password."""
        from core.security.encryption import AESCipher
        
        cipher = AESCipher()
        
        key1, salt1 = cipher.derive_key("password123")
        key2, _ = cipher.derive_key("password123", salt=salt1)
        
        # Same password and salt should produce same key
        assert key1 == key2
        
        # Different password should produce different key
        key3, _ = cipher.derive_key("different_password", salt=salt1)
        assert key1 != key3
    
    def test_different_iv_each_encryption(self):
        """Test that each encryption uses a different IV."""
        from core.security.encryption import AESCipher
        
        cipher = AESCipher()
        key = cipher.generate_key()
        plaintext = b"Same message"
        
        encrypted1 = cipher.encrypt(plaintext, key)
        encrypted2 = cipher.encrypt(plaintext, key)
        
        # IVs should be different
        assert encrypted1.iv != encrypted2.iv
        # Ciphertexts should be different
        assert encrypted1.ciphertext != encrypted2.ciphertext


class TestRSAEncryption:
    """Tests for RSA encryption."""
    
    def test_key_generation(self):
        """Test RSA key pair generation."""
        from core.security.encryption import RSACipher
        
        cipher = RSACipher()
        key_pair = cipher.generate_key_pair(key_size=2048)
        
        assert key_pair.key_size == 2048
        assert key_pair.private_key is not None
        assert key_pair.public_key is not None
    
    def test_encrypt_decrypt(self):
        """Test RSA encryption and decryption."""
        from core.security.encryption import RSACipher
        
        cipher = RSACipher()
        key_pair = cipher.generate_key_pair()
        
        plaintext = b"Short secret"
        encrypted = cipher.encrypt(plaintext, key_pair.public_key)
        decrypted = cipher.decrypt(encrypted, key_pair.private_key)
        
        assert decrypted == plaintext
    
    def test_key_export(self):
        """Test key export to PEM format."""
        from core.security.encryption import RSACipher
        
        cipher = RSACipher()
        key_pair = cipher.generate_key_pair()
        
        public_pem = key_pair.get_public_pem()
        private_pem = key_pair.get_private_pem()
        
        assert b"BEGIN PUBLIC KEY" in public_pem
        assert b"BEGIN PRIVATE KEY" in private_pem
    
    def test_key_load(self):
        """Test loading keys from PEM."""
        from core.security.encryption import RSACipher
        
        cipher = RSACipher()
        key_pair = cipher.generate_key_pair()
        
        # Export and reload
        public_pem = key_pair.get_public_pem()
        private_pem = key_pair.get_private_pem()
        
        loaded_public = cipher.load_public_key(public_pem)
        loaded_private = cipher.load_private_key(private_pem)
        
        # Encrypt with loaded public, decrypt with loaded private
        plaintext = b"Test message"
        encrypted = cipher.encrypt(plaintext, loaded_public)
        decrypted = cipher.decrypt(encrypted, loaded_private)
        
        assert decrypted == plaintext


class TestHybridEncryption:
    """Tests for hybrid encryption."""
    
    def test_encrypt_large_data(self):
        """Test encrypting large data with hybrid encryption."""
        from core.security.encryption import HybridEncryption, RSACipher
        
        hybrid = HybridEncryption()
        key_pair = RSACipher().generate_key_pair()
        
        # Large data (100KB)
        large_data = b"x" * 100000
        
        encrypted = hybrid.encrypt(large_data, key_pair.public_key)
        decrypted = hybrid.decrypt(encrypted, key_pair.private_key)
        
        assert decrypted == large_data
    
    def test_serialization(self):
        """Test serialization of encrypted data."""
        from core.security.encryption import HybridEncryption, RSACipher, HybridEncryptedData
        
        hybrid = HybridEncryption()
        key_pair = RSACipher().generate_key_pair()
        
        plaintext = b"Serialization test"
        encrypted = hybrid.encrypt(plaintext, key_pair.public_key)
        
        # Serialize and deserialize
        data_dict = encrypted.to_dict()
        restored = HybridEncryptedData.from_dict(data_dict)
        
        decrypted = hybrid.decrypt(restored, key_pair.private_key)
        assert decrypted == plaintext


class TestKeyExchange:
    """Tests for key exchange mechanism."""
    
    def test_key_exchange_flow(self):
        """Test complete key exchange flow."""
        from core.security.encryption import KeyExchange
        
        exchange = KeyExchange()
        
        # Recipient generates keys
        recipient_keys = exchange.generate_recipient_keys()
        
        # Sender creates and encrypts session key
        session_key, encrypted_key = exchange.create_session_key(recipient_keys.public_key)
        
        # Recipient recovers session key
        recovered_key = exchange.recover_session_key(encrypted_key, recipient_keys.private_key)
        
        # Both should have the same key
        assert session_key == recovered_key
    
    def test_key_derivation_from_secret(self):
        """Test deriving key from shared secret."""
        from core.security.encryption import KeyExchange
        
        exchange = KeyExchange()
        
        shared_secret = b"shared_secret_between_parties"
        salt = b"random_salt_value"
        
        key1 = exchange.derive_key_from_shared_secret(shared_secret, salt=salt)
        key2 = exchange.derive_key_from_shared_secret(shared_secret, salt=salt)
        
        assert key1 == key2
        assert len(key1) == 32  # AES-256 key


class TestPasswordHashing:
    """Tests for password hashing with salt."""
    
    def test_hash_and_verify(self):
        """Test password hashing and verification."""
        from core.security.hashing import PasswordHasher
        
        hasher = PasswordHasher(use_argon2=False)  # Use PBKDF2 for testing
        
        password = "secure_password_123!"
        hashed = hasher.hash(password)
        
        # Correct password should verify
        assert hasher.verify(password, hashed)
        
        # Wrong password should not verify
        assert not hasher.verify("wrong_password", hashed)
    
    def test_hash_includes_salt(self):
        """Test that hash includes unique salt."""
        from core.security.hashing import PasswordHasher
        
        hasher = PasswordHasher(use_argon2=False)
        
        password = "same_password"
        hash1 = hasher.hash(password)
        hash2 = hasher.hash(password)
        
        # Same password should produce different hashes (different salts)
        assert hash1 != hash2
        
        # But both should verify
        assert hasher.verify(password, hash1)
        assert hasher.verify(password, hash2)
    
    def test_hash_format(self):
        """Test that hash is in expected format."""
        from core.security.hashing import PasswordHasher
        
        hasher = PasswordHasher(use_argon2=False)
        hashed = hasher.hash("password")
        
        # Should be PBKDF2 format
        assert hashed.startswith("$pbkdf2-sha256$")


class TestHashing:
    """Tests for general hashing service."""
    
    def test_hash_with_salt(self):
        """Test hashing with salt."""
        from core.security.hashing import HashingService, HashAlgorithm
        
        hasher = HashingService(HashAlgorithm.SHA256)
        
        data = b"data to hash"
        hashed = hasher.hash_with_salt(data)
        
        assert hashed.salt is not None
        assert len(hashed.salt) == 16  # Default salt length
        assert hashed.algorithm == "sha256"
    
    def test_verify_hash(self):
        """Test hash verification."""
        from core.security.hashing import HashingService
        
        hasher = HashingService()
        
        data = b"verify this data"
        hashed = hasher.hash_with_salt(data)
        
        assert hasher.verify_hash(data, hashed)
        assert not hasher.verify_hash(b"different data", hashed)
    
    def test_different_algorithms(self):
        """Test different hash algorithms."""
        from core.security.hashing import HashingService, HashAlgorithm
        
        data = b"test data"
        
        sha256_hash = HashingService(HashAlgorithm.SHA256).hash(data)
        sha512_hash = HashingService(HashAlgorithm.SHA512).hash(data)
        
        assert len(sha256_hash) == 32  # 256 bits
        assert len(sha512_hash) == 64  # 512 bits


class TestHMAC:
    """Tests for HMAC service."""
    
    def test_create_and_verify_mac(self):
        """Test creating and verifying MAC."""
        from core.security.hashing import HMACService
        
        hmac_service = HMACService()
        key = hmac_service.generate_key()
        message = b"Authenticate this message"
        
        mac = hmac_service.create_mac(message, key)
        
        assert hmac_service.verify_mac(message, mac, key)
        assert not hmac_service.verify_mac(b"Different message", mac, key)
    
    def test_sign_data(self):
        """Test signing and verifying structured data."""
        from core.security.hashing import HMACService
        
        hmac_service = HMACService()
        key = hmac_service.generate_key()
        
        data = {"user_id": 123, "action": "login", "timestamp": 1234567890}
        signed = hmac_service.sign_data(data, key)
        
        # Verify and decode
        recovered = hmac_service.verify_signed_data(signed, key)
        assert recovered == data
        
        # Tampered data should fail
        tampered = signed.replace("login", "admin")
        assert hmac_service.verify_signed_data(tampered, key) is None


class TestDigitalSignature:
    """Tests for digital signatures."""
    
    def test_sign_and_verify(self):
        """Test signing and verifying messages."""
        from core.security.hashing import DigitalSignature
        from core.security.encryption import RSACipher
        
        signer = DigitalSignature()
        key_pair = RSACipher().generate_key_pair()
        
        message = b"Important document content"
        signature = signer.sign(message, key_pair.private_key)
        
        # Valid signature should verify
        assert signer.verify(message, signature, key_pair.public_key)
        
        # Modified message should not verify
        assert not signer.verify(b"Modified content", signature, key_pair.public_key)
    
    def test_sign_document(self):
        """Test document signing with metadata."""
        from core.security.hashing import DigitalSignature
        from core.security.encryption import RSACipher
        
        signer = DigitalSignature()
        key_pair = RSACipher().generate_key_pair()
        
        document = "Contract document content..."
        signed = signer.sign_document(document, key_pair.private_key)
        
        assert "document_hash" in signed
        assert "signature" in signed
        
        # Verify document
        result = signer.verify_document(document, signed, key_pair.public_key)
        assert result["valid"]
        assert result["hash_valid"]
        assert result["signature_valid"]


class TestBase64Encoding:
    """Tests for Base64 encoding."""
    
    def test_encode_decode(self):
        """Test basic encode and decode."""
        from core.security.encoding import Base64Encoder
        
        encoder = Base64Encoder()
        
        data = b"Hello, World!"
        encoded = encoder.encode(data)
        decoded = encoder.decode(encoded)
        
        assert decoded == data
        assert encoded == "SGVsbG8sIFdvcmxkIQ=="
    
    def test_urlsafe_encoding(self):
        """Test URL-safe Base64 encoding."""
        from core.security.encoding import Base64Encoder
        
        encoder = Base64Encoder()
        
        # Data that would have + and / in standard Base64
        data = b"\xfb\xff\xfe"
        
        urlsafe = encoder.encode_urlsafe(data)
        standard = encoder.encode(data)
        
        # URL-safe should not have + or /
        assert "+" not in urlsafe
        assert "/" not in urlsafe
        
        # Should decode correctly
        assert encoder.decode_urlsafe(urlsafe) == data
    
    def test_string_encoding(self):
        """Test string convenience methods."""
        from core.security.encoding import Base64Encoder
        
        encoder = Base64Encoder()
        
        text = "Unicode text: 你好世界 🌍"
        encoded = encoder.encode_string(text)
        decoded = encoder.decode_string(encoded)
        
        assert decoded == text
    
    def test_validation(self):
        """Test Base64 validation."""
        from core.security.encoding import Base64Encoder
        
        encoder = Base64Encoder()
        
        assert encoder.is_valid_base64("SGVsbG8=")
        assert encoder.is_valid_base64("YWJjZGVm")
        assert not encoder.is_valid_base64("Invalid!!!")
        assert not encoder.is_valid_base64("Has spaces ")


class TestEncodingService:
    """Tests for high-level encoding service."""
    
    def test_secure_encode_with_checksum(self):
        """Test encoding with integrity checksum."""
        from core.security.encoding import EncodingService
        
        service = EncodingService()
        
        data = b"Important data that needs integrity"
        
        # Encode with checksum
        encoded = service.secure_encode(data, include_checksum=True)
        
        # Decode and verify
        decoded = service.secure_decode(encoded, verify_checksum=True)
        assert decoded == data
    
    def test_secure_decode_detects_corruption(self):
        """Test that corrupted data is detected."""
        from core.security.encoding import EncodingService
        import base64
        
        service = EncodingService()
        
        data = b"Original data"
        encoded = service.secure_encode(data, include_checksum=True)
        
        # Corrupt the encoded data
        decoded_bytes = base64.b64decode(encoded)
        corrupted_bytes = bytes([decoded_bytes[0] ^ 0xFF]) + decoded_bytes[1:]
        corrupted = base64.b64encode(corrupted_bytes).decode()
        
        # Should raise error
        with pytest.raises(ValueError, match="Checksum verification failed"):
            service.secure_decode(corrupted, verify_checksum=True)


class TestIntegration:
    """Integration tests combining multiple security features."""
    
    def test_secure_message_flow(self):
        """Test complete secure message flow."""
        from core.security.encryption import EncryptionService
        from core.security.hashing import DigitalSignature, PasswordHasher
        from core.security.encoding import EncodingService
        
        encryption = EncryptionService()
        signer = DigitalSignature()
        encoder = EncodingService()
        
        # Generate sender's keys
        sender_keys = encryption.generate_user_keys()
        # Generate recipient's keys
        recipient_keys = encryption.generate_user_keys()
        
        # Create message
        message = "Secret message that needs encryption and signing"
        
        # 1. Sign the message
        signature = signer.sign(message.encode(), sender_keys.private_key)
        
        # 2. Encrypt for recipient
        encrypted = encryption.encrypt_for_recipient(
            message.encode(), 
            recipient_keys.public_key
        )
        
        # 3. Recipient decrypts
        decrypted = encryption.decrypt_for_recipient(
            encrypted, 
            recipient_keys.private_key
        )
        
        # 4. Verify signature
        is_valid = signer.verify(decrypted, signature, sender_keys.public_key)
        
        assert decrypted.decode() == message
        assert is_valid
    
    def test_access_control_with_encryption(self):
        """Test combining ACL with encryption."""
        from core.security.acl import AccessControlMatrix, ResourceType, Permission
        from core.security.encryption import EncryptionService
        
        acm = AccessControlMatrix()
        encryption = EncryptionService()
        
        # Sensitive data
        sensitive_data = "Financial report data"
        
        # Check access before decryption
        if acm.check_access("ACCOUNTANT", ResourceType.REPORT, Permission.READ):
            # Encrypt for storage
            encrypted = encryption.encrypt_with_password(
                sensitive_data, 
                "secure_key_123"
            )
            
            # Decrypt for authorized access
            decrypted = encryption.decrypt_with_password(
                encrypted, 
                "secure_key_123"
            )
            
            assert decrypted == sensitive_data
        
        # Viewer should also have READ access to reports
        assert acm.check_access("VIEWER", ResourceType.REPORT, Permission.READ)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
