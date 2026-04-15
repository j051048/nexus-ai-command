import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import time

from app.core.token_budget import (
    TokenBudgetManager,
    _InMemoryBudgetStore,
    BudgetVerdict,
    UsageSummary,
)
from app.core.config import settings

@pytest.fixture
def budget_manager():
    manager = TokenBudgetManager()
    manager._memory_store = _InMemoryBudgetStore()
    return manager

@pytest.mark.asyncio
class TestTokenBudgetManager:
    async def test_in_memory_store_incr_and_expiry(self):
        store = _InMemoryBudgetStore()
        
        # Test increment
        val1 = await store.incr_by("key1", 100, ttl=1)
        assert val1 == 100
        
        val2 = await store.incr_by("key1", 50, ttl=1)
        assert val2 == 150
        
        # Test get_val
        val = await store.get_val("key1")
        assert val == 150
        
        # Test expiry
        # Normally time is fast, we can mock time or sleep
        with patch("time.time", return_value=time.time() + 2):
            val_expired = await store.get_val("key1")
            assert val_expired == 0
            
            # incr after expiry
            val3 = await store.incr_by("key1", 10, ttl=1)
            assert val3 == 10

    @patch("app.core.token_budget.settings")
    async def test_check_budget_session_token_exceeded(self, mock_settings, budget_manager):
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 1000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 5000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 5.0
        
        # Exceed session boundary
        await budget_manager._incr(budget_manager._key("sess_tok", "session_1"), 1001, 86400)
        
        status = await budget_manager.check_budget("session_1", "user_1")
        assert status.verdict == BudgetVerdict.EXCEEDED
        assert "超过单会话上限" in status.message

    @patch("app.core.token_budget.settings")
    async def test_check_budget_user_hour_token_exceeded(self, mock_settings, budget_manager):
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 5000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 1000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 5.0
        
        user_id = "user_2"
        hour_key = budget_manager._key("user_hr", f"{user_id}:{int(time.time() // 3600)}")
        await budget_manager._incr(hour_key, 1005, 3600)
        
        status = await budget_manager.check_budget("session_2", user_id)
        assert status.verdict == BudgetVerdict.EXCEEDED
        assert "超过每小时上限" in status.message

    @patch("app.core.token_budget.settings")
    async def test_check_budget_tenant_daily_cost_exceeded(self, mock_settings, budget_manager):
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 50000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 50000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 50.0
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT = 10.0
        
        tenant_id = "tenant_1"
        day_key = budget_manager._key("tenant_day", f"{tenant_id}:{int(time.time() // 86400)}")
        await budget_manager._incr(day_key, 15.0, 86400)
        
        status = await budget_manager.check_budget("session_3", "user_3", tenant_id)
        assert status.verdict == BudgetVerdict.EXCEEDED
        assert "超过每日上限" in status.message

    @patch("app.core.token_budget.settings")
    async def test_check_budget_tenant_monthly_cost_exceeded(self, mock_settings, budget_manager):
        # Allow everything except monthly cost
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 50000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 50000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 50.0
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_DAY_PER_TENANT = 100.0
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT = 500.0

        tenant_id = "tenant_2"
        month_key = budget_manager._key("tenant_month", f"{tenant_id}:{time.strftime('%Y-%m')}")
        await budget_manager._incr(month_key, 501.0, 2764800)
        
        status = await budget_manager.check_budget("session_4", "user_4", tenant_id)
        assert status.verdict == BudgetVerdict.EXCEEDED
        assert "超过月度上限" in status.message

    @patch("app.core.token_budget.settings")
    async def test_check_budget_warning_boundary(self, mock_settings, budget_manager):
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 1000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 1000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 10.0
        # tenant logic bypassed by passing None
        
        # 85% is greater than 80% threshold
        await budget_manager._incr(budget_manager._key("sess_tok", "sess_warn"), 850, 86400)
        
        status = await budget_manager.check_budget("sess_warn", "user_warn")
        assert status.verdict == BudgetVerdict.WARNING
        assert "接近预算上限" in status.message
        assert "会话 token" in status.message

    @patch("app.core.token_budget.settings")
    async def test_check_budget_ok(self, mock_settings, budget_manager):
        mock_settings.TOKEN_BUDGET_MAX_PER_SESSION = 1000
        mock_settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 1000
        mock_settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 10.0
        
        # 50% is below 80% threshold
        await budget_manager._incr(budget_manager._key("sess_tok", "sess_ok"), 500, 86400)
        
        status = await budget_manager.check_budget("sess_ok", "user_ok")
        assert status.verdict == BudgetVerdict.OK

    async def test_record_usage(self, budget_manager):
        session_id = "test_session"
        user_id = "test_user"
        tenant_id = "test_tenant"
        
        # Record explicit cost
        await budget_manager.record_usage(
            session_id, user_id, tenant_id,
            input_tokens=100, output_tokens=50, model="gpt-4o", cost=0.01
        )
        
        # Check if values were incremented correctly
        summary = await budget_manager.get_session_usage(session_id)
        assert summary.session_total_tokens == 150
        assert abs(summary.session_cost_usd - 0.01) < 1e-5
        
        # Check user hour
        user_hr = await budget_manager._get(budget_manager._key("user_hr", f"{user_id}:{int(time.time() // 3600)}"))
        assert user_hr == 150

        # Check tenant day
        tenant_day = await budget_manager._get(budget_manager._key("tenant_day", f"{tenant_id}:{int(time.time() // 86400)}"))
        assert tenant_day == 0.01

    @patch("app.core.token_budget.settings")
    async def test_check_request_cost(self, mock_settings, budget_manager):
        mock_settings.LLM_MAX_COST_PER_REQUEST = 1.0
        
        assert await budget_manager.check_request_cost(0.5) is True
        assert await budget_manager.check_request_cost(1.5) is False
        assert await budget_manager.check_request_cost(-1.0) is True  # <=0 logic

    async def test_get_redis_fallback(self, budget_manager):
        # By default no redis setup should fallback to memory gracefully
        redis_client = await budget_manager._get_redis()
        assert redis_client is None

        # Even with _incr, it goes to memory
        val = await budget_manager._incr("test", 10, 60)
        assert val == 10
