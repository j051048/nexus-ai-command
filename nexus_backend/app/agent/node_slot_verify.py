"""
Slot Verification Node — DST (Dialog State Tracking) 槽位填充。

在 plan → execute 之间检查工具必填参数是否完整。
缺失参数时通过 ask_user 伪工具向用户追问，避免 LLM 幻觉填充。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.agent.state import AgentPhase, ThinkingStep, ToolCallRecord
from app.tools import get_tool

if TYPE_CHECKING:
    from app.agent.state import AgentState

logger = logging.getLogger(__name__)

# 伪工具不做槽位检查
_SKIP_TOOLS = frozenset({"ask_user", "compact_context"})

# JSON Schema type → ask_user field type 映射
_SCHEMA_TYPE_MAP = {
    "string": "text",
    "number": "number",
    "integer": "number",
    "boolean": "checkbox",
}

# 最大澄清轮次
_MAX_SLOT_ROUNDS = 3


def _build_fields_from_schema(
    tool_schema: dict, missing_keys: list[str],
) -> list[dict]:
    """从工具 JSON Schema 的 properties 构建 ask_user 表单字段。"""
    props = tool_schema.get("properties", {})
    fields: list[dict] = []

    for key in missing_keys:
        prop = props.get(key, {})
        field_type = _SCHEMA_TYPE_MAP.get(prop.get("type", "string"), "text")

        # enum → select
        if "enum" in prop:
            field_type = "select"

        field: dict = {
            "name": key,
            "label": prop.get("description") or key,
            "type": field_type,
            "required": True,
        }

        if field_type == "select" and "enum" in prop:
            field["options"] = prop["enum"]

        if "default" in prop:
            field["default_value"] = str(prop["default"])

        fields.append(field)

    return fields


async def slot_verify_node(state: AgentState, config=None) -> dict:
    """检查 pending_tool_calls 的必填参数，缺失则构建 ask_user 追问。

    Returns:
        dict with updated state fields. Key routing signals:
        - slot_context=None → 参数完整，直接进入 execute
        - slot_context={...} → 有缺失，通过 ask_user 追问用户
    """
    pending = state.get("pending_tool_calls", [])
    slot_round = state.get("slot_round", 0)

    if not pending:
        return {"slot_context": None}

    # 收集所有工具的缺失参数
    all_missing: list[dict] = []  # [{tool_name, tool_call_id, missing_keys, tool_schema}]

    for tc in pending:
        if tc.tool_name in _SKIP_TOOLS:
            continue

        tool = get_tool(tc.tool_name)
        if not tool:
            continue

        schema = getattr(tool, "parameters", None)
        if not schema or not isinstance(schema, dict):
            continue

        required_keys = schema.get("required", [])
        if not required_keys:
            continue

        args = tc.tool_args or {}
        missing = [k for k in required_keys if k not in args or args[k] in (None, "")]

        if missing:
            all_missing.append({
                "tool_name": tc.tool_name,
                "tool_call_id": tc.tool_call_id,
                "missing_keys": missing,
                "tool_schema": schema,
                "filled_slots": {k: v for k, v in args.items() if v not in (None, "")},
            })

    # 参数完整 → pass-through 到 execute
    if not all_missing:
        return {"slot_context": None, "slot_round": 0}

    # 超过最大澄清轮次 → 放弃追问，返回友好错误
    if slot_round >= _MAX_SLOT_ROUNDS:
        logger.warning(
            f"[SlotVerify] Giving up after {slot_round} rounds for {all_missing[0]['tool_name']}"
        )
        missing_info = all_missing[0]
        return {
            "current_phase": AgentPhase.RESPONDING,
            "final_response": (
                f"抱歉，执行「{missing_info['tool_name']}」需要以下信息，"
                f"但多次追问后仍未获取完整参数：{', '.join(missing_info['missing_keys'])}。"
                f"请您直接提供这些信息后重试。"
            ),
            "slot_context": None,
            "slot_round": 0,
            "pending_tool_calls": [],
        }

    # 构建 ask_user 表单 — 只处理第一个缺失工具（避免一次追问太多）
    target = all_missing[0]
    fields = _build_fields_from_schema(target["tool_schema"], target["missing_keys"])

    tool_desc = ""
    tool_obj = get_tool(target["tool_name"])
    if tool_obj:
        tool_desc = getattr(tool_obj, "description", "") or ""

    question = f"执行「{tool_desc or target['tool_name']}」还需要以下信息："

    # 构建 ask_user ToolCallRecord
    ask_record = ToolCallRecord(
        tool_name="ask_user",
        tool_args={
            "question": question,
            "fields": fields,
            "context": f"工具: {target['tool_name']}",
        },
        tool_call_id=f"slot_ask_{target['tool_call_id']}",
    )
    ask_record.status = "ask_user"
    ask_record.result = question

    # 保存 slot_context 供下轮 plan 使用
    slot_ctx = {
        "tool_name": target["tool_name"],
        "tool_call_id": target["tool_call_id"],
        "filled_slots": target["filled_slots"],
        "missing_slots": target["missing_keys"],
        "tool_schema": target["tool_schema"],
    }

    logger.info(
        f"[SlotVerify] Missing params for {target['tool_name']}: "
        f"{target['missing_keys']} (round {slot_round + 1})"
    )

    return {
        "current_phase": AgentPhase.RESPONDING,
        "slot_context": slot_ctx,
        "slot_round": slot_round + 1,
        "pending_tool_calls": [],
        "completed_tool_calls": [ask_record],
        "final_response": "",
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.EXECUTING.value,
                content=f"检测到缺失参数: {', '.join(target['missing_keys'])}，向用户追问",
            )
        ],
    }
