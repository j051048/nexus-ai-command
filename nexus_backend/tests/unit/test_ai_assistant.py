import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

from app.routers.ai_assistant import (
    parse_voice,
    batch_approval_suggestions,
    get_customer_memory_summary
)
from fastapi import HTTPException

@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.org_id = "test_org"
    req.state.db = MagicMock()
    return req

@pytest.mark.asyncio
@patch("app.routers.ai_assistant.parse_voice_intent", new_callable=AsyncMock)
async def test_parse_voice(mock_parse, mock_request):
    mock_parse.return_value = {"intent": "test"}
    res = await parse_voice(text="hello", request=mock_request, user_id="u1")
    assert res == {"intent": "test"}
    mock_parse.assert_called_once_with(text="hello", user_id="u1", org_id="test_org")

@pytest.mark.asyncio
async def test_parse_voice_no_org(mock_request):
    mock_request.state.org_id = None
    with pytest.raises(HTTPException) as exc:
        await parse_voice(text="hello", request=mock_request, user_id="u1")
    assert "租户上下文缺失" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_batch_approval_suggestions_empty(mock_request):
    with pytest.raises(HTTPException) as exc:
        await batch_approval_suggestions(request_ids=[], request=mock_request, user_id="u1", db=mock_request.state.db)
    assert "不能为空" in str(exc.value.detail)

@pytest.mark.asyncio
@patch("app.routers.ai_assistant.get_llm")
async def test_batch_approval_suggestions_success(mock_get_llm, mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"id": "r1", "amount": 100}]
    mock_db.table.return_value.select.return_value.in_.return_value.execute = mock_exec

    mock_llm_instance = AsyncMock()
    mock_llm_result = MagicMock()
    mock_llm_result.content = '{"approve_count": 1, "reject_count": 0, "reason": "ok"}'
    mock_llm_instance.ainvoke.return_value = mock_llm_result
    mock_get_llm.return_value = mock_llm_instance

    res = await batch_approval_suggestions(request_ids=["r1"], request=mock_request, user_id="u1", db=mock_db)
    assert res.get("data").get("approve_count") == 1
    assert mock_get_llm.called

@pytest.mark.asyncio
@patch("app.routers.ai_assistant.get_llm")
async def test_get_customer_memory_summary(mock_get_llm, mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"content": "Customer wants more discount"}]
    mock_db.table.return_value.select.return_value.eq.return_value.ilike.return_value.order.return_value.limit.return_value.execute = mock_exec

    mock_llm_instance = AsyncMock()
    mock_llm_result = MagicMock()
    mock_llm_result.content = '```json\n{"summary": "Need discount", "key_points": ["d"], "sentiment": "neutral"}\n```'
    mock_llm_instance.ainvoke.return_value = mock_llm_result
    mock_get_llm.return_value = mock_llm_instance

    import app.routers.ai_assistant
    # Clear cache
    app.routers.ai_assistant._memory_summary_cache = {}

    res = await get_customer_memory_summary(customer_name="Alpha", request=mock_request, user_id="u1")
    assert res.get("data").get("has_insights") is True
    assert res.get("data").get("summary") == "Need discount"
