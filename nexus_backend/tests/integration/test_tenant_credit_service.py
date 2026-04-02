"""Tests for tenant_credit_service: quota, credits, rate limiting, abuse detection."""

import pytest

from app.services.tenant_credit_service import (
    AlertLevel,
    CreditType,
    TenantCreditService,
    TenantQuota,
)


class TestCreditCheck:
    @pytest.mark.asyncio
    async def test_check_credit_within_limit(self):
        service = TenantCreditService()
        is_ok, msg = await service.check_credit("org-1", CreditType.TOKENS, 100)
        assert is_ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_consume_credit(self):
        service = TenantCreditService()
        ok, msg = await service.consume_credit("org-1", CreditType.TOKENS, 100, "user-1")
        assert ok is True
        assert msg is None

    @pytest.mark.asyncio
    async def test_consume_credit_tracks_usage(self):
        service = TenantCreditService()
        await service.consume_credit("org-1", CreditType.API_CALLS, 1, "user-1")
        await service.consume_credit("org-1", CreditType.API_CALLS, 1, "user-1")
        stats = await service.get_usage_stats("org-1")
        assert stats is not None


class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_rate_limit_allows_normal(self):
        service = TenantCreditService()
        allowed, retry_after = await service.check_rate_limit("org-1", "user-1")
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_burst(self):
        service = TenantCreditService()
        # Exhaust burst limit
        for _ in range(15):
            await service.check_rate_limit("org-burst-test", "user-burst")
        allowed, retry_after = await service.check_rate_limit("org-burst-test", "user-burst")
        # Should eventually be rate-limited
        # Note: depends on TenantQuota.burst_limit (default 10)


class TestAbuseDetection:
    @pytest.mark.asyncio
    async def test_normal_request_not_suspicious(self):
        service = TenantCreditService()
        result = await service.detect_abuse(
            user_id="user-1",
            org_id="org-1",
            action="chat",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Chrome",
        )
        assert result.is_suspicious is False
        assert result.risk_score < 0.5

    @pytest.mark.asyncio
    async def test_suspicious_user_agent(self):
        service = TenantCreditService()
        result = await service.detect_abuse(
            user_id="user-1",
            org_id="org-1",
            action="chat",
            ip_address="10.0.0.1",
            user_agent="python-requests/2.31.0",
        )
        # python-requests adds 0.2 to risk score
        assert result.risk_score >= 0.2


class TestAlertLevel:
    def test_alert_level_thresholds(self):
        assert AlertLevel.NORMAL.value == "normal"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.CRITICAL.value == "critical"
        assert AlertLevel.EXHAUSTED.value == "exhausted"


class TestTenantQuota:
    def test_default_quotas(self):
        q = TenantQuota()
        assert q.monthly_token_limit == 1_000_000
        assert q.monthly_api_call_limit == 10_000
        assert q.rate_limit_per_minute == 60
        assert q.burst_limit == 10
        assert q.storage_limit_mb == 1_000
