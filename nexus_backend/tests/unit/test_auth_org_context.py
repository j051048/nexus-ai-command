"""Auth dependency edge cases for tenant context."""

import pytest
from fastapi import HTTPException

from app.core.auth import get_current_org_id


class _State:
    auth_failed = False
    org_id = None


class _Headers(dict):
    def get(self, key: str, default=None):
        return super().get(key, default)


class _Request:
    def __init__(self, *, authorization: str | None = None, auth_failed: bool = False):
        self.state = _State()
        self.state.auth_failed = auth_failed
        self.headers = _Headers()
        if authorization:
            self.headers["Authorization"] = authorization


@pytest.mark.asyncio
async def test_missing_org_without_auth_is_401():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_org_id(_Request())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_org_after_auth_failure_is_401():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_org_id(
            _Request(authorization="Bearer bad-token", auth_failed=True)
        )

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_org_with_authenticated_context_is_configuration_error():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_org_id(_Request(authorization="Bearer verified-token"))

    assert exc_info.value.status_code == 400
