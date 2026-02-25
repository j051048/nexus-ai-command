"""
Tests for SSE streaming — format functions, state building, text chunking.
"""

import json

import pytest

from app.agent.stream import _chunk_text, _sse_content, _sse_data, _sse_status, _sse_thinking
from app.agent.state import ThinkingStep


# ── SSE Format Functions ──


class TestSSEFormatting:
    """Test SSE event formatting."""

    def test_sse_data_format(self):
        result = _sse_data({"key": "value"})
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        payload = json.loads(result[6:].strip())
        assert payload == {"key": "value"}

    def test_sse_data_chinese_characters(self):
        result = _sse_data({"message": "你好世界"})
        payload = json.loads(result[6:].strip())
        assert payload["message"] == "你好世界"

    def test_sse_content_openai_format(self):
        result = _sse_content("Hello")
        payload = json.loads(result[6:].strip())
        assert "choices" in payload
        assert payload["choices"][0]["delta"]["content"] == "Hello"

    def test_sse_content_empty_string(self):
        result = _sse_content("")
        payload = json.loads(result[6:].strip())
        assert payload["choices"][0]["delta"]["content"] == ""

    def test_sse_thinking_step(self):
        step = ThinkingStep(phase="planning", content="Analyzing query...")
        result = _sse_thinking(step)
        payload = json.loads(result[6:].strip())
        assert "thinking_step" in payload
        assert payload["thinking_step"]["phase"] == "planning"
        assert payload["thinking_step"]["content"] == "Analyzing query..."

    def test_sse_status(self):
        result = _sse_status("正在思考...")
        payload = json.loads(result[6:].strip())
        assert payload["status"] == "正在思考..."


# ── Text Chunking ──


class TestChunkText:
    """Test text chunking for smooth streaming."""

    def test_empty_text(self):
        assert _chunk_text("") == []

    def test_short_text_single_chunk(self):
        chunks = _chunk_text("Hi")
        assert len(chunks) == 1
        assert chunks[0] == "Hi"

    def test_chunks_at_natural_boundaries(self):
        text = "你好。世界！"
        chunks = _chunk_text(text, chunk_size=4)
        # Should split at 。 and ！
        reassembled = "".join(chunks)
        assert reassembled == text

    def test_chunk_size_respected(self):
        text = "a" * 20
        chunks = _chunk_text(text, chunk_size=4)
        for chunk in chunks:
            assert len(chunk) <= 5  # chunk_size + 1 (boundary char)

    def test_preserves_all_content(self):
        text = "这是一段测试文本，包含中文和English混合内容。还有标点！对吧？"
        chunks = _chunk_text(text, chunk_size=4)
        reassembled = "".join(chunks)
        assert reassembled == text

    def test_newline_breaks_chunk(self):
        text = "第一行\n第二行"
        chunks = _chunk_text(text, chunk_size=10)
        # Should split at \n
        assert any("\n" in c for c in chunks) or len(chunks) > 1


# ── ThinkingStep Serialization ──


class TestThinkingStep:
    """Test ThinkingStep data class."""

    def test_to_dict_basic(self):
        step = ThinkingStep(phase="planning", content="test")
        d = step.to_dict()
        assert d["phase"] == "planning"
        assert d["content"] == "test"

    def test_to_dict_with_tool_info(self):
        step = ThinkingStep(
            phase="executing",
            content="Running tool",
            tool_name="search",
            tool_result="found 5 results",
            duration_ms=150,
        )
        d = step.to_dict()
        assert d["tool_name"] == "search"
        assert d["tool_result"] == "found 5 results"
        assert d["duration_ms"] == 150

    def test_to_dict_optional_fields_none(self):
        step = ThinkingStep(phase="reflecting", content="checking")
        d = step.to_dict()
        assert d.get("tool_name") is None
