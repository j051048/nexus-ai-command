"""Reasoning model <think> tag stripping utilities.

Extracted from stream.py to eliminate circular imports — node_reflect.py and
node_respond.py both need these helpers but should not depend on the heavy
streaming module.
"""

import re

# Regex for complete <think>...</think> blocks (non-greedy, DOTALL)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_think_tags(text: str) -> str:
    """Remove all <think>...</think> blocks from text."""
    if not text or "<think>" not in text and "</think>" not in text:
        return text
    # Remove complete blocks
    cleaned = _THINK_BLOCK_RE.sub("", text)
    # Remove orphan opening/closing tags (partial streaming artifacts)
    cleaned = cleaned.replace("<think>", "").replace("</think>", "")
    return cleaned.lstrip("\n")


def extract_clean_content(msg) -> str:
    """Extract clean response content from an AIMessage, stripping reasoning.

    Handles three cases:
    1. reasoning_content in additional_kwargs (OpenAI o1, Stepfun step-3.5-flash)
    2. <think>...</think> blocks in content (DeepSeek-R1, QwQ)
    3. Raw reasoning merged into content by proxy APIs

    For case 3, if reasoning_content is found in additional_kwargs and the main
    content starts with it (proxy merged them), strip the reasoning prefix.
    """
    content = msg.content or ""
    kwargs = getattr(msg, "additional_kwargs", {}) or {}

    # Case 1 & 3: reasoning_content stored separately by LangChain
    reasoning = kwargs.get("reasoning_content", "")
    if reasoning and content.startswith(reasoning):
        # Proxy API merged reasoning into content — strip the reasoning prefix
        content = content[len(reasoning):].lstrip("\n")

    # Case 2: <think> tags
    content = strip_think_tags(content)

    return content
