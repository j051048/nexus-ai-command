"""
Tests for auth module — JWT validation, algorithm whitelist, security controls.
"""

from unittest.mock import MagicMock

import pytest

# ── Test JWT validation ──


class TestGetCurrentUserId:
    """Tests for get_current_user_id function."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-key-for-testing-only")
        monkeypatch.setenv("ENV", "test")

    def _make_token(
        self,
        payload: dict,
        secret: str = "test-secret-key-for-testing-only",
        algorithm: str = "HS256",
    ):
        import jwt as pyjwt

        return pyjwt.encode(payload, secret, algorithm=algorithm)

    @pytest.mark.asyncio
    async def test_missing_authorization_header(self):
        """Should reject requests with no auth header."""
        from app.core.auth import get_current_user_id

        request = MagicMock()
        request.state = MagicMock(spec=[])  # no api_key_auth attr

        with pytest.raises(Exception) as exc_info:
            await get_current_user_id(request=request, authorization=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_test_prefix_blocked(self):
        """test: prefix authentication must be blocked in all environments."""
        from app.core.auth import get_current_user_id

        request = MagicMock()
        request.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
            await get_current_user_id(request=request, authorization="test:user-123")
        assert exc_info.value.status_code == 401
        assert "禁用" in exc_info.value.detail or "disabled" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_format_not_bearer(self):
        """Should reject non-Bearer token format."""
        from app.core.auth import get_current_user_id

        request = MagicMock()
        request.state = MagicMock(spec=[])

        with pytest.raises(Exception) as exc_info:
            await get_current_user_id(request=request, authorization="Basic abc123")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_hs256_token(self):
        """Should accept a valid HS256 JWT with correct secret."""
        # Reload module to pick up env var
        import importlib

        import jwt as pyjwt

        import app.core.auth as auth_module

        importlib.reload(auth_module)

        request = MagicMock()
        request.state = MagicMock(spec=[])

        payload = {
            "sub": "user-abc-123",
            "exp": 9999999999,
            "aud": "authenticated",
        }
        token = pyjwt.encode(
            payload, "test-secret-key-for-testing-only", algorithm="HS256"
        )

        user_id = await auth_module.get_current_user_id(
            request=request, authorization=f"Bearer {token}"
        )
        assert user_id == "user-abc-123"

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self):
        """Should reject expired JWT."""
        import importlib

        import jwt as pyjwt

        import app.core.auth as auth_module

        importlib.reload(auth_module)

        request = MagicMock()
        request.state = MagicMock(spec=[])

        payload = {
            "sub": "user-expired",
            "exp": 1000000000,  # Way in the past
            "aud": "authenticated",
        }
        token = pyjwt.encode(
            payload, "test-secret-key-for-testing-only", algorithm="HS256"
        )

        with pytest.raises(Exception) as exc_info:
            await auth_module.get_current_user_id(
                request=request, authorization=f"Bearer {token}"
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected(self):
        """Should reject JWT signed with wrong secret."""
        import importlib

        import jwt as pyjwt

        import app.core.auth as auth_module

        importlib.reload(auth_module)

        request = MagicMock()
        request.state = MagicMock(spec=[])

        payload = {"sub": "user-wrong", "exp": 9999999999, "aud": "authenticated"}
        token = pyjwt.encode(
            payload, "wrong-secret-for-auth-rejection-test-32b", algorithm="HS256"
        )

        with pytest.raises(Exception) as exc_info:
            await auth_module.get_current_user_id(
                request=request, authorization=f"Bearer {token}"
            )
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_auth_passthrough(self):
        """Should accept request if API key middleware already authenticated."""
        from app.core.auth import get_current_user_id

        request = MagicMock()
        request.state.api_key_auth = True
        request.state.user_id = "api-key-user-123"

        user_id = await get_current_user_id(request=request, authorization=None)
        assert user_id == "api-key-user-123"

    @pytest.mark.asyncio
    async def test_none_algorithm_rejected(self):
        """Algorithm 'none' must be rejected (algorithm confusion attack)."""
        import importlib

        import app.core.auth as auth_module

        importlib.reload(auth_module)

        request = MagicMock()
        request.state = MagicMock(spec=[])

        # Manually craft a token-like string (alg:none tokens)
        with pytest.raises(Exception) as exc_info:
            await auth_module.get_current_user_id(
                request=request,
                authorization="Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJoYWNrZXIifQ.",
            )
        assert exc_info.value.status_code == 401


class TestAlgorithmWhitelist:
    """Verify algorithm whitelist is properly configured."""

    def test_allowed_algorithms_fixed(self):
        from app.core.auth import ALLOWED_ALGORITHMS

        assert "HS256" in ALLOWED_ALGORITHMS
        assert "RS256" in ALLOWED_ALGORITHMS
        assert "ES256" in ALLOWED_ALGORITHMS
        assert "none" not in ALLOWED_ALGORITHMS
        assert "HS384" not in ALLOWED_ALGORITHMS
