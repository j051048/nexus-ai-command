from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.memory.context_policy import choose_memory_context_policy
from app.services.conversation_memory.admission import (
    evaluate_memory_admission,
    sanitize_tool_arguments,
)
from app.services.conversation_memory.storage import (
    MemoryEncryptionError,
    _encrypt_value,
)
from app.services.memory_hygiene_service import MemoryHygieneService


def test_sensitive_memory_encryption_fails_closed():
    with patch(
        "app.services.encryption_service.encryption_service.encrypt",
        side_effect=ValueError("bad key"),
    ), pytest.raises(MemoryEncryptionError):
        _encrypt_value("private fact", "explicit_memory")


def test_admission_rejects_credentials():
    decision = evaluate_memory_admission(
        value="Authorization: Bearer abcdefghijklmnopqrstuvwxyz",
        category="explicit_memory",
        confidence=1.0,
        source="user_explicit",
        extraction_method="user_explicit",
        metadata=None,
        valid_until=None,
        evidence_ref=None,
    )
    assert not decision.allowed
    assert decision.sensitivity == "restricted"


def test_low_confidence_and_unsupported_calibration_are_quarantined():
    low_confidence = evaluate_memory_admission(
        value="Instrument may be drifting",
        category="fact",
        confidence=0.4,
        source="chat",
        extraction_method="llm",
        metadata=None,
        valid_until=None,
        evidence_ref=None,
    )
    calibration = evaluate_memory_admission(
        value="MS-01 baseline is 0.3 ppm",
        category="calibration_baseline",
        confidence=0.95,
        source="chat",
        extraction_method="llm",
        metadata=None,
        valid_until=None,
        evidence_ref=None,
    )
    assert low_confidence.lifecycle_state == "pending_review"
    assert calibration.lifecycle_state == "pending_review"


def test_tool_arguments_are_redacted_and_bounded():
    sanitized = sanitize_tool_arguments(
        {"customer_id": "c-1", "api_key": "secret", "notes": "x" * 900}
    )
    assert sanitized["customer_id"] == "c-1"
    assert sanitized["api_key"] == "[REDACTED]"
    assert len(sanitized["notes"]) == 500


def test_context_policy_skips_expensive_sources_for_simple_queries():
    simple = choose_memory_context_policy("你好")
    complex_query = choose_memory_context_policy(
        "分析上次仪器维修为什么失败并给下一步计划", "complex"
    )
    assert simple.sources == ("l1", "l2")
    assert simple.token_budget == 900
    assert {"org", "kg", "patterns", "episodic", "reasoning"}.issubset(
        complex_query.sources
    )
    assert complex_query.token_budget == 1800


@pytest.mark.asyncio
async def test_hygiene_failure_reports_degraded_instead_of_false_healthy():
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    query.execute = AsyncMock(side_effect=RuntimeError("schema mismatch"))
    db = MagicMock()
    db.table.return_value = query

    result = await MemoryHygieneService().audit_memory_hygiene(
        db=db, user_id="u-1", org_id="o-1"
    )

    assert result["status"] == "degraded"
    assert result["hygiene_score"] == 0
    assert result["error"] == "RuntimeError"
