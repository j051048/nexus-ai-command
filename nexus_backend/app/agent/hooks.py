"""
Agent 生命周期 Hook 系统。
在工具调用前/后、LLM 调用前/后提供统一拦截管道。
"""

from __future__ import annotations

import logging
import re
import time
from abc import ABC
from enum import StrEnum
from typing import Any

logger = logging.getLogger("nexus.agent.hooks")

# ─── 基础定义 ───────────────────────────────────────────────


class HookPhase(StrEnum):
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"


class AgentHook(ABC):
    """Base class for agent lifecycle hooks."""

    priority: int = 100  # lower = runs first

    async def before_tool_call(self, tool_name: str, params: dict, context: dict) -> dict:
        """Return modified params, or raise to block the call."""
        return params

    async def after_tool_call(self, tool_name: str, result: Any, context: dict) -> Any:
        """Return modified result."""
        return result

    async def before_llm_call(self, messages: list[dict], context: dict) -> list[dict]:
        """Return modified messages."""
        return messages

    async def after_llm_call(self, response: str, context: dict) -> str:
        """Return modified response."""
        return response


# ─── Hook 注册中心 ──────────────────────────────────────────


class HookRegistry:
    """Manages and executes hooks in priority order."""

    def __init__(self) -> None:
        self._hooks: list[AgentHook] = []

    def register(self, hook: AgentHook) -> None:
        self._hooks.append(hook)
        self._hooks.sort(key=lambda h: h.priority)

    def unregister(self, hook_type: type) -> None:
        self._hooks = [h for h in self._hooks if not isinstance(h, hook_type)]

    async def run_before_tool(self, tool_name: str, params: dict, context: dict) -> dict:
        for hook in self._hooks:
            try:
                params = await hook.before_tool_call(tool_name, params, context)
            except PermissionError:
                raise  # 权限错误需要向上传播
            except Exception:
                logger.exception("Hook %s.before_tool_call failed", type(hook).__name__)
        return params

    async def run_after_tool(self, tool_name: str, result: Any, context: dict) -> Any:
        for hook in self._hooks:
            try:
                result = await hook.after_tool_call(tool_name, result, context)
            except Exception:
                logger.exception("Hook %s.after_tool_call failed", type(hook).__name__)
        return result

    async def run_before_llm(self, messages: list[dict], context: dict) -> list[dict]:
        for hook in self._hooks:
            try:
                messages = await hook.before_llm_call(messages, context)
            except Exception:
                logger.exception("Hook %s.before_llm_call failed", type(hook).__name__)
        return messages

    async def run_after_llm(self, response: str, context: dict) -> str:
        for hook in self._hooks:
            try:
                response = await hook.after_llm_call(response, context)
            except Exception:
                logger.exception("Hook %s.after_llm_call failed", type(hook).__name__)
        return response


# ─── 内置 Hook: 权限校验 ────────────────────────────────────

# viewer 角色禁止调用的写入类工具（前缀匹配）
ROLE_TOOL_RESTRICTIONS: dict[str, list[str]] = {
    "viewer": [
        "create_",
        "update_",
        "delete_",
        "remove_",
        "insert_",
        "upsert_",
        "send_",
        "approve_",
        "reject_",
    ],
}


class PermissionHook(AgentHook):
    """before_tool_call: 校验用户角色是否有权调用该工具。"""

    priority = 10  # 最先执行

    async def before_tool_call(self, tool_name: str, params: dict, context: dict) -> dict:
        role = context.get("user_role", "")
        blocked_prefixes = ROLE_TOOL_RESTRICTIONS.get(role, [])
        for prefix in blocked_prefixes:
            if tool_name.startswith(prefix):
                raise PermissionError(f"角色 '{role}' 无权调用工具 '{tool_name}'")
        return params


# ─── 内置 Hook: 审计日志 ────────────────────────────────────

# 审计日志中需要脱敏的参数名
_AUDIT_SENSITIVE_KEYS = {"password", "token", "secret", "api_key", "credential"}


class AuditLogHook(AgentHook):
    """after_tool_call: 记录工具调用的结构化审计日志。"""

    priority = 90  # 在脱敏之前记录（脱敏后的结果更安全）

    async def before_tool_call(self, tool_name: str, params: dict, context: dict) -> dict:
        context["_audit_start"] = time.monotonic()
        return params

    async def after_tool_call(self, tool_name: str, result: Any, context: dict) -> Any:
        elapsed = time.monotonic() - context.pop("_audit_start", time.monotonic())
        safe_params = {
            k: "***" if k.lower() in _AUDIT_SENSITIVE_KEYS else v
            for k, v in (context.get("_tool_params") or {}).items()
        }
        summary = str(result)[:200] if result is not None else "None"
        logger.info(
            "ToolAudit | tool=%s user=%s org=%s elapsed=%.3fs params=%s result=%s",
            tool_name,
            context.get("user_id", "-"),
            context.get("org_id", "-"),
            elapsed,
            safe_params,
            summary,
        )
        return result


# ─── 内置 Hook: 敏感数据脱敏 ────────────────────────────────

_PHONE_RE = re.compile(r"(1[3-9]\d)\d{4}(\d{4})")
_ID_CARD_RE = re.compile(r"(\d{3})\d{11}(\d{4})")
_EMAIL_RE = re.compile(r"([a-zA-Z0-9])[a-zA-Z0-9.]*@([a-zA-Z0-9.-]+)")


