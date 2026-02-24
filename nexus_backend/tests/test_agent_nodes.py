"""Tests for agent nodes: helper functions and node logic."""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.nodes import _messages_to_lc_format


class TestMessagesToLCFormat:
    def test_dict_system_message(self):
        msgs = [{"role": "system", "content": "You are helpful."}]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == "You are helpful."

    def test_dict_user_message(self):
        msgs = [{"role": "user", "content": "Hello"}]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 1
        assert isinstance(result[0], HumanMessage)

    def test_dict_assistant_message(self):
        msgs = [{"role": "assistant", "content": "Hi there"}]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 1
        assert isinstance(result[0], AIMessage)

    def test_dict_tool_message(self):
        msgs = [
            {
                "role": "tool",
                "content": "result data",
                "tool_call_id": "tc-1",
                "name": "search",
            }
        ]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 1
        assert isinstance(result[0], ToolMessage)
        assert result[0].tool_call_id == "tc-1"

    def test_passthrough_lc_messages(self):
        msgs = [HumanMessage(content="Already LC format")]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 1
        assert result[0] is msgs[0]

    def test_mixed_format(self):
        msgs = [
            {"role": "system", "content": "System prompt"},
            HumanMessage(content="User question"),
            {"role": "assistant", "content": "AI response"},
        ]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 3
        assert isinstance(result[0], SystemMessage)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)

    def test_empty_messages(self):
        result = _messages_to_lc_format([])
        assert result == []

    def test_unknown_role_skipped(self):
        msgs = [{"role": "unknown", "content": "skip me"}]
        result = _messages_to_lc_format(msgs)
        assert len(result) == 0
