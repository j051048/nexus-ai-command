"""LLM interaction utilities for memory operations.

Key utilities:
- ID mapping to prevent LLM hallucination of UUIDs
- JSON parsing helpers for LLM responses
"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def prepare_memories_for_llm(
    memories: list[dict],
    *,
    text_field: str = "value",
    extra_fields: tuple[str, ...] = ("category",),
) -> tuple[list[dict], dict[str, str]]:
    """将真实 UUID 映射为简单整数 ID，防止 LLM 幻觉。

    LLM 看到的是 ``{"id": "0", "text": "..."}`` 而不是真实 UUID，
    大幅降低 LLM 编造 / 混淆 ID 的概率。

    Args:
        memories: 包含 ``id`` 字段的记忆列表
        text_field: 记忆文本内容所在的字段名
        extra_fields: 需要一并传给 LLM 的额外字段

    Returns:
        (safe_memories, id_mapping):
            safe_memories — 适合发给 LLM 的记忆列表（整数 ID）
            id_mapping — ``{str(idx): real_uuid}`` 映射表
    """
    id_mapping: dict[str, str] = {}
    safe_memories: list[dict] = []

    for idx, mem in enumerate(memories):
        real_id = str(mem.get("id", ""))
        id_mapping[str(idx)] = real_id

        safe_item: dict[str, Any] = {
            "id": str(idx),
            "text": mem.get(text_field, ""),
        }
        for field in extra_fields:
            if field in mem:
                safe_item[field] = mem[field]

        safe_memories.append(safe_item)

    return safe_memories, id_mapping


def restore_real_ids(
    llm_response: dict | list,
    id_mapping: dict[str, str],
) -> dict | list:
    """将 LLM 输出中的整数 ID 映射回真实 UUID。

    支持两种格式:
    - dict with ``memory`` key (Mem0 style)
    - list of items with ``id`` field
    """
    items: list[dict] = []

    if isinstance(llm_response, dict):
        items = llm_response.get("memory", [])
    elif isinstance(llm_response, list):
        items = llm_response

    for item in items:
        if not isinstance(item, dict):
            continue
        fake_id = str(item.get("id", ""))
        if fake_id in id_mapping:
            item["id"] = id_mapping[fake_id]

    return llm_response


def parse_llm_json(text: str) -> Any:
    """从 LLM 回复中解析 JSON，处理 markdown 代码块和思维标签。

    Handles:
    - ```json ... ``` blocks
    - <think>...</think> tags
    - Raw JSON strings
    """
    if not text or not text.strip():
        return None

    clean = text.strip()

    # Remove <think>...</think> blocks
    clean = re.sub(r"<think>[\s\S]*?</think>", "", clean, flags=re.DOTALL).strip()

    # Remove markdown code block wrappers
    if "```json" in clean:
        clean = clean.split("```json")[1].split("```")[0].strip()
    elif "```" in clean:
        parts = clean.split("```")
        if len(parts) >= 3:
            clean = parts[1].strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        # Try to find JSON array or object in the text
        json_match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', clean)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

    logger.error(f"Failed to parse LLM JSON response: {text[:200]}...")
    return None