def _mask_text(text: str) -> str:
    """对文本中的手机号、身份证、邮箱做脱敏。"""
    text = _PHONE_RE.sub(r"\1****\2", text)
    text = _ID_CARD_RE.sub(r"\1***********\2", text)
    text = _EMAIL_RE.sub(r"\1***@\2", text)
    return text


def _mask_value(value: Any) -> Any:
    """递归脱敏：支持 str / dict / list。"""
    if isinstance(value, str):
        return _mask_text(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    return value


class SensitiveDataHook(AgentHook):
    """after_tool_call: 对返回结果中的手机号、身份证号、邮箱做脱敏。"""

    priority = 50

    async def after_tool_call(self, tool_name: str, result: Any, context: dict) -> Any:
        return _mask_value(result)


# ─── 内置 Hook: LLM 入站 PII 脱敏 ─────────────────────────────


class PIISanitizeHook(AgentHook):
    """before_llm_call: 扫描发送给 LLM 的消息，对 PII 做脱敏。

    覆盖所有 graph 内部的 LLM 调用点（plan/execute/reflect/respond/synthesize/orchestrate），
    确保用户消息、工具返回结果和 RAG context 中的 PII 不会泄露给外部模型。
    """

    priority = 20  # 在权限校验之后、审计之前

    async def before_llm_call(self, messages: list[dict], context: dict) -> list[dict]:
        from app.services.content_moderation import sanitize_pii_for_llm

        for msg in messages:
            content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
            if isinstance(content, str) and content:
                sanitized = sanitize_pii_for_llm(content)
                if sanitized != content:
                    if isinstance(msg, dict):
                        msg["content"] = sanitized
                    elif hasattr(msg, "content"):
                        # LangChain BaseMessage — content is a writable property
                        try:
                            msg.content = sanitized
                        except AttributeError:
                            pass  # Frozen message, skip
        return messages


# ─── 内置 Hook: 自动快照 (P0-7 Hermes 风格) ──────────────────


class AutoSnapshotHook(AgentHook):
    """after_tool_call: 在不可逆/高风险工具执行后自动创建状态快照。

    借鉴 Hermes Agent 的 shadow git 模式，对关键操作做透明快照，
    支持事后回溯和审计。使用 asyncio.create_task 异步化，不阻塞主流程。
    """

    priority = 85  # 在审计日志(90)之前，脱敏(50)之后

    async def after_tool_call(self, tool_name: str, result: Any, context: dict) -> Any:
        try:
            from app.tools import get_tool

            tool = get_tool(tool_name)
            if not tool or not getattr(tool, "is_irreversible", False):
                return result

            # 异步保存快照，不阻塞
            import asyncio

            from app.agent.state_versioning import state_version_control

            thread_id = context.get("thread_id") or context.get("session_id", "unknown")
            snapshot_state = {
                "tool_name": tool_name,
                "tool_result_preview": str(result)[:300] if result else "",
                "user_id": context.get("user_id", ""),
                "org_id": context.get("org_id", ""),
                "timestamp": time.time(),
            }

            asyncio.create_task(
                state_version_control.save_snapshot(
                    thread_id=thread_id,
                    state=snapshot_state,
                    label=f"post_{tool_name}",
                    snapshot_type="pre_irreversible",
                )
            )
            logger.info(f"[AutoSnapshot] Queued snapshot after irreversible tool: {tool_name}")

        except Exception as e:
            # 快照失败不应阻塞主流程
            logger.warning(f"[AutoSnapshot] Failed to queue snapshot: {e}")

        return result


# ─── 内置 Hook: 自动快照 (Hermes 风格透明快照) ──────────────


class AutoSnapshotHook(AgentHook):
    """after_tool_call: 在不可逆工具执行后自动创建状态快照。

    借鉴 Hermes Agent 的 shadow-git 模式，对高风险操作透明拍快照，
    支持事后回滚。使用 asyncio.create_task 异步执行，不阻塞主流程。
    """

    priority = 85  # 在审计日志(90)之前，脱敏(50)之后

    async def after_tool_call(self, tool_name: str, result: Any, context: dict) -> Any:
        # 只对不可逆工具拍快照
        try:
            from app.tools import get_tool

            tool = get_tool(tool_name)
            if not tool or not tool.is_irreversible:
                return result

            import asyncio

            from app.agent.state_versioning import state_version_control

            thread_id = context.get("thread_id") or context.get("session_id", "")
            if not thread_id:
                return result

            # 构建快照 state（从 context 中提取可用信息）
            snapshot_state = {
                "tool_name": tool_name,
                "tool_result_preview": str(result)[:300] if result else "",
                "user_id": context.get("user_id", ""),
                "snapshot_type": "post_irreversible",
            }

            asyncio.create_task(
                state_version_control.save_lightweight_snapshot(
                    thread_id=thread_id,
                    state=snapshot_state,
                    label=f"after_{tool_name}",
                    tool_names=[tool_name],
                )
            )
            logger.info(f"[AutoSnapshot] Scheduled snapshot after irreversible tool: {tool_name}")

        except Exception as e:
            # 快照失败不应影响主流程
            logger.warning(f"[AutoSnapshot] Failed to schedule snapshot: {e}")

        return result


# ─── 模块级单例 ─────────────────────────────────────────────

hook_registry = HookRegistry()
hook_registry.register(PermissionHook())
hook_registry.register(PIISanitizeHook())
hook_registry.register(AuditLogHook())
hook_registry.register(SensitiveDataHook())
hook_registry.register(AutoSnapshotHook())
hook_registry.register(AutoSnapshotHook())
