import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from pydantic import ValidationError

from app.routers.intent_rules import (
    list_intent_rules,
    create_intent_rule,
    update_intent_rule,
    delete_intent_rule,
    validate_regex,
    IntentRuleCreate,
    IntentRuleUpdate,
    RegexValidateRequest
)

@pytest.fixture
def mock_request():
    req = MagicMock(spec=Request)
    req.state = MagicMock()
    
    mock_db = MagicMock()
    req.state.db = mock_db
    return req

def test_pydantic_validators():
    with pytest.raises(ValidationError):
        IntentRuleCreate(keyword="  ", complexity="critical")
        
    with pytest.raises(ValidationError):
        IntentRuleCreate(keyword="test", complexity="invalid")

    with pytest.raises(ValidationError):
        IntentRuleUpdate(complexity="invalid_val")

@pytest.mark.asyncio
async def test_list_intent_rules(mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"keyword": "buy"}]
    mock_db.table.return_value.select.return_value.order.return_value.execute = mock_exec

    res = await list_intent_rules(mock_request, user_id="u1")
    assert res.get("success") is True
    assert res.get("data") == [{"keyword": "buy"}]

@pytest.mark.asyncio
async def test_create_intent_rule_conflict(mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [{"id": 1}] # EXISTS
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = mock_exec

    req_body = IntentRuleCreate(keyword="buy", complexity="critical")
    from fastapi import HTTPException
    res = await create_intent_rule(body=req_body, request=mock_request, user_id="u1")
    assert isinstance(res, HTTPException)
    assert res.status_code == 409
    assert "已存在" in str(res.detail)

@pytest.mark.asyncio
async def test_update_intent_rule_not_found(mock_request):
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = [] # empty array for update
    mock_db.table.return_value.update.return_value.eq.return_value.execute = mock_exec
    
    req_body = IntentRuleUpdate(description="test")
    from fastapi import HTTPException
    res = await update_intent_rule(rule_id="r1", body=req_body, request=mock_request, user_id="u1")
    assert isinstance(res, HTTPException)
    assert res.status_code == 404
    assert "不存在" in str(res.detail)

@pytest.mark.asyncio
async def test_delete_intent_rule(mock_request, monkeypatch):
    mock_reload = AsyncMock()
    monkeypatch.setattr("app.routers.intent_rules._trigger_reload", mock_reload)
    
    mock_db = mock_request.state.db
    mock_exec = AsyncMock()
    mock_exec.return_value.data = None
    mock_db.table.return_value.delete.return_value.eq.return_value.execute = mock_exec

    res = await delete_intent_rule(rule_id="r1", request=mock_request, user_id="u1")
    assert res.get("success") is True
    assert mock_reload.called

@pytest.mark.asyncio
async def test_validate_regex():
    res_ok = await validate_regex(RegexValidateRequest(pattern="^test$"), user_id="u1")
    assert res_ok.get("data").get("valid") is True

    res_err = await validate_regex(RegexValidateRequest(pattern="[invalid"), user_id="u1")
    assert res_err.get("data").get("valid") is False
