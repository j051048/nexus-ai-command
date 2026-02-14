"""
MCP Server MVP Endpoint.

Exposes the internal tool registry via the Model Context Protocol (MCP) format,
allowing external MCP clients to discover and invoke Nexus tools over HTTP.

Endpoints:
    GET  /api/mcp/tools                  - List all registered tools in MCP schema format
    POST /api/mcp/tools/{tool_name}/execute - Execute a tool by name with provided arguments
"""

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.tools import TOOL_REGISTRY, get_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["MCP Server"])


# ---------------------------------------------------------------------------
# Response / Request schemas
# ---------------------------------------------------------------------------

class MCPToolSchema(BaseModel):
    """MCP-compatible tool descriptor."""
    name: str
    description: str
    inputSchema: Dict[str, Any]


class MCPToolListResponse(BaseModel):
    """Response for the tool listing endpoint."""
    tools: List[MCPToolSchema]
    count: int


class MCPExecuteRequest(BaseModel):
    """Request body for tool execution."""
    arguments: Dict[str, Any] = {}


class MCPExecuteResponse(BaseModel):
    """Response for a tool execution."""
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/tools", response_model=MCPToolListResponse)
async def list_tools(user_id: str = Depends(get_current_user_id)):
    """List all available tools in MCP format.

    Returns each tool's name, description and JSON-Schema input definition so
    that MCP clients can build dynamic UIs or route calls automatically.
    """
    tools: List[MCPToolSchema] = []
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
    return MCPToolListResponse(tools=tools, count=len(tools))


@router.post("/tools/{tool_name}/execute", response_model=MCPExecuteResponse)
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
        logger.warning(
            "[MCP] tool_not_found tool=%s user=%s", tool_name, user_id
        )
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found in the registry.",
        )

    # --- Build execution context ---
    org_id = getattr(request.state, "org_id", None)
    config: Dict[str, Any] = {
        "org_id": org_id,
        "source": "mcp",
    }

    logger.info(
        "[MCP] execute tool=%s user=%s org=%s args_keys=%s",
        tool_name,
        user_id,
        org_id,
        list(body.arguments.keys()),
    )

    # --- Execute ---
    start = time.perf_counter()
    try:
        result = await tool.run(
            args=body.arguments,
            user_id=user_id,
            config=config,
        )
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        logger.info(
            "[MCP] tool_success tool=%s user=%s duration_ms=%.2f",
            tool_name,
            user_id,
            duration_ms,
        )

        return MCPExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result,
            duration_ms=duration_ms,
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
        raise HTTPException(
            status_code=500,
            detail=f"Tool execution failed: {exc}",
        )
