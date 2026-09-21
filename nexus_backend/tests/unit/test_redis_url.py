"""Tests for redis URL normalization.

Regression guard for the production warning::

    [Stream] Token budget check failed (non-blocking):
        Redis URL must specify one of the following schemes
        (redis://, rediss://, unix://)
"""

from __future__ import annotations

import pytest

from app.core.redis_url import (
    describe_redis_url_problem,
    normalize_redis_url,
    redact_redis_url,
)


@pytest.mark.parametrize(
    "raw",
    [
        "redis://localhost:6379/0",
        "redis://default:secret@hkg1.clusters.zeabur.com:31000",
        "rediss://default:secret@host:31000/1",
        "unix:///var/run/redis/redis.sock",
    ],
)
def test_valid_urls_pass_through_untouched(raw: str) -> None:
    assert normalize_redis_url(raw) == raw
    assert describe_redis_url_problem(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "hkg1.clusters.zeabur.com:31000",
        "localhost:6379",
        "default:secret@hkg1.clusters.zeabur.com:31000",
        "redis.internal:6379/2",
    ],
)
def test_bare_host_port_targets_gain_the_redis_scheme(raw: str) -> None:
    assert normalize_redis_url(raw) == f"redis://{raw}"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "https://hkg1.clusters.zeabur.com:31000",
        "http://example.com",
        "amqp://guest:guest@rabbit:5672",
        "redis url with spaces",
        "://missing-scheme",
    ],
)
def test_unusable_values_are_rejected(raw: str | None) -> None:
    assert normalize_redis_url(raw) is None
    assert describe_redis_url_problem(raw) is not None


def test_valid_scheme_is_passed_through_even_if_the_rest_is_wrong() -> None:
    # redis-py owns deep URL validation; the shim only settles the scheme
    # question so callers can decide between degraded mode and an error.
    assert normalize_redis_url("redis://host:not-a-port") == "redis://host:not-a-port"


def test_http_url_is_reported_as_a_scheme_problem() -> None:
    problem = describe_redis_url_problem("https://cache.zeabur.com:31000")
    assert problem is not None
    assert "https://" in problem
    assert "redis://" in problem


def test_missing_url_reports_not_set() -> None:
    assert describe_redis_url_problem(None) == "REDIS_URL is not set"
    assert describe_redis_url_problem("") == "REDIS_URL is not set"


def test_normalization_tolerates_surrounding_whitespace() -> None:
    assert (
        normalize_redis_url("  redis://localhost:6379/0  ")
        == "redis://localhost:6379/0"
    )
    assert (
        normalize_redis_url("  hkg1.clusters.zeabur.com:31000  ")
        == "redis://hkg1.clusters.zeabur.com:31000"
    )


def test_redaction_never_leaks_the_password() -> None:
    raw = "rediss://default:super-secret@hkg1.clusters.zeabur.com:31000/1"
    redacted = redact_redis_url(raw)
    assert "super-secret" not in redacted
    assert "default" in redacted
    assert "hkg1.clusters.zeabur.com:31000/1" in redacted


def test_redaction_handles_missing_values() -> None:
    assert redact_redis_url(None) == "<unset>"
    assert redact_redis_url("") == "<empty>"
    assert redact_redis_url("redis://localhost:6379/0") == "redis://localhost:6379/0"
