"""
P1 Fix #42: Encryption Service
Provides secure encryption/decryption for sensitive data like API keys.
"""

import base64
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Fernet for secure encryption
try:
    from cryptography.fernet import Fernet

    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    logger.warning(
        "cryptography package not found. Data will be stored as base64 (UNSECURE)."
    )


class EncryptionService:
    @staticmethod
    def _get_fernet():
        """Get Fernet instance using master key"""
        if not _FERNET_AVAILABLE:
            raise ImportError(
                "cryptography package is required for secure encryption. Please install with `pip install cryptography`."
            )
        try:
            return Fernet(settings.ENCRYPTION_KEY.encode())
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            raise ValueError(
                f"Invalid ENCRYPTION_KEY or Fernet initialization error: {e}"
            )

    @staticmethod
    def encrypt(data: str) -> str:
        """Encrypt a string to a secure representation"""
        if not data:
            return ""

        # P0 Security Fix: Enforce strong encryption, no base64 fallback
        fernet = EncryptionService._get_fernet()
        return fernet.encrypt(data.encode()).decode()

    @staticmethod
    def decrypt(encrypted_data: str) -> str:
        """Decrypt an encrypted string"""
        if not encrypted_data:
            return ""

        if encrypted_data.startswith("enc:"):
            # Handle legacy base64 encoding
            try:
                return base64.b64decode(encrypted_data[4:].encode()).decode()
            except Exception as e:
                logger.error(f"Legacy base64 decryption failed: {e}")
                raise ValueError("Failed to decrypt legacy-encoded data")

        fernet = EncryptionService._get_fernet()
        try:
            return fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.debug(
                f"Fernet decryption failed (will try raw fallback): {e}"
            )
            raise ValueError(
                "Decryption failed - data corrupted or encryption key mismatch"
            )


# Global instance
encryption_service = EncryptionService()
