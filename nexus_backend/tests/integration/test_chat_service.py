"""Tests for chat_service: prompt loading, save_message with org_id."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chat_service import ChatService


class TestSystemPrompt:
    @pytest.mark.asyncio
    async def test_get_system_prompt_default(self):
        prompt = await ChatService.get_system_prompt("default_fallback")
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.asyncio
    async def test_get_system_prompt_sales(self):
        prompt = await ChatService.get_system_prompt("sales_commander")
        assert isinstance(prompt, str)

    @pytest.mark.asyncio
    async def test_get_system_prompt_approval(self):
        prompt = await ChatService.get_system_prompt("approval_manager")
        assert isinstance(prompt, str)

    @pytest.mark.asyncio
    async def test_get_system_prompt_unknown_fallback(self):
        prompt = await ChatService.get_system_prompt("nonexistent_agent_xyz")
        assert isinstance(prompt, str)
        assert len(prompt) > 0  # Should fall back to default


class TestAgentPhase:
    def test_phase_values(self):
        from app.agent.state import AgentPhase

        assert AgentPhase.PLANNING.value is not None
        assert AgentPhase.EXECUTING.value is not None
        assert AgentPhase.REFLECTING.value is not None
        assert AgentPhase.RESPONDING.value is not None


class TestThinkingStep:
    def test_thinking_step_creation(self):
        from app.agent.state import ThinkingStep

        step = ThinkingStep(
            phase="planning",
            content="Analyzing user intent...",
            tool_name="search_tool",
        )
        assert step.phase == "planning"
        assert step.content == "Analyzing user intent..."
        assert step.tool_name == "search_tool"


class TestSaveMessage:
    """Tests for ChatService.save_message with org_id and agent support."""

    def _make_mock_supabase(self):
        """Create a mock supabase that captures inserted data."""
        captured = {}
        mock_execute = AsyncMock()

        class MockInsertChain:
            def __init__(self, data):
                captured.update(data)

            async def execute(self):
                return await mock_execute()

        class MockTable:
            def insert(self, data):
                return MockInsertChain(data)

        mock_sb = MagicMock()
        mock_sb.table = MagicMock(return_value=MockTable())
        return mock_sb, captured, mock_execute

    @pytest.mark.asyncio
    async def test_save_message_basic(self):
        """save_message inserts with user_id, session_id, role, content."""
        mock_sb, captured, mock_execute = self._make_mock_supabase()

        with patch("app.services.chat_service.supabase", mock_sb):
            await ChatService.save_message(
                user_id="u1",
                session_id="s1",
                role="user",
                content="hello",
            )
            assert captured["user_id"] == "u1"
            assert captured["session_id"] == "s1"
            assert captured["role"] == "user"
            assert captured["content"] == "hello"

    @pytest.mark.asyncio
    async def test_save_message_with_org_id(self):
        """save_message includes organization_id when org_id is provided."""
        mock_sb, captured, _ = self._make_mock_supabase()

        with patch("app.services.chat_service.supabase", mock_sb):
            await ChatService.save_message(
                user_id="u1",
                session_id="s1",
                role="assistant",
                content="response",
                org_id="org-abc",
            )
            assert captured["organization_id"] == "org-abc"
            assert captured["user_id"] == "u1"

    @pytest.mark.asyncio
    async def test_save_message_with_agent(self):
        """save_message includes agent field when provided."""
        mock_sb, captured, _ = self._make_mock_supabase()

        with patch("app.services.chat_service.supabase", mock_sb):
            await ChatService.save_message(
                user_id="u1",
                session_id="s1",
                role="user",
                content="hello",
                agent="@销售指挥官",
            )
            assert captured["agent"] == "@销售指挥官"

    @pytest.mark.asyncio
    async def test_save_message_without_optional_fields(self):
        """save_message omits org_id and agent when not provided."""
        mock_sb, captured, _ = self._make_mock_supabase()

        with patch("app.services.chat_service.supabase", mock_sb):
            await ChatService.save_message(
                user_id="u1",
                session_id="s1",
                role="user",
                content="test",
            )
            assert "organization_id" not in captured
            assert "agent" not in captured

    @pytest.mark.asyncio
    async def test_save_message_error_handling(self):
        """save_message logs error but doesn't raise on failure."""
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("DB down")

        with patch("app.services.chat_service.supabase", mock_sb):
            # Should not raise
            await ChatService.save_message(
                user_id="u1",
                session_id="s1",
                role="user",
                content="test",
            )
