"""
Shared imports, helpers, constants and Pydantic models for graph nodes.

All node modules import from here to avoid circular dependencies.
"""

import logging

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agent.state import (
    AgentConfig,
    AgentPhase,  # noqa: F401
    AgentState,  # noqa: F401
    QueryComplexity,  # noqa: F401
    ThinkingStep,  # noqa: F401
    ToolCallRecord,  # noqa: F401
)
from app.core.ai_metrics import (
    record_hallucination,  # noqa: F401
    record_llm_latency,  # noqa: F401
    record_tool_execution,  # noqa: F401
)
from app.services.content_moderation import sanitize_output, scan_content  # noqa: F401
from app.services.error_recovery_service import llm_circuit_breaker, tool_circuit_breaker  # noqa: F401
from app.services.plugin_system_service import ExtensionPoint, plugin_system_service  # noqa: F401
from app.tools import get_all_tools_schema, get_tool

logger = logging.getLogger(__name__)

# Long-running tools that need extended timeout (120s instead of default 30s)
LONG_RUNNING_TOOLS: set[str] = {
    "generate_product_manual",
    "generate_faq_response",
    "generate_training_material",
    "generate_weekly_report",
    "generate_competitor_analysis",
    "generate_tender_analysis",
    "generate_contract_summary",
    "batch_analyze_documents",
    "query_knowledge_base",
    "strategy_simulation",
    "get_company_stats",
}


# ─── Pydantic models for structured LLM output in reflect_node ───────────────


class GroundednessCheck(BaseModel):
    """RAG groundedness evaluation result."""

    is_grounded: bool = Field(description="Whether the response is grounded in reference knowledge")
    reason: str = Field(default="", description="Reason for the evaluation")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Groundedness score 0-1")


class HallucinationCheck(BaseModel):
    """LLM-based hallucination detection result."""

    is_hallucination: bool = Field(description="Whether the response contains fabricated information")
    reason: str = Field(default="", description="Reason for the evaluation")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1")


class CriticResult(BaseModel):
    """P1-5: Independent critic evaluation of agent response quality."""

    completeness: float = Field(default=0.5, ge=0.0, le=1.0, description="回答是否完整覆盖用户问题")
    relevance: float = Field(default=0.5, ge=0.0, le=1.0, description="回答与用户意图的相关性")
    accuracy: float = Field(default=0.5, ge=0.0, le=1.0, description="信息准确性（基于工具结果）")
    passed: bool = Field(default=True, description="是否通过评审")
    improvement_suggestion: str = Field(default="", description="改进建议（未通过时提供）")


# P1 Fix: Cache tool schemas to avoid rebuilding on every request
_tool_schemas_cache = None
_tool_schemas_count = None

# Role hierarchy for tool access filtering
_ROLE_HIERARCHY = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "boss": 3,
    "founder": 4,
}


def _get_tool_schemas(user_role: str | None = None):
    """Get tool schemas with caching. Optionally filter by user role to reduce token cost."""
    global _tool_schemas_cache, _tool_schemas_count
    schemas = get_all_tools_schema()
    if _tool_schemas_cache is None or len(schemas) != _tool_schemas_count:
        _tool_schemas_cache = schemas
        _tool_schemas_count = len(schemas)

    if not user_role:
        return _tool_schemas_cache

    # Filter schemas by user role — exclude tools the user cannot execute
    user_level = _ROLE_HIERARCHY.get(user_role, 1)
    filtered = []
    for schema in _tool_schemas_cache:
        tool_name = schema.get("function", {}).get("name", "")
        tool = get_tool(tool_name)
        if not tool:
            continue
        req_role = getattr(tool, "required_role", "all")
        if req_role in ("all", "ai_assistant"):
            filtered.append(schema)
        else:
            req_level = _ROLE_HIERARCHY.get(req_role, 1)
            if user_level >= req_level:
                filtered.append(schema)
    return filtered


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False, resolved_config: dict | None = None
):
    """Get a LangChain ChatOpenAI instance with the provided config.

    If resolved_config is provided (from LLM gateway), use it.
    Otherwise fall back to AgentConfig settings.

    #25: Injects trace_id as default header for full-chain propagation.
    """
    from app.core.trace_context import get_request_id, get_trace_id

    # 构建追踪头
    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    # Langfuse CallbackHandler injection
    callbacks = None
    try:
        from app.core.config import settings

        if settings.LANGFUSE_ENABLED:
            from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

            callbacks = [
                LangfuseCallbackHandler(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
            ]
    except Exception:
        pass  # Langfuse not available, skip

    if resolved_config:
        return ChatOpenAI(
            model=resolved_config.get("model", model or config.model),
            api_key=resolved_config.get("api_key", config.api_key),
            base_url=resolved_config.get("base_url", config.base_url),
            temperature=resolved_config.get("temperature", config.temperature),
            streaming=streaming,
            timeout=resolved_config.get("timeout", 60.0),
            default_headers=default_headers or None,
            callbacks=callbacks,
        )
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=60.0,
        default_headers=default_headers or None,
        callbacks=callbacks,
    )


