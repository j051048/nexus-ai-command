"""
P0 Security Fix: Tenant Credit Service

Implements organization-level credit/quota system and abuse prevention.
Fixes Issues #50, #51: Anti-abuse mechanism and tenant budget control.
"""

import os
import time
import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class CreditType(Enum):
    """Types of credits available"""
    TOKENS = "tokens"
    API_CALLS = "api_calls"
    STORAGE_MB = "storage_mb"


class AlertLevel(Enum):
    """Alert levels for credit usage"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"


@dataclass
class TenantCredit:
    """Credit allocation for a tenant"""
    org_id: str
    credit_type: CreditType
    allocated: int
    used: int
    reserved: int = 0
    period_start: datetime = None
    period_end: datetime = None

    @property
    def remaining(self) -> int:
        return max(0, self.allocated - self.used - self.reserved)

    @property
    def usage_percentage(self) -> float:
        if self.allocated == 0:
            return 100.0
        return (self.used / self.allocated) * 100

    @property
    def alert_level(self) -> AlertLevel:
        pct = self.usage_percentage
        if pct >= 100:
            return AlertLevel.EXHAUSTED
        elif pct >= 95:
            return AlertLevel.CRITICAL
        elif pct >= 80:
            return AlertLevel.WARNING
        return AlertLevel.NORMAL


@dataclass
class AbuseDetectionResult:
    """Result of abuse detection check"""
    is_suspicious: bool
    risk_score: float
    reasons: list = field(default_factory=list)
    recommended_action: str = "allow"


@dataclass
class TenantQuota:
    """Default quota configuration for tenants"""
    monthly_token_limit: int = 1_000_000
    monthly_api_call_limit: int = 10_000
    daily_token_limit: int = 100_000
    daily_api_call_limit: int = 1_000
    rate_limit_per_minute: int = 60
    burst_limit: int = 10
    storage_limit_mb: int = 1_000


class TenantCreditService:
    """
    P0 Security: Tenant-level credit management and abuse prevention.
    """

    DEFAULT_QUOTAS = TenantQuota()

    def __init__(self):
        self._rate_limit_cache: Dict[str, list] = {}
        self._credit_cache: Dict[str, TenantCredit] = {}
        self._behavior_tracker: Dict[str, Dict] = {}
        self._ip_tracker: Dict[str, Dict] = {}

    async def check_credit(
        self, org_id: str, credit_type: CreditType, amount: int = 1, db=None
    ) -> Tuple[bool, Optional[str]]:
        """Check if tenant has sufficient credits."""
        if not org_id:
            return False, "Organization ID is required"

        credit = await self._get_credit_status(org_id, credit_type, db)

        if credit.alert_level == AlertLevel.EXHAUSTED:
            return False, f"{credit_type.value} quota exhausted. Please upgrade."

        if credit.remaining < amount:
            return False, f"Insufficient {credit_type.value}"

        if credit.alert_level == AlertLevel.WARNING:
            logger.warning(f"Tenant {org_id} approaching limit ({credit.usage_percentage:.1f}%)")

        return True, None

    async def consume_credit(
        self, org_id: str, credit_type: CreditType, amount: int, user_id: str = None, db=None
    ) -> Tuple[bool, Optional[str]]:
        """Consume credits from tenant allocation."""
        has_credit, error = await self.check_credit(org_id, credit_type, amount, db)
        if not has_credit:
            return False, error

        cache_key = f"{org_id}:{credit_type.value}"
        if cache_key in self._credit_cache:
            self._credit_cache[cache_key].used += amount

        await self._persist_credit_usage(org_id, credit_type, amount, user_id, db)
        return True, None

    async def check_rate_limit(self, org_id: str, user_id: str) -> Tuple[bool, Optional[int]]:
        """Check rate limit. Returns (is_allowed, retry_after_seconds)."""
        quota = await self._get_tenant_quota(org_id)
        current_minute = int(time.time() / 60)

        org_key = f"org:{org_id}:{current_minute}"
        org_requests = self._rate_limit_cache.get(org_key, [])

        if len(org_requests) >= quota.rate_limit_per_minute:
            retry_after = 60 - (time.time() % 60)
            return False, int(retry_after)

        if user_id:
            user_key = f"user:{user_id}:{current_minute}"
            user_requests = self._rate_limit_cache.get(user_key, [])
            if len(user_requests) >= quota.burst_limit:
                return False, 5

        now = time.time()
        self._rate_limit_cache[org_key] = org_requests + [now]
        if user_id:
            user_key = f"user:{user_id}:{current_minute}"
            self._rate_limit_cache[user_key] = self._rate_limit_cache.get(user_key, []) + [now]

        return True, None

    async def detect_abuse(
        self, user_id: str, org_id: str, action: str, ip_address: str = None, user_agent: str = None
    ) -> AbuseDetectionResult:
        """Detect potential abuse patterns."""
        risk_factors = []
        risk_score = 0.0

        user_behavior = self._behavior_tracker.get(user_id, {})
        recent_requests = user_behavior.get("recent_requests", [])
        now = time.time()

        # Check frequency
        requests_last_minute = len([r for r in recent_requests if now - r < 60])
        if requests_last_minute > 30:
            risk_factors.append(f"High frequency: {requests_last_minute}/min")
            risk_score += 0.3

        requests_last_hour = len([r for r in recent_requests if now - r < 3600])
        if requests_last_hour > 500:
            risk_factors.append(f"Very high hourly: {requests_last_hour}/hour")
            risk_score += 0.4

        # Check bot-like patterns
        if len(recent_requests) >= 5:
            intervals = [recent_requests[i] - recent_requests[i-1] 
                        for i in range(1, min(6, len(recent_requests)))]
            avg_interval = sum(intervals) / len(intervals) if intervals else 1
            if avg_interval < 0.5:
                risk_factors.append("Bot-like rapid-fire pattern")
                risk_score += 0.5

        # Check IP
        if ip_address:
            ip_data = self._ip_tracker.get(ip_address, {})
            if ip_data.get("blocked_until", 0) > now:
                risk_factors.append(f"IP {ip_address} blocked")
                risk_score = 1.0
            elif ip_data.get("failed_attempts", 0) > 10:
                risk_factors.append("IP has multiple failures")
                risk_score += 0.3

        # Check user agent
        if user_agent:
            suspicious = ["python-requests", "curl", "wget", "scanner", "bot"]
            if any(s in user_agent.lower() for s in suspicious):
                risk_factors.append(f"Suspicious UA: {user_agent[:30]}")
                risk_score += 0.2

        recommended_action = "allow"
        if risk_score >= 0.8:
            recommended_action = "block"
        elif risk_score >= 0.5:
            recommended_action = "throttle"

        self._behavior_tracker[user_id] = {
            **user_behavior,
            "recent_requests": (recent_requests + [now])[-100:],
            "last_action": action,
            "last_action_time": now
        }

        is_suspicious = risk_score >= 0.3
        if is_suspicious:
            logger.warning(f"Abuse detected: user={user_id}, score={risk_score:.2f}")

        return AbuseDetectionResult(
            is_suspicious=is_suspicious,
            risk_score=min(risk_score, 1.0),
            reasons=risk_factors,
            recommended_action=recommended_action
        )

    async def record_failed_attempt(self, ip_address: str, action: str = "unknown"):
        """Record a failed attempt for IP tracking."""
        if not ip_address:
            return
        now = time.time()
        ip_data = self._ip_tracker.get(ip_address, {})
        recent_failures = [t for t in ip_data.get("failure_times", []) if now - t < 3600]
        recent_failures.append(now)
        self._ip_tracker[ip_address] = {
            **ip_data,
            "failure_times": recent_failures,
            "failed_attempts": len(recent_failures),
            "blocked_until": now + 300 if len(recent_failures) > 10 else 0
        }

    async def get_usage_stats(self, org_id: str, db=None) -> Dict:
        """Get usage statistics for a tenant."""
        token_credit = await self._get_credit_status(org_id, CreditType.TOKENS, db)
        api_credit = await self._get_credit_status(org_id, CreditType.API_CALLS, db)
        return {
            "tokens": {
                "allocated": token_credit.allocated,
                "used": token_credit.used,
                "remaining": token_credit.remaining,
                "usage_percentage": token_credit.usage_percentage,
                "alert_level": token_credit.alert_level.value
            },
            "api_calls": {
                "allocated": api_credit.allocated,
                "used": api_credit.used,
                "remaining": api_credit.remaining,
                "usage_percentage": api_credit.usage_percentage,
                "alert_level": api_credit.alert_level.value
            }
        }

    async def _get_credit_status(self, org_id: str, credit_type: CreditType, db=None) -> TenantCredit:
        """Get credit status from cache or database."""
        cache_key = f"{org_id}:{credit_type.value}"
        if cache_key in self._credit_cache:
            return self._credit_cache[cache_key]

        if db:
            try:
                res = await db.table("tenant_credits").select("*").eq("org_id", org_id).eq("credit_type", credit_type.value).maybe_single().execute()
                if res.data:
                    credit = TenantCredit(
                        org_id=org_id, credit_type=credit_type,
                        allocated=res.data.get("allocated", 0),
                        used=res.data.get("used", 0),
                        reserved=res.data.get("reserved", 0)
                    )
                    self._credit_cache[cache_key] = credit
                    return credit
            except Exception as e:
                logger.error(f"Failed to load credit: {e}")

        quota = await self._get_tenant_quota(org_id)
        defaults = {
            CreditType.TOKENS: quota.monthly_token_limit,
            CreditType.API_CALLS: quota.monthly_api_call_limit,
            CreditType.STORAGE_MB: quota.storage_limit_mb
        }
        credit = TenantCredit(org_id=org_id, credit_type=credit_type, allocated=defaults.get(credit_type, 0), used=0)
        self._credit_cache[cache_key] = credit
        return credit

    async def _get_tenant_quota(self, org_id: str) -> TenantQuota:
        return self.DEFAULT_QUOTAS

    async def _persist_credit_usage(self, org_id: str, credit_type: CreditType, amount: int, user_id: str = None, db=None):
        if not db:
            return
        try:
            await db.rpc("consume_tenant_credit", {
                "p_org_id": org_id, "p_credit_type": credit_type.value,
                "p_amount": amount, "p_user_id": user_id
            }).execute()
        except Exception as e:
            logger.error(f"Failed to persist: {e}")


tenant_credit_service = TenantCreditService()
