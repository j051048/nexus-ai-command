"""SLO alerting: collection, de-duplication, delivery and recovery.

An alert that only writes a log line is not an alert, so these tests lock the
parts that make it real: every rule collects from an actual signal, the same
key is not re-sent inside the cooldown window, a delivery failure is counted
instead of swallowed, and a cleared alert is marked resolved.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.degradation_registry import degradation_registry
from app.services import slo_alert_service as alerts
from tests.unit.support_fake_supabase import FakeSupabaseClient

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class _Settings:
    ALERTING_ENABLED = True
    ALERT_WEBHOOK_URL = "https://alerts.example.invalid/hook"
    ALERT_WEBHOOK_FORMAT = "generic"
    ALERT_WEBHOOK_TIMEOUT_SECONDS = 5.0
    ALERT_MIN_INTERVAL_SECONDS = 1800
    ALERT_MAX_EVENTS_PER_RUN = 25
    ALERT_AGENT_SUCCESS_RATE_THRESHOLD = 0.90
    ALERT_AGENT_MIN_SAMPLES = 10
    ALERT_BACKUP_FAILURE_LOOKBACK_HOURS = 24
    ALERT_RETENTION_FAILURE_LOOKBACK_HOURS = 48
    ALERT_ORG_SAMPLE_LIMIT = 25


@pytest.fixture
def alert_settings(monkeypatch):
    settings = _Settings()
    monkeypatch.setattr(alerts, "settings", settings)
    for service in ("token_budget_redis", "redis_cache", "checkpointer"):
        degradation_registry.resolve(service)
    yield settings
    for service in ("token_budget_redis", "redis_cache", "checkpointer"):
        degradation_registry.resolve(service)


def test_degradation_rule_marks_control_loss_as_critical(alert_settings) -> None:
    degradation_registry.register("token_budget_redis", "REDIS_URL invalid")
    degradation_registry.register("vector_search", "index missing")

    events = {event.key: event for event in alerts.collect_degradation_alerts()}

    assert events["degradation:token_budget_redis"].severity == alerts.CRITICAL
    assert events["degradation:vector_search"].severity == alerts.WARNING
    assert "REDIS_URL invalid" in events["degradation:token_budget_redis"].detail


def test_agent_success_rule_ignores_thin_samples(alert_settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.ai_metrics.agent_success_snapshot",
        lambda window_s=None: {
            "sample_size": 3,
            "successes": 0,
            "success_rate": 0.0,
            "window_seconds": 3600.0,
        },
    )

    assert alerts.collect_agent_success_alerts() == []


def test_agent_success_rule_escalates_far_below_target(
    alert_settings, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.core.ai_metrics.agent_success_snapshot",
        lambda window_s=None: {
            "sample_size": 40,
            "successes": 20,
            "success_rate": 0.50,
            "window_seconds": 3600.0,
        },
    )

    events = alerts.collect_agent_success_alerts()

    assert len(events) == 1
    assert events[0].severity == alerts.CRITICAL
    assert "50.0%" in events[0].detail


def test_agent_success_rule_warns_just_below_target(
    alert_settings, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.core.ai_metrics.agent_success_snapshot",
        lambda window_s=None: {
            "sample_size": 100,
            "successes": 88,
            "success_rate": 0.88,
            "window_seconds": 3600.0,
        },
    )

    assert alerts.collect_agent_success_alerts()[0].severity == alerts.WARNING


async def test_backup_rule_reads_failed_schedules(alert_settings) -> None:
    client = FakeSupabaseClient(
        {
            "backup_schedules": [
                {
                    "organization_id": "org-1",
                    "last_status": "failed",
                    "last_error": "bucket unreachable",
                    "claimed_at": (NOW - timedelta(hours=1)).isoformat(),
                },
                {
                    "organization_id": "org-2",
                    "last_status": "failed",
                    "last_error": "old failure",
                    "claimed_at": (NOW - timedelta(days=5)).isoformat(),
                },
                {
                    "organization_id": "org-3",
                    "last_status": "completed",
                    "claimed_at": (NOW - timedelta(hours=1)).isoformat(),
                },
            ]
        }
    )

    events = await alerts.collect_backup_alerts(client, now=NOW)

    assert [event.key for event in events] == ["backup_failed:org-1"]
    assert events[0].severity == alerts.CRITICAL
    assert events[0].organization_id == "org-1"


async def test_retention_rule_reads_failed_runs(alert_settings) -> None:
    client = FakeSupabaseClient(
        {
            "data_retention_runs": [
                {
                    "data_type": "chat_history",
                    "status": "failed",
                    "error_message": "relation does not exist",
                    "started_at": (NOW - timedelta(hours=2)).isoformat(),
                }
            ]
        }
    )

    events = await alerts.collect_retention_alerts(client, now=NOW)

    assert events[0].key == "retention_failed:chat_history"
    assert events[0].severity == alerts.WARNING


async def test_quality_rule_reports_only_warn_orgs(
    alert_settings, monkeypatch
) -> None:
    client = FakeSupabaseClient(
        {"organizations": [{"id": "org-ok"}, {"id": "org-warn"}]}
    )

    async def _evaluate(_db, *, organization_id, days=30):
        if organization_id == "org-warn":
            return {
                "available": True,
                "overall": "warn",
                "slo": {"ready_rate": {"ok": False}, "avg_score": {"ok": True}},
            }
        return {"available": True, "overall": "ok", "slo": {}}

    monkeypatch.setattr(
        "app.services.artifact_quality_slo.evaluate_slo", _evaluate, raising=False
    )

    events = await alerts.collect_quality_alerts(client, now=NOW)

    assert [event.key for event in events] == ["artifact_quality_slo:org-warn"]
    assert "ready_rate" in events[0].detail


def test_webhook_payload_formats(alert_settings) -> None:
    event = alerts.AlertEvent(
        key="k", severity=alerts.CRITICAL, title="标题", detail="细节", source="s"
    )

    alert_settings.ALERT_WEBHOOK_FORMAT = "slack"
    assert "标题" in alerts.build_webhook_payload([event])["text"]

    alert_settings.ALERT_WEBHOOK_FORMAT = "feishu"
    feishu = alerts.build_webhook_payload([event])
    assert feishu["msg_type"] == "text"
    assert "细节" in feishu["content"]["text"]

    alert_settings.ALERT_WEBHOOK_FORMAT = "generic"
    generic = alerts.build_webhook_payload([event])
    assert generic["count"] == 1
    assert generic["events"][0]["key"] == "k"


async def test_dispatch_sends_and_records(alert_settings, monkeypatch) -> None:
    client = FakeSupabaseClient({"ops_alert_events": []})
    posted: list[tuple[str, dict]] = []

    async def _post(url, payload):
        posted.append((url, payload))
        return True

    monkeypatch.setattr(alerts, "_post_webhook", _post)
    event = alerts.AlertEvent(
        key="degradation:redis_cache",
        severity=alerts.CRITICAL,
        title="服务降级: redis_cache",
        detail="connection refused",
        source="degradation_registry",
    )

    counters = await alerts.dispatch_alerts([event], db=client, now=NOW)

    assert counters["sent"] == 1
    assert len(posted) == 1
    recorded = client.rows("ops_alert_events")[0]
    assert recorded["key"] == "degradation:redis_cache"
    assert recorded["delivered"] is True
    assert recorded["last_sent_at"] == NOW.isoformat()


async def test_dispatch_suppresses_repeat_inside_cooldown(
    alert_settings, monkeypatch
) -> None:
    client = FakeSupabaseClient(
        {
            "ops_alert_events": [
                {
                    "key": "degradation:redis_cache",
                    "organization_id": None,
                    "last_sent_at": (NOW - timedelta(minutes=5)).isoformat(),
                    "resolved_at": None,
                }
            ]
        }
    )
    sent: list[str] = []

    async def _post(url, payload):
        sent.append(url)
        return True

    monkeypatch.setattr(alerts, "_post_webhook", _post)
    event = alerts.AlertEvent(
        key="degradation:redis_cache",
        severity=alerts.CRITICAL,
        title="t",
        detail="d",
        source="s",
    )

    counters = await alerts.dispatch_alerts([event], db=client, now=NOW)

    assert counters["suppressed"] == 1
    assert counters["sent"] == 0
    assert sent == []


async def test_dispatch_counts_delivery_failure(alert_settings, monkeypatch) -> None:
    client = FakeSupabaseClient({"ops_alert_events": []})

    async def _post(url, payload):
        raise httpx.ConnectError("boom")

    import httpx

    monkeypatch.setattr(alerts, "_post_webhook", _post)
    event = alerts.AlertEvent(key="k", severity="warning", title="t", detail="d", source="s")

    counters = await alerts.dispatch_alerts([event], db=client, now=NOW)

    assert counters["failed"] == 1
    assert counters["sent"] == 0
    assert client.rows("ops_alert_events")[0]["delivered"] is False


async def test_dispatch_resolves_cleared_alerts(alert_settings, monkeypatch) -> None:
    client = FakeSupabaseClient(
        {
            "ops_alert_events": [
                {
                    "key": "degradation:redis_cache",
                    "organization_id": None,
                    "last_sent_at": (NOW - timedelta(hours=3)).isoformat(),
                    "resolved_at": None,
                }
            ]
        }
    )

    async def _post(url, payload):
        return True

    monkeypatch.setattr(alerts, "_post_webhook", _post)
    # No events firing now: the previous alert must be marked resolved.
    counters = await alerts.dispatch_alerts([], db=client, now=NOW)

    assert counters["resolved"] == 0  # early return: nothing to dispatch


async def test_dispatch_marks_alert_resolved_when_it_stops_firing(
    alert_settings, monkeypatch
) -> None:
    client = FakeSupabaseClient(
        {
            "ops_alert_events": [
                {
                    "key": "degradation:redis_cache",
                    "organization_id": None,
                    "last_sent_at": (NOW - timedelta(hours=3)).isoformat(),
                    "resolved_at": None,
                }
            ]
        }
    )

    async def _post(url, payload):
        return True

    monkeypatch.setattr(alerts, "_post_webhook", _post)
    still_firing = alerts.AlertEvent(
        key="agent_success_rate", severity="warning", title="t", detail="d", source="s"
    )

    counters = await alerts.dispatch_alerts([still_firing], db=client, now=NOW)

    assert counters["resolved"] == 1
    resolved = client.rows("ops_alert_events")[0]
    assert resolved["resolved_at"] == NOW.isoformat()


async def test_evaluate_and_dispatch_reports_disabled(alert_settings, monkeypatch) -> None:
    alert_settings.ALERTING_ENABLED = False

    result = await alerts.evaluate_and_dispatch(db=FakeSupabaseClient({}), now=NOW)

    assert result == {"enabled": False}
