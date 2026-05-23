from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.dependencies import get_request_db


def test_get_request_db_returns_tenant_scoped_client():
    request = MagicMock()
    request.state.db = object()

    assert get_request_db(request) is request.state.db


def test_get_request_db_rejects_missing_tenant_context():
    request = MagicMock()
    request.state.db = None
    request.state.auth_failed = True
    request.state.user_id = None
    request.url.path = "/api/dashboard/boss"
    request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        get_request_db(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "租户上下文未建立，请重新登录"


@pytest.mark.asyncio
async def test_qa_pairs_missing_db_is_not_wrapped_as_500():
    from app.routers.qa_pairs import list_qa_pairs

    request = MagicMock()
    request.state.db = None
    request.state.auth_failed = True
    request.state.user_id = None
    request.url.path = "/api/qa-pairs"
    request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        await list_qa_pairs(request, user_id="user-1")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_saved_prompts_missing_db_is_not_wrapped_as_500():
    from app.routers.saved_prompts import list_saved_prompts

    request = MagicMock()
    request.state.db = None
    request.state.auth_failed = True
    request.state.user_id = None
    request.url.path = "/api/ai/saved-prompts"
    request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        await list_saved_prompts(request, user_id="user-1")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_competitors_missing_db_is_not_wrapped_as_500():
    from app.routers.competitors import list_competitors

    request = MagicMock()
    request.state.db = None
    request.state.auth_failed = True
    request.state.user_id = None
    request.state.org_id = "org-1"
    request.url.path = "/api/competitors"
    request.method = "GET"

    with pytest.raises(HTTPException) as exc_info:
        await list_competitors(request, user_id="user-1")

    assert exc_info.value.status_code == 401
