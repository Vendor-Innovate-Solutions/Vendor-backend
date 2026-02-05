"""
Encoding Module - Base64, QR Code, and Barcode Encoding/Decoding.

This module provides encoding and decoding services including:
- Base64 encoding/decoding (standard and URL-safe)
- QR Code generation
- Barcode generation (Code128, EAN13, etc.)
- Hex encoding/decoding

Security Requirements Covered:
- Encoding & Decoding Implementation (Base64/QR Code/Barcode)
- Security Levels & Risks (documented in docstrings)
- Possible Attacks (documented in docstrings)

Security Considerations:
- Base64 is NOT encryption - it's only encoding for data transport
- QR codes can contain malicious URLs - always validate content
- Never encode sensitive data without encryption first
"""

import base64
import io
import re
from typing import Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Try to import QR and barcode libraries
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    logger.warning("qrcode library not installed - QR code generation unavailable")

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    logger.warning("python-barcode library not installed - barcode generation unavailable")


class QRErrorCorrection(Enum):
    """QR Code error correction levels."""
    LOW = "L"       # ~7% recovery
    MEDIUM = "M"    # ~15% recovery
    QUARTILE = "Q"  # ~25% recovery
    HIGH = "H"      # ~30% recovery


class BarcodeType(Enum):
    """Supported barcode types."""
    CODE128 = "code128"
    CODE39 = "code39"
    EAN13 = "ean13"
    EAN8 = "ean8"
    UPCA = "upca"
    ISBN13 = "isbn13"
    ISBN10 = "isbn10"


@dataclass
class EncodedData:
    """Container for encoded data with metadata."""
    data: str
    encoding: str
    original_length: int
    encoded_length: int
    
    @property
    def overhead_ratio(self) -> float:
        """Calculate encoding overhead."""
        if self.original_length == 0:
            return 0
        return (self.encoded_length - self.original_length) / self.original_length


class Base64Encoder:
    """
    Base64 encoding and decoding service.
    
    Base64 is used to encode binary data as ASCII text for transmission
    over text-based protocols (email, JSON, URLs, etc.).
    
    SECURITY WARNINGS:
    1. Base64 is NOT encryption - data is easily decoded
    2. Never use Base64 alone for sensitive data
    3. Always encrypt sensitive data BEFORE Base64 encoding
    
    Security Risks:
    - Data exposure: Anyone can decode Base64
    - Data tampering: No integrity verification
    - Injection attacks: Decoded data may contain malicious content
    
    Possible Attacks:
    - Data interception: Base64 provides no confidentiality
    - Padding oracle attacks: In some crypto contexts
    - Injection: Malicious content hidden in Base64 data
    
    Example Usage:
        encoder = Base64Encoder()
        
        # Standard Base64
        encoded = encoder.encode(b"Hello, World!")
        decoded = encoder.decode(encoded)
        
        # URL-safe Base64
        encoded_url = encoder.encode_urlsafe(b"data with special chars")
    """
    
    @staticmethod
    def encode(data: bytes) -> str:
        """
        Encode bytes to standard Base64 string.
        
        Args:
            data: Bytes to encode
            
        Returns:
            Base64 encoded string
        """
        encoded = base64.b64encode(data).decode('ascii')
        logger.debug(f"Base64 encoded {len(data)} bytes -> {len(encoded)} chars")
        return encoded
    
    @staticmethod
    def decode(encoded: str) -> bytes:
        """
        Decode Base64 string to bytes.
        
        Args:
            encoded: Base64 encoded string
            
        Returns:
            Decoded bytes
            
        Raises:
            ValueError: If input is not valid Base64
        """
        try:
            # Handle both with and without padding
            # Add padding if missing
            padding = 4 - (len(encoded) % 4)
            if padding != 4:
                encoded += '=' * padding
            
            decoded = base64.b64decode(encoded)
            logger.debug(f"Base64 decoded {len(encoded)} chars -> {len(decoded)} bytes")
            return decoded
        except Exception as e:
            raise ValueError(f"Invalid Base64 data: {e}")
    
    @staticmethod
    def encode_urlsafe(data: bytes) -> str:
        """
        Encode bytes to URL-safe Base64 string.
        
        URL-safe Base64 uses '-' instead of '+' and '_' instead of '/'
        so the encoded data can be used in URLs without escaping.
        
        Args:
            data: Bytes to encode
            
        Returns:
            URL-safe Base64 encoded string (without padding)
        """
        # Remove padding for URL usage
        return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')
    
    @staticmethod
    def decode_urlsafe(encoded: str) -> bytes:
        """
        Decode URL-safe Base64 string to bytes.
        
        Args:
            encoded: URL-safe Base64 encoded string
            
        Returns:
            Decoded bytes
        """
        # Add padding back
        padding = 4 - (len(encoded) % 4)
        if padding != 4:
            encoded += '=' * padding
        
        return base64.urlsafe_b64decode(encoded)
    
    @staticmethod
    def encode_string(text: str, encoding: str = 'utf-8') -> str:
        """Encode a string to Base64."""
        return Base64Encoder.encode(text.encode(encoding))
    
    @staticmethod
    def decode_string(encoded: str, encoding: str = 'utf-8') -> str:
        """Decode Base64 to a string."""
        return Base64Encoder.decode(encoded).decode(encoding)
    
    @staticmethod
    def is_valid_base64(data: str) -> bool:
        """
        Check if a string is valid Base64.
        
        Args:
            data: String to check
            
        Returns:
            True if valid Base64
        """
        # Base64 pattern: A-Z, a-z, 0-9, +, /, with optional = padding
        pattern = r'^[A-Za-z0-9+/]*={0,2}$'
        
        if not re.match(pattern, data):
            return False
        
        try:
            base64.b64decode(data)
            return True
        except Exception:
            return False
    
    def encode_with_metadata(self, data: bytes) -> EncodedData:
        """
        Encode data and return with metadata.
        
        Useful for tracking encoding overhead.
        """
        encoded = self.encode(data)
        return EncodedData(
            data=encoded,
            encoding="base64",
            original_length=len(data),
            encoded_length=len(encoded),
        )


