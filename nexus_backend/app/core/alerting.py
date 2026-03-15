"""
Alerting Rules Engine — 告警规则引擎

基于 Redis 计数器评估告警规则，支持:
- 预定义告警规则（5xx 率、延迟、断路器、认证失败、LLM 错误等）
- 告警去重（同一告警 15 分钟内不重复触发）
- 多通知渠道: log（默认）、webhook（可配置）、email（可配置）
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  Data Models
# ═══════════════════════════════════════════════════════════════════════════════


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class NotificationChannel(str, Enum):
    LOG = "log"
    WEBHOOK = "webhook"
    EMAIL = "email"


@dataclass
class AlertRule:
    """告警规则定义"""

    name: str
    condition: str  # 人可读的条件描述
    threshold: float  # 触发阈值
    window_seconds: int  # 评估时间窗口（秒）
    severity: Severity
    notification_channel: NotificationChannel = NotificationChannel.LOG
    # Redis key pattern used to evaluate this rule
    redis_counter_key: str = ""
    # Optional secondary key for ratio-based rules (e.g., total requests)
    redis_denominator_key: str = ""
    # Whether threshold is a ratio (0-1) or an absolute count
    is_ratio: bool = False


@dataclass
class AlertEvent:
    """已触发的告警事件"""

    rule_name: str
    severity: Severity
    message: str
    value: float
    threshold: float
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
#  Pre-defined Alert Rules
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_RULES: list[AlertRule] = [
    AlertRule(
        name="high_5xx_rate",
        condition=">5% of requests returning 5xx in 5 min window",
        threshold=0.05,
        window_seconds=300,
        severity=Severity.CRITICAL,
        notification_channel=NotificationChannel.WEBHOOK,
        redis_counter_key="metrics:http_5xx_count",
        redis_denominator_key="metrics:http_request_count",
        is_ratio=True,
    ),
    AlertRule(
        name="high_latency",
        condition="P95 latency >5s in 5 min window",
        threshold=5.0,
        window_seconds=300,
        severity=Severity.WARNING,
        notification_channel=NotificationChannel.LOG,
        redis_counter_key="metrics:http_p95_latency",
        is_ratio=False,
    ),
    AlertRule(
        name="circuit_breaker_open",
        condition="Any circuit breaker opens",
        threshold=1,
        window_seconds=300,
        severity=Severity.CRITICAL,
        notification_channel=NotificationChannel.WEBHOOK,
        redis_counter_key="metrics:circuit_breaker_open_count",
        is_ratio=False,
    ),
    AlertRule(
        name="auth_failure_spike",
        condition=">50 auth failures in 5 min",
        threshold=50,
        window_seconds=300,
        severity=Severity.CRITICAL,
        notification_channel=NotificationChannel.WEBHOOK,
        redis_counter_key="metrics:auth_failure_count",
        is_ratio=False,
    ),
    AlertRule(
        name="llm_error_rate",
        condition=">10% LLM call failures in 10 min",
        threshold=0.10,
        window_seconds=600,
        severity=Severity.WARNING,
        notification_channel=NotificationChannel.LOG,
        redis_counter_key="metrics:llm_error_count",
        redis_denominator_key="metrics:llm_call_count",
        is_ratio=True,
    ),
    AlertRule(
        name="rate_limit_exhaustion",
        condition=">100 rate-limited requests in 5 min",
        threshold=100,
        window_seconds=300,
        severity=Severity.WARNING,
        notification_channel=NotificationChannel.LOG,
        redis_counter_key="metrics:rate_limited_count",
        is_ratio=False,
    ),
    AlertRule(
        name="websocket_connection_spike",
        condition=">800 connections (80% of 1000 limit)",
        threshold=800,
        window_seconds=300,
        severity=Severity.WARNING,
        notification_channel=NotificationChannel.WEBHOOK,
        redis_counter_key="metrics:ws_active_connections",
        is_ratio=False,
    ),
    AlertRule(
        name="memory_usage_high",
        condition=">85% memory usage",
        threshold=0.85,
        window_seconds=300,
        severity=Severity.WARNING,
        notification_channel=NotificationChannel.LOG,
        redis_counter_key="metrics:memory_usage_pct",
        is_ratio=False,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
#  Alert Manager
# ═══════════════════════════════════════════════════════════════════════════════


class AlertManager:
    """
    告警管理器 — 基于 Redis 计数器评估规则并触发通知。

    Features:
    - 从 Redis 读取指标计数器
    - 按规则判断是否超阈值
    - 去重: 同名告警 15 分钟内不重复触发
    - 通知: log (always), webhook (configurable), email (configurable)
    """

    # 告警去重间隔（秒）
    DEDUP_WINDOW_SECONDS = 900  # 15 minutes

    def __init__(
        self,
        redis_client=None,
        rules: list[AlertRule] | None = None,
        webhook_url: str | None = None,
        email_config: dict[str, str] | None = None,
    ):
        self._redis = redis_client
        self._rules = rules or DEFAULT_RULES
        self._webhook_url = webhook_url
        self._email_config = email_config
        # In-memory dedup tracker: rule_name -> last_fired_timestamp
        self._last_fired: dict[str, float] = {}

    @property
    def rules(self) -> list[AlertRule]:
        return self._rules

    async def evaluate_all(self) -> list[AlertEvent]:
        """评估所有规则，返回触发的告警事件列表"""
        fired: list[AlertEvent] = []

        for rule in self._rules:
            try:
                event = await self._evaluate_rule(rule)
                if event and self._should_fire(event):
                    self._last_fired[event.rule_name] = event.timestamp
                    fired.append(event)
                    await self._notify(event)
            except Exception:
                logger.exception(f"Error evaluating alert rule: {rule.name}")

        return fired

    async def evaluate_rule_by_name(self, name: str) -> AlertEvent | None:
        """按名称评估单条规则"""
        for rule in self._rules:
            if rule.name == name:
                return await self._evaluate_rule(rule)
        return None

    async def _evaluate_rule(self, rule: AlertRule) -> AlertEvent | None:
        """评估单条规则，超阈值时返回 AlertEvent"""
        if not self._redis:
            logger.debug(f"No Redis client, skipping rule: {rule.name}")
            return None

        try:
            value = await self._get_metric_value(rule)
        except Exception:
            logger.exception(f"Failed to read metric for rule: {rule.name}")
            return None

        if value is None:
            return None

        exceeded = value > rule.threshold if not rule.is_ratio else value > rule.threshold
        if not exceeded:
            return None

        return AlertEvent(
            rule_name=rule.name,
            severity=rule.severity,
            message=f"[{rule.severity.value.upper()}] {rule.name}: {rule.condition} "
                    f"(current={value:.4f}, threshold={rule.threshold})",
            value=value,
            threshold=rule.threshold,
            metadata={"window_seconds": rule.window_seconds},
        )

    async def _get_metric_value(self, rule: AlertRule) -> float | None:
        """从 Redis 读取指标值"""
        raw = await self._redis.get(rule.redis_counter_key)
        if raw is None:
            return None

        numerator = float(raw)

        if rule.is_ratio and rule.redis_denominator_key:
            denom_raw = await self._redis.get(rule.redis_denominator_key)
            if not denom_raw:
                return None
            denominator = float(denom_raw)
            if denominator == 0:
                return None
            return numerator / denominator

        return numerator

    def _should_fire(self, event: AlertEvent) -> bool:
        """去重检查: 同名告警在 DEDUP_WINDOW_SECONDS 内不重复触发"""
        last = self._last_fired.get(event.rule_name)
        if last is None:
            return True
        return (event.timestamp - last) >= self.DEDUP_WINDOW_SECONDS

    # ── Notification Methods ──

    async def _notify(self, event: AlertEvent) -> None:
        """发送通知 — log 始终输出，webhook/email 按配置"""
        # Always log
        self._notify_log(event)

        # Find the rule to check notification channel
        rule = next((r for r in self._rules if r.name == event.rule_name), None)
        if not rule:
            return

        if rule.notification_channel == NotificationChannel.WEBHOOK and self._webhook_url:
            await self._notify_webhook(event)

        if rule.notification_channel == NotificationChannel.EMAIL and self._email_config:
            await self._notify_email(event)

    def _notify_log(self, event: AlertEvent) -> None:
        """日志通知（始终执行）"""
        log_fn = logger.critical if event.severity == Severity.CRITICAL else logger.warning
        log_fn(
            f"ALERT FIRED: {event.message}",
            extra={
                "alert_name": event.rule_name,
                "alert_severity": event.severity.value,
                "alert_value": event.value,
                "alert_threshold": event.threshold,
            },
        )

    async def _notify_webhook(self, event: AlertEvent) -> None:
        """Webhook 通知"""
        if not self._webhook_url:
            return

        try:
            import httpx

            payload = {
                "alert_name": event.rule_name,
                "severity": event.severity.value,
                "message": event.message,
                "value": event.value,
                "threshold": event.threshold,
                "timestamp": event.timestamp,
                "metadata": event.metadata,
            }

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    self._webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code >= 400:
                    logger.error(f"Webhook notification failed: {resp.status_code}")
        except Exception:
            logger.exception("Failed to send webhook notification")

    async def _notify_email(self, event: AlertEvent) -> None:
        """Email 通知（占位实现，可接入 SMTP 或第三方邮件服务）"""
        if not self._email_config:
            return

        recipient = self._email_config.get("recipient", "")
        logger.info(
            f"EMAIL ALERT to {recipient}: {event.message}",
            extra={"alert_name": event.rule_name},
        )
        # Actual SMTP / SES / SendGrid integration would go here

    # ── Metric Increment Helpers ──

    async def increment_counter(self, key: str, amount: int = 1, ttl: int = 600) -> None:
        """递增 Redis 计数器，自动设置过期时间"""
        if not self._redis:
            return
        pipe = self._redis.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, ttl)
        await pipe.execute()

    async def set_gauge(self, key: str, value: float, ttl: int = 600) -> None:
        """设置 Redis gauge 指标值"""
        if not self._redis:
            return
        await self._redis.set(key, str(value), ex=ttl)


# ═══════════════════════════════════════════════════════════════════════════════
#  Module-level singleton (lazy init)
# ═══════════════════════════════════════════════════════════════════════════════

_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """获取全局 AlertManager 实例（单例）"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


def init_alert_manager(
    redis_client=None,
    webhook_url: str | None = None,
    email_config: dict[str, str] | None = None,
) -> AlertManager:
    """初始化全局 AlertManager（通常在 app startup 时调用）"""
    global _alert_manager
    _alert_manager = AlertManager(
        redis_client=redis_client,
        webhook_url=webhook_url,
        email_config=email_config,
    )
    logger.info(f"AlertManager initialized with {len(_alert_manager.rules)} rules")
    return _alert_manager
