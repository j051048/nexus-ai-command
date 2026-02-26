"""
P1 Fix #42: Encryption Service
Provides secure encryption/decryption for sensitive data like API keys.

P2-2: Added KeyProvider abstraction for KMS/Vault support.
"""

import base64
import logging
import os
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Fernet for secure encryption
try:
    from cryptography.fernet import Fernet

    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False
    logger.warning("cryptography package not found. Data will be stored as base64 (UNSECURE).")


class KeyProvider(ABC):
    """Abstract key provider — override for KMS/Vault/HSM integration."""

    @abstractmethod
    def get_encryption_key(self) -> str:
        """Return the Fernet-compatible encryption key."""
        ...

    @abstractmethod
    def rotate_key(self) -> str:
        """Rotate the key and return the new one."""
        ...


class EnvKeyProvider(KeyProvider):
    """Default: reads key from ENCRYPTION_KEY env var / settings."""

    def get_encryption_key(self) -> str:
        return settings.ENCRYPTION_KEY

    def rotate_key(self) -> str:
        new_key = Fernet.generate_key().decode()
        logger.warning("EnvKeyProvider: key rotation generated new key. Update ENCRYPTION_KEY env var manually.")
        return new_key


class VaultKeyProvider(KeyProvider):
    """HashiCorp Vault key provider (stub — implement per deployment)."""

    def __init__(self, vault_addr: str = None, secret_path: str = "secret/data/nexus/encryption"):
        self._vault_addr = vault_addr or os.getenv("VAULT_ADDR", "")
        self._secret_path = secret_path

    def get_encryption_key(self) -> str:
        if not self._vault_addr:
            raise RuntimeError("VAULT_ADDR not configured")
        try:
            import httpx

            token = os.getenv("VAULT_TOKEN", "")
            resp = httpx.get(
                f"{self._vault_addr}/v1/{self._secret_path}",
                headers={"X-Vault-Token": token},
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()["data"]["data"]["encryption_key"]
        except Exception as e:
            logger.error(f"Vault key fetch failed: {e}")
            raise

    def rotate_key(self) -> str:
        raise NotImplementedError("Vault key rotation should be done via Vault CLI/API")


def _resolve_key_provider() -> KeyProvider:
    """Resolve key provider based on configuration."""
    provider_type = os.getenv("KEY_PROVIDER", "env").lower()
    if provider_type == "vault":
        return VaultKeyProvider()
    return EnvKeyProvider()


# Global key provider
_key_provider = _resolve_key_provider()


class EncryptionService:
    @staticmethod
    def _get_fernet():
        """Get Fernet instance using key provider abstraction."""
        if not _FERNET_AVAILABLE:
            raise ImportError(
                "cryptography package is required for secure encryption. Please install with `pip install cryptography`."
            )
        try:
            key = _key_provider.get_encryption_key()
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error(f"Failed to initialize Fernet: {e}")
            raise ValueError(f"Invalid encryption key or Fernet initialization error: {e}")

    @staticmethod
    def encrypt(data: str) -> str:
        """Encrypt a string to a secure representation"""
        if not data:
            return ""

        # P0 Security Fix: Enforce strong encryption, no base64 fallback
        fernet = EncryptionService._get_fernet()
        return fernet.encrypt(data.encode()).decode()

    @staticmethod
    def is_encrypted(data: str) -> bool:
        """Check if a string looks like Fernet-encrypted data or legacy enc: format."""
        if not data:
            return False
        if data.startswith("enc:"):
            return True
        # Fernet tokens are URL-safe base64 and always start with 'gAAAAA'
        return data.startswith("gAAAAA")

    @staticmethod
    def decrypt(encrypted_data: str) -> str:
        """Decrypt an encrypted string. Returns raw value if not encrypted."""
        if not encrypted_data:
            return ""

        if encrypted_data.startswith("enc:"):
            # Handle legacy base64 encoding
            try:
                return base64.b64decode(encrypted_data[4:].encode()).decode()
            except Exception as e:
                logger.error(f"Legacy base64 decryption failed: {e}")
                raise ValueError("Failed to decrypt legacy-encoded data")

        # Not encrypted (plain text API key) — return as-is without attempting Fernet
        if not EncryptionService.is_encrypted(encrypted_data):
            return encrypted_data

        fernet = EncryptionService._get_fernet()
        try:
            return fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.warning(f"Fernet decryption failed: {e}")
            raise ValueError("Decryption failed - data corrupted or encryption key mismatch")


# Global instance
encryption_service = EncryptionService()