def _get_fallback_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False
):
    """Get a fallback LLM instance when primary provider is unavailable.

    Returns None if no fallback is configured.
    """
    from app.core.config import settings

    if not settings.AI_FALLBACK_API_KEY or not settings.AI_FALLBACK_BASE_URL:
        return None

    from app.core.trace_context import get_request_id, get_trace_id

    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    return ChatOpenAI(
        model=model or config.model,
        api_key=settings.AI_FALLBACK_API_KEY,
        base_url=settings.AI_FALLBACK_BASE_URL,
        temperature=config.temperature,
        streaming=streaming,
        timeout=60.0,
        default_headers=default_headers or None,
    )


async def invoke_with_fallback(
    llm,
    messages: list,
    config: AgentConfig,
    model: str | None = None,
    streaming: bool = False,
    tool_schemas: list | None = None,
):
    """Invoke LLM with automatic fallback to backup provider on failure.

    Tries primary LLM first. If it fails (payment, rate limit, auth, server error),
    automatically retries with fallback provider.
    """
    try:
        return await llm.ainvoke(messages)
    except Exception as primary_error:
        error_str = str(primary_error).lower()
        # Only fallback on provider-level errors, not on content/format issues
        is_provider_error = any(
            kw in error_str
            for kw in [
                "401", "402", "403", "429", "500", "502", "503",
                "insufficient", "quota", "balance", "payment",
                "rate limit", "rate_limit", "unauthorized",
                "authentication", "billing", "exceeded",
                "connection", "timeout", "connect",
            ]
        )
        if not is_provider_error:
            raise

        fallback_llm = _get_fallback_llm(config, model=model, streaming=streaming)
        if not fallback_llm:
            raise

        logger.warning(
            f"[LLM Fallback] Primary failed: {primary_error}. Switching to fallback provider."
        )
        if tool_schemas:
            fallback_llm = fallback_llm.bind_tools(tool_schemas, parallel_tool_calls=True)
        return await fallback_llm.ainvoke(messages)


def _messages_to_lc_format(messages) -> list[BaseMessage]:
    """Ensure messages are in LangChain format."""
    result = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            result.append(msg)
        elif isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {})))
            elif role == "tool":
                result.append(
                    ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", ""), name=msg.get("name", ""))
                )
    return result


def _format_validation_error(tool_name: str, error: Exception, schema: dict | None = None) -> str:
    """
    Format a schema validation error with field-level guidance for the LLM.

    Instead of raw jsonschema error text, produces a structured message
    that helps the LLM understand exactly which field to fix.
    """
    try:
        import jsonschema

        if isinstance(error, jsonschema.ValidationError):
            field_path = " → ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
            lines = [f"参数校验失败 [{tool_name}]:"]
            lines.append(f"  错误字段: {field_path}")
            lines.append(f"  问题: {error.message}")

            # Add expected type/enum info
            if error.schema:
                if "type" in error.schema:
                    lines.append(f"  期望类型: {error.schema['type']}")
                if "enum" in error.schema:
                    lines.append(f"  允许值: {error.schema['enum']}")
                if "description" in error.schema:
                    lines.append(f"  字段说明: {error.schema['description']}")

            # Show required fields if it's a missing-property error
            if error.validator == "required" and schema:
                required = schema.get("required", [])
                props = schema.get("properties", {})
                if required:
                    field_hints = []
                    for r in required:
                        desc = props.get(r, {}).get("description", "")
                        ftype = props.get(r, {}).get("type", "")
                        field_hints.append(f"    - {r} ({ftype}): {desc}" if desc else f"    - {r} ({ftype})")
                    lines.append("  必填字段:")
                    lines.extend(field_hints)

            return "\n".join(lines)
    except Exception:
        pass

    # Fallback for non-jsonschema errors
    return f"参数校验失败 [{tool_name}]: {error}"


def _try_extract_tool_names(concatenated_name: str) -> list[str]:
    """
    Gemini concatenation bug workaround: Extract ALL valid tool names
    from a concatenated string like 'get_daily_briefingget_pending_approvals'.

    Returns a list of matched tool names (may be empty).
    """
    all_schemas = get_all_tools_schema()
    # Sort by length descending to match longest tool name first
    known_names = sorted(
        [s["function"]["name"] for s in all_schemas],
        key=len,
        reverse=True,
    )

    found: list[str] = []
    remaining = concatenated_name
    while remaining:
        matched = False
        for name in known_names:
            if remaining.startswith(name):
                found.append(name)
                remaining = remaining[len(name):]
                matched = True
                break
        if not matched:
            break  # Unrecognizable remainder, stop parsing

    return found if len(found) > 1 else []  # Only useful when multiple names found
