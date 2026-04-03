"""
EncryptionService 单元测试
覆盖: 加密/解密/检测/KeyProvider/边界情况
"""

import base64
from unittest.mock import MagicMock, patch

import pytest


# ─── Encrypt / Decrypt Round-trip ──────────────────────────────


class TestEncryptDecrypt:
    """加密解密往返测试"""

    def _make_provider(self):
        """Create mock provider with valid Fernet key."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        mock_provider = MagicMock()
        mock_provider.get_encryption_key.return_value = test_key
        return mock_provider

    def test_encrypt_decrypt_roundtrip(self):
        from app.services.encryption_service import EncryptionService
        with patch("app.services.encryption_service._key_provider", self._make_provider()):
            plaintext = "my-secret-api-key-12345"
            encrypted = EncryptionService.encrypt(plaintext)
            assert encrypted != plaintext
            decrypted = EncryptionService.decrypt(encrypted)
            assert decrypted == plaintext

    def test_encrypt_empty_string(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.encrypt("") == ""

    def test_decrypt_empty_string(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.decrypt("") == ""

    def test_encrypt_unicode(self):
        from app.services.encryption_service import EncryptionService
        with patch("app.services.encryption_service._key_provider", self._make_provider()):
            plaintext = "中文密钥测试🔑"
            encrypted = EncryptionService.encrypt(plaintext)
            assert EncryptionService.decrypt(encrypted) == plaintext

    def test_encrypted_output_starts_with_gAAAAA(self):
        from app.services.encryption_service import EncryptionService
        with patch("app.services.encryption_service._key_provider", self._make_provider()):
            encrypted = EncryptionService.encrypt("test")
            assert encrypted.startswith("gAAAAA")


# ─── is_encrypted ──────────────────────────────────────────────


class TestIsEncrypted:
    """加密检测测试"""

    def test_fernet_token_detected(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.is_encrypted("gAAAAABhello") is True

    def test_legacy_enc_prefix_detected(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.is_encrypted("enc:dGVzdA==") is True

    def test_plaintext_not_detected(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.is_encrypted("plain-api-key") is False

    def test_empty_string_not_detected(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.is_encrypted("") is False

    def test_none_like_not_detected(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.is_encrypted("") is False


# ─── Decrypt Legacy ────────────────────────────────────────────


class TestDecryptLegacy:
    """Legacy enc: 前缀解密测试"""

    def test_legacy_base64_decrypt(self):
        from app.services.encryption_service import EncryptionService
        original = "my-secret"
        encoded = "enc:" + base64.b64encode(original.encode()).decode()
        assert EncryptionService.decrypt(encoded) == original

    def test_legacy_invalid_base64_raises(self):
        from app.services.encryption_service import EncryptionService
        with pytest.raises(ValueError, match="legacy"):
            EncryptionService.decrypt("enc:!!!invalid-base64!!!")

    def test_plaintext_passthrough(self):
        from app.services.encryption_service import EncryptionService
        assert EncryptionService.decrypt("plain-text-key") == "plain-text-key"


# ─── KeyProvider ───────────────────────────────────────────────


class TestKeyProvider:
    """KeyProvider 抽象测试"""

    def test_env_key_provider_reads_settings(self):
        with patch("app.services.encryption_service.settings") as mock_settings:
            mock_settings.ENCRYPTION_KEY = "test-key-value"
            from app.services.encryption_service import EnvKeyProvider
            provider = EnvKeyProvider()
            assert provider.get_encryption_key() == "test-key-value"

    def test_vault_provider_no_addr_raises(self):
        from app.services.encryption_service import VaultKeyProvider
        provider = VaultKeyProvider(vault_addr="")
        with pytest.raises(RuntimeError, match="VAULT_ADDR"):
            provider.get_encryption_key()

    def test_resolve_key_provider_default_is_env(self):
        with patch.dict("os.environ", {"KEY_PROVIDER": "env"}, clear=False):
            from app.services.encryption_service import _resolve_key_provider, EnvKeyProvider
            provider = _resolve_key_provider()
            assert isinstance(provider, EnvKeyProvider)

    def test_resolve_key_provider_vault(self):
        with patch.dict("os.environ", {"KEY_PROVIDER": "vault"}, clear=False):
            from app.services.encryption_service import _resolve_key_provider, VaultKeyProvider
            provider = _resolve_key_provider()
            assert isinstance(provider, VaultKeyProvider)


# ─── Edge Cases ────────────────────────────────────────────────


class TestEdgeCases:
    """边界情况测试"""

    def test_invalid_fernet_key_raises_value_error(self):
        mock_provider = MagicMock()
        mock_provider.get_encryption_key.return_value = "not-a-valid-fernet-key"
        with patch("app.services.encryption_service._key_provider", mock_provider):
            from app.services.encryption_service import EncryptionService
            with pytest.raises(ValueError, match="Invalid encryption key"):
                EncryptionService.encrypt("test")

    def test_corrupted_fernet_data_raises(self):
        from cryptography.fernet import Fernet
        test_key = Fernet.generate_key().decode()
        mock_provider = MagicMock()
        mock_provider.get_encryption_key.return_value = test_key
        with patch("app.services.encryption_service._key_provider", mock_provider):
            from app.services.encryption_service import EncryptionService
            with pytest.raises(ValueError, match="Decryption failed"):
                EncryptionService.decrypt("gAAAAABcorrupted_data_here")
