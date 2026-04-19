"""
MCP Server — Model Context Protocol implementation.

Supports two transport modes:
  1. HTTP REST (original MVP) — for simple tool discovery and execution
  2. SSE (Server-Sent Events) — standard MCP transport for real-time bidirectional
     communication with Claude Desktop, Cursor, and other MCP clients

Endpoints:
    GET  /api/mcp/tools                    - List all registered tools (REST)
    POST /api/mcp/tools/{tool_name}/execute - Execute a tool by name (REST)
    GET  /api/mcp/sse                      - SSE endpoint for MCP clients
    POST /api/mcp/messages                 - Receive JSON-RPC messages from MCP clients
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, model_validator

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.tools import TOOL_REGISTRY, _load_all, get_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Server"])


# ---------------------------------------------------------------------------
# Response / Request schemas
# ---------------------------------------------------------------------------


class MCPToolSchema(BaseModel):
    """MCP-compatible tool descriptor."""

    name: str
    description: str
    inputSchema: dict[str, Any]  # noqa: N815


class MCPToolListResponse(BaseModel):
    """Response for the tool listing endpoint."""

    tools: list[MCPToolSchema]
    count: int


class MCPExecuteRequest(BaseModel):
    """Request body for tool execution.

    Accepts both formats:
      - Standard: {"arguments": {"name": "..."}}
      - Flat:     {"name": "..."}  (auto-wrapped into arguments)
    """

    arguments: dict[str, Any] = {}

    @model_validator(mode="before")
    @classmethod
    def normalize_arguments(cls, data: Any) -> Any:
        """Handle flat argument format from external clients like OpenClaw."""
        if isinstance(data, dict) and "arguments" not in data:
            return {"arguments": data}
        return data


class MCPExecuteResponse(BaseModel):
    """Response for a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# SSE Session Management
# ---------------------------------------------------------------------------


class MCPSession:
    """Manages a single MCP SSE session."""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.created_at = time.time()

    async def send(self, data: dict):
        """Queue an SSE event to be sent to the client."""
        await self.queue.put(data)

    async def send_jsonrpc_response(self, id: Any, result: Any):  # noqa: A002
        """Send a JSON-RPC 2.0 response."""
        await self.send(
            {
                "jsonrpc": "2.0",
                "id": id,
                "result": result,
            }
        )

    async def send_jsonrpc_error(self, id: Any, code: int, message: str):  # noqa: A002
        """Send a JSON-RPC 2.0 error response."""
        await self.send(
            {
                "jsonrpc": "2.0",
                "id": id,
                "error": {"code": code, "message": message},
            }
        )


# In-memory session store (suitable for single-instance deployment)
_sessions: dict[str, MCPSession] = {}

# Server capabilities declaration
MCP_SERVER_INFO = {
    "name": "nexus-ai-command",
    "version": "1.0.0",
}

MCP_CAPABILITIES = {
    "tools": {"listChanged": False},
}


# ---------------------------------------------------------------------------
# REST Endpoints (original MVP)
# ---------------------------------------------------------------------------


@router.get("/tools")
async def list_tools(user_id: str = Depends(get_current_user_id)):
    """List all available tools in MCP format.

    Returns each tool's name, description and JSON-Schema input definition so
    that MCP clients can build dynamic UIs or route calls automatically.
    """
    _load_all()
    tools: list[MCPToolSchema] = []
    for tool in TOOL_REGISTRY.values():
        tools.append(
            MCPToolSchema(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.parameters or {},
            )
        )

    logger.info(
        "[MCP] list_tools called by user=%s, returning %d tools",
        user_id,
        len(tools),
    )
    return api_success(
        data=MCPToolListResponse(tools=tools, count=len(tools)).model_dump()
    )