class HexEncoder:
    """
    Hexadecimal encoding service.
    
    Hex encoding converts each byte to two hexadecimal characters.
    Useful for displaying binary data and cryptographic values.
    """
    
    @staticmethod
    def encode(data: bytes) -> str:
        """Encode bytes to hex string."""
        return data.hex()
    
    @staticmethod
    def decode(encoded: str) -> bytes:
        """Decode hex string to bytes."""
        return bytes.fromhex(encoded)
    
    @staticmethod
    def is_valid_hex(data: str) -> bool:
        """Check if string is valid hex."""
        try:
            bytes.fromhex(data)
            return True
        except ValueError:
            return False


class QRCodeGenerator:
    """
    QR Code generation service.
    
    QR Codes can encode text, URLs, contact info, and more.
    They include error correction for partial damage recovery.
    
    SECURITY WARNINGS:
    1. QR codes can contain malicious URLs - validate before following
    2. QR codes can encode commands for apps - sanitize content
    3. Consider the sensitivity of data before encoding
    
    Security Risks:
    - Phishing: QR codes can redirect to fake sites
    - Malware: URLs can download malicious content
    - Social engineering: Trust in QR codes can be exploited
    
    Possible Attacks:
    - QRLjacking: Hijacking QR login codes
    - URL replacement: Covering legitimate QR with malicious one
    - Data exfiltration: Encoding sensitive data in QR for theft
    
    Example Usage:
        generator = QRCodeGenerator()
        
        # Generate QR code
        qr_bytes = generator.generate("https://example.com")
        
        # Save to file
        generator.save("https://example.com", "qrcode.png")
        
        # Get as base64 for web embedding
        qr_base64 = generator.generate_base64("data")
    """
    
    def __init__(self):
        if not QRCODE_AVAILABLE:
            raise ImportError("qrcode library is required. Install with: pip install qrcode[pil]")
    
    def generate(self, data: str,
                error_correction: QRErrorCorrection = QRErrorCorrection.MEDIUM,
                box_size: int = 10,
                border: int = 4,
                fill_color: str = "black",
                back_color: str = "white") -> bytes:
        """
        Generate QR code as PNG bytes.
        
        Args:
            data: Data to encode in QR code
            error_correction: Error correction level
            box_size: Size of each box in pixels
            border: Border width in boxes
            fill_color: QR code color
            back_color: Background color
            
        Returns:
            PNG image as bytes
        """
        # Map error correction
        ec_map = {
            QRErrorCorrection.LOW: ERROR_CORRECT_L,
            QRErrorCorrection.MEDIUM: ERROR_CORRECT_M,
            QRErrorCorrection.QUARTILE: ERROR_CORRECT_Q,
            QRErrorCorrection.HIGH: ERROR_CORRECT_H,
        }
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=ec_map[error_correction],
            box_size=box_size,
            border=border,
        )
        
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color=fill_color, back_color=back_color)
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        logger.info(f"Generated QR code for {len(data)} chars of data")
        
        return buffer.read()
    
    def generate_base64(self, data: str, **kwargs) -> str:
        """
        Generate QR code as base64-encoded PNG.
        
        Useful for embedding in HTML/CSS:
        <img src="data:image/png;base64,{base64_data}">
        
        Args:
            data: Data to encode
            **kwargs: Additional arguments for generate()
            
        Returns:
            Base64 encoded PNG
        """
        qr_bytes = self.generate(data, **kwargs)
        return base64.b64encode(qr_bytes).decode('ascii')
    
    def generate_data_uri(self, data: str, **kwargs) -> str:
        """
        Generate QR code as data URI for HTML embedding.
        
        Args:
            data: Data to encode
            **kwargs: Additional arguments for generate()
            
        Returns:
            Data URI string
        """
        base64_data = self.generate_base64(data, **kwargs)
        return f"data:image/png;base64,{base64_data}"
    
    def save(self, data: str, filepath: str, **kwargs) -> None:
        """
        Generate and save QR code to file.
        
        Args:
            data: Data to encode
            filepath: Path to save image
            **kwargs: Additional arguments for generate()
        """
        qr_bytes = self.generate(data, **kwargs)
        
        with open(filepath, 'wb') as f:
            f.write(qr_bytes)
        
        logger.info(f"Saved QR code to {filepath}")


