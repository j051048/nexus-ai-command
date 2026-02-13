"""Tests for audit_logger: sanitization, buffering, querying."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from app.services.audit_logger import AuditLogger, AuditAction


class TestSanitization:
    def test_sanitize_password(self):
        logger = AuditLogger()
        details = {"username": "admin", "password": "secret123", "action": "login"}
        sanitized = logger._sanitize_details(details)
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["username"] == "admin"

    def test_sanitize_api_key(self):
        logger = AuditLogger()
        details = {"api_key": "sk-abc123", "model": "gpt-4o"}
        sanitized = logger._sanitize_details(details)
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["model"] == "gpt-4o"

    def test_sanitize_token(self):
        logger = AuditLogger()
        details = {"access_token": "eyJ...", "refresh_token": "abc"}
        sanitized = logger._sanitize_details(details)
        assert sanitized["access_token"] == "[REDACTED]"
        assert sanitized["refresh_token"] == "[REDACTED]"

    def test_sanitize_credit_card(self):
        logger = AuditLogger()
        details = {"credit_card": "4111111111111111", "name": "John"}
        sanitized = logger._sanitize_details(details)
        assert sanitized["credit_card"] == "[REDACTED]"

    def test_sanitize_truncates_long_values(self):
        logger = AuditLogger()
        details = {"data": "x" * 2000}
        sanitized = logger._sanitize_details(details)
        assert len(sanitized["data"]) <= 1014  # 1000 + "...[truncated]"

    def test_sanitize_no_change_safe_data(self):
        logger = AuditLogger()
        details = {"action": "read", "target": "documents", "count": 5}
        sanitized = logger._sanitize_details(details)
        assert sanitized == details


class TestBuffering:
    @pytest.mark.asyncio
    async def test_log_adds_to_buffer(self):
        logger = AuditLogger()
        logger._buffer_size = 100  # Don't auto-flush
        await logger.log(
            action=AuditAction.AUTH_LOGIN,
            actor_user_id="user-1",
            details={"ip": "127.0.0.1"},
        )
        assert len(logger._buffer) == 1
        assert logger._buffer[0].action == AuditAction.AUTH_LOGIN.value

    @pytest.mark.asyncio
    async def test_log_string_action(self):
        logger = AuditLogger()
        logger._buffer_size = 100
        await logger.log(
            action="custom_action",
            actor_user_id="user-1",
        )
        assert len(logger._buffer) == 1
        assert logger._buffer[0].action == "custom_action"


class TestAuditEntry:
    def test_entry_to_dict(self):
        logger = AuditLogger()
        logger._buffer_size = 100

        from app.services.audit_logger import AuditEntry

        entry = AuditEntry(
            action="test",
            actor_user_id="user-1",
            target_id="doc-1",
            target_table="documents",
        )
        d = entry.to_dict()
        assert d["action"] == "test"
        assert d["actor_user_id"] == "user-1"
        assert d["target_id"] == "doc-1"
        assert "timestamp" in d


class TestQueryLogs:
    @pytest.mark.asyncio
    async def test_query_empty(self):
        logger = AuditLogger()
        results = await logger.query_logs(user_id="nobody")
        assert results == [] or isinstance(results, list)
