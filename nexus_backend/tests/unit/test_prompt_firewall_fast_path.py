"""Prompt firewall fast-path tests."""

import pytest

from app.core.prompt_firewall import PromptFirewall


@pytest.mark.asyncio
async def test_context_overflow_does_not_call_llm_judge(monkeypatch):
    fw = PromptFirewall()

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("LLM judge should not run for context-overflow input")

    monkeypatch.setattr(fw, "_llm_judge", fail_if_called)

    result = await fw.scan_input("normal business request " * 500)

    assert result.violations
    assert any(v.layer == "context_overflow" for v in result.violations)
