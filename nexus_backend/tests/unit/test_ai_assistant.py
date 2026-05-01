import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request

from app.routers.ai_assistant import (
    parse_voice,
    batch_approval_suggestions,
    get_customer_memory_summary
)
from app.services.llm_adapters.base import ChatResponse
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
    # background_tasks 是新签名新增的必传参数
    mock_bg = MagicMock()
    with pytest.raises(HTTPException) as exc:
        await batch_approval_suggestions(request_ids=[], request=mock_request, background_tasks=mock_bg, user_id="u1", db=mock_request.state.db)
    assert "不能为空" in str(exc.value.detail)

@pytest.mark.asyncio
async def test_batch_approval_suggestions_success(mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"id": "r1", "amount": 100}]
    mock_db.table.return_value.select.return_value.in_.return_value.execute = mock_exec

    mock_bg = MagicMock()
    res = await batch_approval_suggestions(request_ids=["r1"], request=mock_request, background_tasks=mock_bg, user_id="u1", db=mock_db)
    # 改为后台任务模式：返回 task_id 而非直接结果
    assert res.get("data").get("task_id") is not None
    assert res.get("data").get("status") == "processing"
    # 确认后台任务已注册
    mock_bg.add_task.assert_called_once()

@pytest.mark.asyncio
async def test_get_customer_memory_summary(mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"content": "Customer wants more discount"}]
    mock_db.table.return_value.select.return_value.eq.return_value.ilike.return_value.order.return_value.limit.return_value.execute = mock_exec

    import app.routers.ai_assistant
    # Clear cache
    app.routers.ai_assistant._memory_summary_cache = {}

    mock_bg = MagicMock()
    res = await get_customer_memory_summary(customer_name="Alpha", request=mock_request, background_tasks=mock_bg, user_id="u1")
    # 改为后台任务模式：有记忆数据时返回 task_id
    assert res.get("data").get("task_id") is not None
    assert res.get("data").get("status") == "processing"
    # 确认后台任务已注册
    mock_bg.add_task.assert_called_once()
