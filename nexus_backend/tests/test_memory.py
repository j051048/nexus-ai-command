"""Tests for agent memory — persist_result with org_id passthrough."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestPersistResult:
    """Tests for persist_result org_id passthrough to save_message."""

    @pytest.mark.asyncio
    async def test_persist_result_passes_org_id(self):
        """persist_result forwards org_id to both save_message calls."""
        from app.agent.memory import persist_result

        calls = []
        original_save = AsyncMock(side_effect=lambda **kwargs: calls.append(kwargs))

        with patch("app.agent.memory.ChatService") as MockChatService:
            MockChatService.save_message = original_save
            await persist_result(
                user_id="u1",
                session_id="s1",
                user_message="hello",
                assistant_response="hi there",
                agent_name="@助手",
                org_id="org-123",
            )

        assert len(calls) == 2
        # User message
        assert calls[0]["org_id"] == "org-123"
        assert calls[0]["role"] == "user"
        assert calls[0]["agent"] == "@助手"
        # Assistant message
        assert calls[1]["org_id"] == "org-123"
        assert calls[1]["role"] == "assistant"
        assert calls[1]["agent"] == "@助手"

    @pytest.mark.asyncio
    async def test_persist_result_none_org_id(self):
        """persist_result works without org_id (backward compat)."""
        from app.agent.memory import persist_result

        calls = []
        original_save = AsyncMock(side_effect=lambda **kwargs: calls.append(kwargs))

        with patch("app.agent.memory.ChatService") as MockChatService:
            MockChatService.save_message = original_save
            await persist_result(
                user_id="u1",
                session_id="s1",
                user_message="hello",
                assistant_response="hi",
            )

        assert len(calls) == 2
        assert calls[0]["org_id"] is None
        assert calls[1]["org_id"] is None

    @pytest.mark.asyncio
    async def test_persist_result_save_failure_non_fatal(self):
        """persist_result doesn't crash if save_message raises."""
        from app.agent.memory import persist_result

        with patch("app.agent.memory.ChatService") as MockChatService:
            MockChatService.save_message = AsyncMock(side_effect=Exception("DB down"))
            # Should not raise
            await persist_result(
                user_id="u1",
                session_id="s1",
                user_message="hello",
                assistant_response="hi",
                org_id="org-123",
            )

    @pytest.mark.asyncio
    async def test_persist_result_triggers_semantic_cache(self):
        """persist_result updates semantic cache when both messages present."""
        from app.agent.memory import persist_result

        mock_cache = AsyncMock()

        with (
            patch("app.agent.memory.ChatService") as MockChatService,
            patch("app.services.semantic_cache.semantic_cache_service") as mock_sc,
        ):
            MockChatService.save_message = AsyncMock()
            mock_sc.set_cache = mock_cache
            await persist_result(
                user_id="u1",
                session_id="s1",
                user_message="What is 2+2?",
                assistant_response="4",
            )

        mock_cache.assert_awaited_once_with("What is 2+2?", "4", "u1")

    @pytest.mark.asyncio
    async def test_persist_result_extracts_org_memories(self):
        """persist_result extracts org-level memories when org_id is provided."""
        from app.agent.memory import persist_result

        mock_extract = AsyncMock(return_value=["memory1"])

        with (
            patch("app.agent.memory.ChatService") as MockChatService,
            patch(
                "app.services.conversation_memory_service.conversation_memory_service"
            ) as mock_mem,
        ):
            MockChatService.save_message = AsyncMock()
            mock_mem.extract_preferences = AsyncMock(return_value=[])
            mock_mem.extract_org_memories = mock_extract
            await persist_result(
                user_id="u1",
                session_id="s1",
                user_message="Our company policy is...",
                assistant_response="Got it",
                org_id="org-456",
            )

        mock_extract.assert_awaited_once()
        call_kwargs = mock_extract.call_args[1]
        assert call_kwargs["org_id"] == "org-456"
        assert call_kwargs["user_id"] == "u1"
