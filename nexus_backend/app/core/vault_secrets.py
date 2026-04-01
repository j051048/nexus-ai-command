"""
HashiCorp Vault integration for secure secret management.

P0 Task: Replace environment variable storage with Vault.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_vault_client = None


def get_vault_client():
    """Get or create Vault client."""
    global _vault_client
    if _vault_client is not None:
        return _vault_client

    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")

    if not vault_addr or not vault_token:
        logger.warning("[Vault] VAULT_ADDR or VAULT_TOKEN not set, using env vars")
        return None

    try:
        import hvac

        _vault_client = hvac.Client(url=vault_addr, token=vault_token)
        if not _vault_client.is_authenticated():
            logger.error("[Vault] Authentication failed")
            _vault_client = None
            return None

        logger.info(f"[Vault] Connected to {vault_addr}")
        return _vault_client
    except ImportError:
        logger.error("[Vault] hvac library not installed: pip install hvac")
        return None
    except Exception as e:
        logger.error(f"[Vault] Connection failed: {e}")
        return None


def get_secret(path: str, key: str, fallback_env: Optional[str] = None) -> Optional[str]:
    """
    Get secret from Vault or fallback to environment variable.

    Args:
        path: Vault secret path (e.g., 'nexus/openai_api_key')
        key: Key within the secret (e.g., 'key')
        fallback_env: Environment variable name to use if Vault unavailable

    Returns:
        Secret value or None
    """
    client = get_vault_client()

    if client:
        try:
            secret = client.secrets.kv.v2.read_secret_version(path=path)
            value = secret["data"]["data"].get(key)
            if value:
                logger.debug(f"[Vault] Retrieved secret from {path}/{key}")
                return value
        except Exception as e:
            logger.warning(f"[Vault] Failed to read {path}/{key}: {e}")

    if fallback_env:
        value = os.getenv(fallback_env)
        if value:
            logger.debug(f"[Vault] Using fallback env var {fallback_env}")
            return value

    return None


def set_secret(path: str, data: dict) -> bool:
    """
    Store secret in Vault.

    Args:
        path: Vault secret path
        data: Dictionary of key-value pairs

    Returns:
        True if successful
    """
    client = get_vault_client()
    if not client:
        logger.error("[Vault] Client not available")
        return False

    try:
        client.secrets.kv.v2.create_or_update_secret(path=path, secret=data)
        logger.info(f"[Vault] Stored secret at {path}")
        return True
    except Exception as e:
        logger.error(f"[Vault] Failed to store {path}: {e}")
        return False


# Convenience functions for common secrets
def get_openai_api_key() -> Optional[str]:
    return get_secret("nexus/openai", "api_key", "OPENAI_API_KEY")


def get_encryption_key() -> Optional[str]:
    return get_secret("nexus/encryption", "key", "ENCRYPTION_KEY")


def get_supabase_service_key() -> Optional[str]:
    return get_secret("nexus/supabase", "service_key", "SUPABASE_SERVICE_KEY")
