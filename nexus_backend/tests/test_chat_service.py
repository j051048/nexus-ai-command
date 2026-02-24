"""Tests for chat_service: prompt loading, system prompt resolution."""

import pytest

from app.services.chat_service import ChatService


class TestSystemPrompt:
    @pytest.mark.asyncio
    async def test_get_system_prompt_default(self):
        service = ChatService()
        prompt = await service.get_system_prompt("default_fallback")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_get_system_prompt_sales(self):
        service = ChatService()
        prompt = await service.get_system_prompt("sales_commander")
        assert isinstance(prompt, str)

    @pytest.mark.asyncio
    async def test_get_system_prompt_approval(self):
        service = ChatService()
        prompt = await service.get_system_prompt("approval_manager")
        assert isinstance(prompt, str)

    @pytest.mark.asyncio
    async def test_get_system_prompt_unknown_fallback(self):
        service = ChatService()
        prompt = await service.get_system_prompt("nonexistent_agent_xyz")
        assert isinstance(prompt, str)
        assert len(prompt) > 0  # Should fall back to default


class TestAgentPhase:
    def test_phase_values(self):
        from app.services.chat_service import AgentPhase

        assert AgentPhase.PLANNING.value is not None
        assert AgentPhase.EXECUTING.value is not None
        assert AgentPhase.REFLECTING.value is not None
        assert AgentPhase.RESPONDING.value is not None


class TestThinkingStep:
    def test_thinking_step_creation(self):
        from app.services.chat_service import ThinkingStep

        step = ThinkingStep(
            phase="planning",
            content="Analyzing user intent...",
            tool_name="search_tool",
        )
        assert step.phase == "planning"
        assert step.content == "Analyzing user intent..."
        assert step.tool_name == "search_tool"