class BarcodeGenerator:
    """
    Barcode generation service.
    
    Supports various barcode formats for product identification,
    inventory management, and more.
    
    SECURITY CONSIDERATIONS:
    - Barcodes can be forged easily
    - Always verify barcode data against backend systems
    - Don't rely on barcodes alone for authentication
    
    Example Usage:
        generator = BarcodeGenerator()
        
        # Generate Code128 barcode
        barcode_bytes = generator.generate("PRODUCT123", BarcodeType.CODE128)
        
        # Generate EAN-13 barcode
        ean_bytes = generator.generate("5901234123457", BarcodeType.EAN13)
    """
    
    def __init__(self):
        if not BARCODE_AVAILABLE:
            raise ImportError(
                "python-barcode library is required. "
                "Install with: pip install python-barcode[images]"
            )
    
    def generate(self, data: str, barcode_type: BarcodeType = BarcodeType.CODE128,
                options: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Generate barcode as PNG bytes.
        
        Args:
            data: Data to encode
            barcode_type: Type of barcode to generate
            options: Additional barcode options
            
        Returns:
            PNG image as bytes
        """
        # Get barcode class
        barcode_class = barcode.get_barcode_class(barcode_type.value)
        
        # Create barcode with image writer
        buffer = io.BytesIO()
        
        bc = barcode_class(data, writer=ImageWriter())
        bc.write(buffer, options=options or {})
        
        buffer.seek(0)
        
        logger.info(f"Generated {barcode_type.value} barcode for: {data}")
        
        return buffer.read()
    
    def generate_base64(self, data: str,
                       barcode_type: BarcodeType = BarcodeType.CODE128,
                       options: Optional[Dict[str, Any]] = None) -> str:
        """Generate barcode as base64-encoded PNG."""
        bc_bytes = self.generate(data, barcode_type, options)
        return base64.b64encode(bc_bytes).decode('ascii')
    
    def save(self, data: str, filepath: str,
            barcode_type: BarcodeType = BarcodeType.CODE128,
            options: Optional[Dict[str, Any]] = None) -> None:
        """Generate and save barcode to file."""
        bc_bytes = self.generate(data, barcode_type, options)
        
        with open(filepath, 'wb') as f:
            f.write(bc_bytes)
        
        logger.info(f"Saved barcode to {filepath}")
    
    @staticmethod
    def validate_ean13(data: str) -> Tuple[bool, str]:
        """
        Validate EAN-13 barcode checksum.
        
        Args:
            data: 13-digit EAN code
            
        Returns:
            Tuple of (is_valid, message)
        """
        if len(data) != 13 or not data.isdigit():
            return False, "EAN-13 must be exactly 13 digits"
        
        # Calculate checksum
        odd_sum = sum(int(data[i]) for i in range(0, 12, 2))
        even_sum = sum(int(data[i]) for i in range(1, 12, 2))
        checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
        
        if checksum == int(data[12]):
            return True, "Valid EAN-13"
        else:
            return False, f"Invalid checksum: expected {checksum}, got {data[12]}"


class EncodingService:
    """
    High-level encoding service combining all encoding methods.
    
    Provides a unified interface for various encoding needs.
    
    SECURITY BEST PRACTICES:
    1. Always encrypt sensitive data BEFORE encoding
    2. Validate decoded data before processing
    3. Use URL-safe encoding for URLs and filenames
    4. Add integrity checks (HMAC) for important data
    
    Example Usage:
        service = EncodingService()
        
        # Base64 operations
        encoded = service.base64_encode(b"data")
        decoded = service.base64_decode(encoded)
        
        # Generate QR code (if available)
        qr = service.generate_qr_code("https://example.com")
        
        # Generate barcode (if available)
        bc = service.generate_barcode("PRODUCT123")
    """
    
    def __init__(self):
        self.base64 = Base64Encoder()
        self.hex = HexEncoder()
        
        # Optional components
        self._qr: Optional[QRCodeGenerator] = None
        self._barcode: Optional[BarcodeGenerator] = None
    
    @property
    def qr(self) -> QRCodeGenerator:
        """Get QR code generator (lazy initialization)."""
        if self._qr is None:
            self._qr = QRCodeGenerator()
        return self._qr
    
    @property
    def barcode(self) -> BarcodeGenerator:
        """Get barcode generator (lazy initialization)."""
        if self._barcode is None:
            self._barcode = BarcodeGenerator()
        return self._barcode
    
    # Base64 methods
    def base64_encode(self, data: Union[bytes, str]) -> str:
        """Encode to Base64."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self.base64.encode(data)
    
    def base64_decode(self, encoded: str) -> bytes:
        """Decode from Base64."""
        return self.base64.decode(encoded)
    
    def base64_encode_urlsafe(self, data: Union[bytes, str]) -> str:
        """Encode to URL-safe Base64."""
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self.base64.encode_urlsafe(data)
    
    def base64_decode_urlsafe(self, encoded: str) -> bytes:
        """Decode from URL-safe Base64."""
        return self.base64.decode_urlsafe(encoded)
    
    # Hex methods
    def hex_encode(self, data: bytes) -> str:
        """Encode to hex."""
        return self.hex.encode(data)
    
    def hex_decode(self, encoded: str) -> bytes:
        """Decode from hex."""
        return self.hex.decode(encoded)
    
    # QR Code methods
    def generate_qr_code(self, data: str, **kwargs) -> bytes:
        """Generate QR code PNG."""
        return self.qr.generate(data, **kwargs)
    
    def generate_qr_code_base64(self, data: str, **kwargs) -> str:
        """Generate QR code as Base64."""
        return self.qr.generate_base64(data, **kwargs)
    
    def generate_qr_code_data_uri(self, data: str, **kwargs) -> str:
        """Generate QR code as data URI."""
        return self.qr.generate_data_uri(data, **kwargs)
    
    # Barcode methods
    def generate_barcode(self, data: str,
                        barcode_type: BarcodeType = BarcodeType.CODE128,
                        **kwargs) -> bytes:
        """Generate barcode PNG."""
        return self.barcode.generate(data, barcode_type, **kwargs)
    
    def generate_barcode_base64(self, data: str,
                               barcode_type: BarcodeType = BarcodeType.CODE128,
                               **kwargs) -> str:
        """Generate barcode as Base64."""
        return self.barcode.generate_base64(data, barcode_type, **kwargs)
    
    # Utility methods
    def is_qr_available(self) -> bool:
        """Check if QR code generation is available."""
        return QRCODE_AVAILABLE
    
    def is_barcode_available(self) -> bool:
        """Check if barcode generation is available."""
        return BARCODE_AVAILABLE
    
    def secure_encode(self, data: bytes, include_checksum: bool = True) -> str:
        """
        Encode data with optional integrity checksum.
        
        If include_checksum is True, appends a SHA-256 hash for
        integrity verification on decode.
        
        Args:
            data: Data to encode
            include_checksum: Add integrity checksum
            
        Returns:
            Encoded string with optional checksum
        """
        import hashlib
        
        if include_checksum:
            checksum = hashlib.sha256(data).digest()[:8]  # 64-bit checksum
            data = data + checksum
        
        return self.base64.encode(data)
    
    def secure_decode(self, encoded: str, verify_checksum: bool = True) -> bytes:
        """
        Decode data and optionally verify integrity.
        
        Args:
            encoded: Encoded string from secure_encode
            verify_checksum: Verify integrity checksum
            
        Returns:
            Original data
            
        Raises:
            ValueError: If checksum verification fails
        """
        import hashlib
        
        data = self.base64.decode(encoded)
        
        if verify_checksum:
            if len(data) < 8:
                raise ValueError("Data too short for checksum")
            
            original_data = data[:-8]
            stored_checksum = data[-8:]
            computed_checksum = hashlib.sha256(original_data).digest()[:8]
            
            if stored_checksum != computed_checksum:
                raise ValueError("Checksum verification failed - data may be corrupted")
            
            return original_data
        
        return data
