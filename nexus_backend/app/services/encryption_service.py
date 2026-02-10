"""
P1 Fix #42: Encryption Service
Provides secure encryption/decryption for sensitive data like API keys.
"""
import logging
import base64
from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Fernet for secure encryption
try:
    from cryptography.fernet import Fernet
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    logger.warning("cryptography package not found. Data will be stored as base64 (UNSECURE).")

class EncryptionService:
    @staticmethod
    def _get_fernet():
        """Get Fernet instance using master key"""
        if not _FERNET_AVAILABLE:
            return None
        try:
            return Fernet(settings.ENCRYPTION_KEY.encode())
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            return None

    @staticmethod
    def encrypt(data: str) -> str:
        """Encrypt a string to a secure representation"""
        if not data:
            return ""
        
        fernet = EncryptionService._get_fernet()
        if fernet:
            return fernet.encrypt(data.encode()).decode()
        
        # Fallback to base64 if cryptography is missing (better than plain text, but not secure)
        return "enc:" + base64.b64encode(data.encode()).decode()

    @staticmethod
    def decrypt(encrypted_data: str) -> str:
        """Decrypt an encrypted string"""
        if not encrypted_data:
            return ""
        
        if encrypted_data.startswith("enc:"):
            # Handle fallback base64
            try:
                return base64.b64decode(encrypted_data[4:].encode()).decode()
            except Exception:
                return encrypted_data
        
        fernet = EncryptionService._get_fernet()
        if fernet:
            try:
                return fernet.decrypt(encrypted_data.encode()).decode()
            except Exception as e:
                logger.error(f"Decryption failed: {e}")
                return encrypted_data # Return original if decryption fails (might be plain text)
        
        return encrypted_data

# Global instance
encryption_service = EncryptionService()
