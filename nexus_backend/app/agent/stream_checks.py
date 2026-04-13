"""Pre-flight checks for the streaming agent pipeline.

Extracted from stream.py to isolate guard-clause logic (token budget,
input moderation, PII sanitization) from the main event loop.
"""

import logging

from app.core.token_budget import BudgetVerdict, token_budget_manager
from app.services.content_moderation import check_user_input
from app.services.tenant_credit_service import CreditType, tenant_credit_service
from app.services.token_service import usage_tracker, validate_request_tokens

from .sse_protocol import _sse_content

logger = logging.getLogger(__name__)


async def run_pre_checks(
    messages: list[dict],
    user_id: str,
    model: str,
    session_id: str | None,
    org_id: str | None,
    *,
    skip_moderation: bool = False,
) -> tuple[bool, list[str], str]:
    """Execute all pre-flight checks before running the agent.

    Parameters
    ----------
    skip_moderation : bool
        If True, skip input moderation (caller already did it, e.g. chat.py).

    Returns
    -------
    (passed, sse_events, sanitised_last_user_content)
        passed: True if all checks passed
        sse_events: list of SSE strings to yield if checks failed
        sanitised_last_user_content: the (possibly PII-sanitised) last user message
    """
    sse_events: list[str] = []

    # ── 1. Token budget check ──
    await usage_tracker.ensure_loaded(user_id)
    messages_dicts = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
    ]
    is_allowed, _input_tokens, reason = validate_request_tokens(
        messages_dicts, model, user_id
    )
    if not is_allowed:
        sse_events.append(_sse_content(f"⛔ 请求被拒绝 (超出限制): {reason}"))
        sse_events.append("data: [DONE]\n\n")
        return False, sse_events, ""

    # ── 1b. Session/user/tenant cost circuit-breaker ──
    try:
        budget_status = await token_budget_manager.check_budget(
            session_id=session_id or "default",
            user_id=user_id,
            tenant_id=org_id,
        )
        if budget_status.verdict == BudgetVerdict.EXCEEDED:
            sse_events.append(_sse_content(f"⛔ {budget_status.message}"))
            sse_events.append("data: [DONE]\n\n")
            return False, sse_events, ""
        if budget_status.verdict == BudgetVerdict.WARNING:
            logger.warning(f"[Stream] Token budget warning: {budget_status.message}")
    except Exception as e:
        logger.warning(f"[Stream] Token budget check failed (non-blocking): {e}")

    # ── 1c. Tenant credit quota check ──
    if org_id:
        try:
            has_credit, credit_error = await tenant_credit_service.check_credit(
                org_id, CreditType.API_CALLS, 1
            )
            if not has_credit:
                sse_events.append(_sse_content(f"⚠️ 组织配额不足: {credit_error}"))
                sse_events.append("data: [DONE]\n\n")
                return False, sse_events, ""
        except Exception as e:
            logger.warning(f"[Stream] Tenant credit check failed (non-blocking): {e}")

    # ── 2. Input moderation ──
    # P0 #5: Skip if caller already performed moderation (e.g. chat.py)
    last_user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_content = msg.get("content", "")
            break

    if last_user_content and not skip_moderation:
        is_safe, warning = check_user_input(last_user_content)
        if not is_safe:
            sse_events.append(_sse_content(f"⛔ 安全警告: {warning}"))
            sse_events.append("data: [DONE]\n\n")
            return False, sse_events, ""

    # ── 2a. PII sanitization before LLM ──
    if last_user_content:
        from app.services.content_moderation import sanitize_pii_for_llm

        sanitized = sanitize_pii_for_llm(last_user_content)
        if sanitized != last_user_content:
            last_user_content = sanitized
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    msg["content"] = sanitized
                    break

    # 2a-ext. Sanitize PII in ALL user messages (not just the last one)
    if messages:
        from app.services.content_moderation import (
            sanitize_pii_for_llm as _sanitize_pii,
        )

        for msg in messages:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                msg["content"] = _sanitize_pii(msg["content"])

    return True, sse_events, last_user_content