@router.post("/tools/{tool_name}/execute")
async def execute_tool(
    tool_name: str,
    body: MCPExecuteRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Execute a registered tool by name.

    The caller must supply the tool arguments as a JSON object under the
    ``arguments`` key.  The endpoint resolves the tool from the global
    registry, validates access, and runs it with the authenticated user
    context.
    """
    # --- Resolve tool ---
    tool = get_tool(tool_name)
    if tool is None:
        logger.warning("[MCP] tool_not_found tool=%s user=%s", tool_name, user_id)
        raise api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            f"Tool '{tool_name}' not found in the registry.",
        )

    # --- Validate required arguments ---
    schema = getattr(tool, "parameters", None) or {}
    required_args = schema.get("required", [])
    missing = [r for r in required_args if r not in body.arguments]
    if missing:
        raise api_error(
            ErrorCode.VALIDATION_MISSING_FIELD,
            f"Tool '{tool_name}' 缺少必填参数: {', '.join(missing)}",
        )

    # --- Validate arguments against JSON Schema ---
    try:
        await tool.validate(body.arguments)
    except Exception as ve:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"参数校验失败: {ve}",
        )

    # --- Build execution context ---
    org_id = getattr(request.state, "org_id", None)
    config: dict[str, Any] = {
        "org_id": org_id,
        "source": "mcp",
    }

    logger.info(
        "[MCP] execute tool=%s user=%s org=%s args_keys=%s args=%s",
        tool_name,
        user_id,
        org_id,
        list(body.arguments.keys()),
        {
            k: (v if len(str(v)) < 100 else str(v)[:100] + "...")
            for k, v in body.arguments.items()
        },
    )

    # --- Execute (with timeout protection against LLM-heavy tools) ---
    mcp_tool_timeout_seconds = 60
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            tool.run(
                args=body.arguments,
                user_id=user_id,
                config=config,
            ),
            timeout=mcp_tool_timeout_seconds,
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "[MCP] tool_success tool=%s user=%s duration_ms=%.2f",
            tool_name,
            user_id,
            duration_ms,
        )

        return api_success(
            data=MCPExecuteResponse(
                tool_name=tool_name,
                success=True,
                result=result,
                duration_ms=duration_ms,
            ).model_dump()
        )
    except TimeoutError:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.warning(
            "[MCP] tool_timeout tool=%s user=%s duration_ms=%.2f timeout=%ds",
            tool_name,
            user_id,
            duration_ms,
            mcp_tool_timeout_seconds,
        )
        raise api_error(
            ErrorCode.AI_SERVICE_TIMEOUT,
            f"工具 '{tool_name}' 执行超时（{mcp_tool_timeout_seconds}秒），请稍后重试。",
        )
    except HTTPException:
        raise
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "[MCP] tool_error tool=%s user=%s duration_ms=%.2f error=%s",
            tool_name,
            user_id,
            duration_ms,
            str(exc),
        )
        raise api_error(
            ErrorCode.SYSTEM_INTERNAL_ERROR,
            f"Tool execution failed: {exc}",
        )


# ---------------------------------------------------------------------------
# SSE Transport Endpoints (Standard MCP)
# ---------------------------------------------------------------------------


@router.get("/sse")
async def sse_endpoint(request: Request, user_id: str = Depends(get_current_user_id)):
    """
    SSE endpoint for MCP clients (Claude Desktop, Cursor, etc.).

    The client connects here and receives server-sent events.
    Messages from client are sent via POST /api/mcp/messages.

    SSE Protocol:
      1. Client connects to GET /api/mcp/sse
      2. Server sends 'endpoint' event with the messages URL
      3. Client sends JSON-RPC requests to POST /api/mcp/messages
      4. Server sends JSON-RPC responses back via SSE
    """
    session_id = str(uuid.uuid4())
    session = MCPSession(session_id, user_id)
    _sessions[session_id] = session

    logger.info("[MCP-SSE] New session=%s user=%s", session_id, user_id)

    async def event_stream():
        try:
            # First event: tell client where to send messages
            messages_url = f"/api/mcp/messages?session_id={session_id}"
            yield f"event: endpoint\ndata: {messages_url}\n\n"

            # Keep connection alive, forward queued responses
            # P0-8: keepalive 每 10s 一次,避免 Nginx 60s / Vercel 25s 空闲断连
            while True:
                try:
                    data = await asyncio.wait_for(session.queue.get(), timeout=10.0)
                    payload = json.dumps(data, ensure_ascii=False)
                    yield f"event: message\ndata: {payload}\n\n"
                except TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
                except asyncio.CancelledError:
                    break

                # Check if client disconnected
                if await request.is_disconnected():
                    break
        finally:
            # Cleanup session
            _sessions.pop(session_id, None)
            logger.info("[MCP-SSE] Session closed=%s", session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages")
async def handle_message(
    request: Request,
    session_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Receive JSON-RPC 2.0 messages from MCP clients.

    Supported methods:
      - initialize: Handshake, returns server capabilities
      - tools/list: List available tools
      - tools/call: Execute a tool
      - ping: Keepalive ping
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    logger.info(
        "[MCP-SSE] message session=%s method=%s id=%s",
        session_id,
        method,
        msg_id,
    )

    try:
        if method == "initialize":
            await session.send_jsonrpc_response(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": MCP_SERVER_INFO,
                    "capabilities": MCP_CAPABILITIES,
                },
            )

        elif method == "notifications/initialized":
            # Client acknowledges initialization — no response needed
            pass

        elif method == "ping":
            await session.send_jsonrpc_response(msg_id, {})

        elif method == "tools/list":
            _load_all()
            tools = []
            for tool in TOOL_REGISTRY.values():
                tools.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.parameters
                        or {
                            "type": "object",
                            "properties": {},
                        },
                    }
                )
            await session.send_jsonrpc_response(msg_id, {"tools": tools})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            tool = get_tool(tool_name)
            if not tool:
                await session.send_jsonrpc_error(
                    msg_id, -32602, f"Tool '{tool_name}' not found"
                )
                return {"ok": True}

            # Validate arguments against JSON Schema
            try:
                await tool.validate(arguments)
            except Exception as ve:
                await session.send_jsonrpc_error(msg_id, -32602, f"参数校验失败: {ve}")
                return {"ok": True}

            # Execute tool (with timeout protection)
            mcp_sse_tool_timeout = 60
            start = time.perf_counter()
            try:
                org_id = getattr(request.state, "org_id", None)
                result = await asyncio.wait_for(
                    tool.run(
                        args=arguments,
                        user_id=user_id,
                        config={"org_id": org_id, "source": "mcp-sse"},
                    ),
                    timeout=mcp_sse_tool_timeout,
                )
                duration_ms = round((time.perf_counter() - start) * 1000, 2)

                await session.send_jsonrpc_response(
                    msg_id,
                    {
                        "content": [
                            {"type": "text", "text": str(result)},
                        ],
                        "isError": False,
                        "_meta": {"duration_ms": duration_ms},
                    },
                )
            except TimeoutError:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.warning(
                    "[MCP-SSE] tool_timeout tool=%s duration_ms=%.2f timeout=%ds",
                    tool_name,
                    duration_ms,
                    mcp_sse_tool_timeout,
                )
                await session.send_jsonrpc_response(
                    msg_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": f"工具 '{tool_name}' 执行超时（{mcp_sse_tool_timeout}秒），请稍后重试。",
                            },
                        ],
                        "isError": True,
                        "_meta": {"duration_ms": duration_ms},
                    },
                )
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.error("[MCP-SSE] tool_error tool=%s error=%s", tool_name, exc)
                await session.send_jsonrpc_response(
                    msg_id,
                    {
                        "content": [
                            {"type": "text", "text": f"Tool error: {str(exc)}"},
                        ],
                        "isError": True,
                        "_meta": {"duration_ms": duration_ms},
                    },
                )

        else:
            await session.send_jsonrpc_error(
                msg_id, -32601, f"Method '{method}' not supported"
            )

    except Exception as exc:
        logger.exception("[MCP-SSE] handler error: %s", exc)
        if msg_id is not None:
            await session.send_jsonrpc_error(
                msg_id, -32603, f"Internal error: {str(exc)}"
            )

    return {"ok": True}
