"""
Tests for rate limiter — token bucket algorithm, memory cleanup, IP extraction.
"""

import time
from unittest.mock import MagicMock

import pytest

from app.core.rate_limiter import RateLimiter


def _make_request(ip: str = "127.0.0.1", forwarded_for: str | None = None) -> MagicMock:
    """Create a mock FastAPI request."""
    request = MagicMock()
    request.client = MagicMock()
    request.client.host = ip
    headers = {}
    if forwarded_for:
        headers["X-Forwarded-For"] = forwarded_for
    request.headers = headers
    return request


class TestTokenBucket:
    """Test core token bucket algorithm."""

    def test_allows_requests_under_limit(self):
        limiter = RateLimiter(rate=10, burst=5, prefix="test")
        request = _make_request()

        # Should allow burst number of requests immediately
        for i in range(5):
            allowed, meta = limiter._check_memory(limiter._get_key(request))
            assert allowed, f"Request {i+1} should be allowed"

    def test_rejects_after_burst_exhausted(self):
        limiter = RateLimiter(rate=10, burst=3, prefix="test2")
        request = _make_request()
        key = limiter._get_key(request)

        # Exhaust burst
        for _ in range(3):
            limiter._check_memory(key)

        # Next request should be rejected
        allowed, meta = limiter._check_memory(key)
        assert not allowed
        assert meta["remaining"] == 0

    def test_tokens_refill_over_time(self):
        limiter = RateLimiter(rate=60, burst=5, prefix="test3")
        request = _make_request()
        key = limiter._get_key(request)

        # Exhaust all tokens
        for _ in range(5):
            limiter._check_memory(key)

        # Simulate 2 seconds passing (60 req/min = 1 req/sec, so 2 tokens refill)
        limiter.last_update[key] -= 2.0

        allowed, meta = limiter._check_memory(key)
        assert allowed, "Should have refilled tokens after time passed"

    def test_burst_cap_enforced(self):
        limiter = RateLimiter(rate=60, burst=3, prefix="test4")
        request = _make_request()
        key = limiter._get_key(request)

        # Simulate long idle time (should cap at burst, not accumulate infinitely)
        limiter.last_update[key] -= 3600  # 1 hour idle

        allowed, meta = limiter._check_memory(key)
        assert allowed
        # After consuming 1, remaining should be at most burst-1
        assert meta["remaining"] <= 2

    def test_metadata_contains_required_fields(self):
        limiter = RateLimiter(rate=30, burst=5, prefix="test5")
        request = _make_request()
        key = limiter._get_key(request)

        allowed, meta = limiter._check_memory(key)
        assert "remaining" in meta
        assert "limit" in meta
        assert "reset" in meta
        assert meta["limit"] == 30


class TestIPExtraction:
    """Test IP extraction with X-Forwarded-For handling."""

    def test_direct_ip_when_no_proxy(self):
        limiter = RateLimiter(rate=10, burst=5, prefix="ip_test")
        request = _make_request(ip="192.168.1.100")
        key = limiter._get_key(request)
        assert "192.168.1.100" in key

    def test_forwarded_for_with_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr("app.core.rate_limiter.TRUSTED_PROXY_COUNT", 1)
        limiter = RateLimiter(rate=10, burst=5, prefix="ip_test2")
        # X-Forwarded-For: client, proxy1 — with 1 trusted proxy, pick entry at index max(0, 2-1)=1
        request = _make_request(ip="10.0.0.1", forwarded_for="203.0.113.50, 10.0.0.1")
        key = limiter._get_key(request)
        # Algorithm: index = max(0, len(parts) - TRUSTED_PROXY_COUNT) = max(0, 2-1) = 1 → "10.0.0.1"
        assert "10.0.0.1" in key

    def test_forwarded_for_spoofing_prevented(self, monkeypatch):
        monkeypatch.setattr("app.core.rate_limiter.TRUSTED_PROXY_COUNT", 1)
        limiter = RateLimiter(rate=10, burst=5, prefix="ip_test3")
        # Attacker injects fake IP: "fake, real_client, proxy"
        request = _make_request(ip="10.0.0.1", forwarded_for="1.2.3.4, 203.0.113.50, 10.0.0.1")
        key = limiter._get_key(request)
        # index = max(0, 3-1) = 2 → picks "10.0.0.1" (the proxy-appended IP)
        assert "10.0.0.1" in key

    def test_no_proxy_trust_ignores_forwarded_for(self, monkeypatch):
        monkeypatch.setattr("app.core.rate_limiter.TRUSTED_PROXY_COUNT", 0)
        limiter = RateLimiter(rate=10, burst=5, prefix="ip_test4")
        request = _make_request(ip="10.0.0.1", forwarded_for="203.0.113.50")
        key = limiter._get_key(request)
        assert "10.0.0.1" in key


class TestMemoryCleanup:
    """Test stale entry eviction to prevent memory leaks."""

    def test_evicts_stale_entries_when_over_limit(self):
        limiter = RateLimiter(rate=60, burst=10, prefix="cleanup")

        # Simulate 10001 entries with old timestamps
        now = time.time()
        for i in range(10001):
            key = f"cleanup:ip:192.168.1.{i % 256}"
            limiter.tokens[key] = 10.0
            limiter.last_update[key] = now - 7200  # 2 hours ago (stale)

        # Add one fresh entry
        fresh_key = "cleanup:ip:fresh"
        limiter.tokens[fresh_key] = 10.0
        limiter.last_update[fresh_key] = now

        # Trigger cleanup via _check_memory
        request = _make_request(ip="trigger_cleanup")
        limiter._check_memory(limiter._get_key(request))

        # Stale entries should be evicted
        assert len(limiter.last_update) < 10001

    def test_user_based_key_generation(self):
        limiter = RateLimiter(rate=10, burst=5, prefix="user")
        request = _make_request()
        key = limiter._get_key(request, user_id="user-123")
        assert "user:user-123" in key


class TestReset:
    """Test rate limiter reset functionality."""

    def test_reset_restores_burst(self):
        limiter = RateLimiter(rate=10, burst=5, prefix="reset")
        request = _make_request()
        key = limiter._get_key(request)

        # Exhaust tokens
        for _ in range(5):
            limiter._check_memory(key)

        allowed, _ = limiter._check_memory(key)
        assert not allowed

        # Reset
        limiter.reset(request)

        # Should be allowed again
        allowed, _ = limiter._check_memory(key)
        assert allowed
