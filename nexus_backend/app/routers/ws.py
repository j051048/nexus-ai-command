"""
WebSocket Router — provides real-time bidirectional communication.

Endpoints:
  /ws/chat    — Real-time agent chat streaming (alternative to SSE)
  /ws/push    — Server-push channel for notifications and trigger results
"""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import stream_agent_via_ws, ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time AI agent chat.

    Protocol:
    1. Client connects with ?token=<jwt>
    2. Client sends JSON: {"messages": [...], "config": {...}, "system_prompt": "..."}
    3. Server streams JSON events:
       - {"type": "content", "data": {"choices": [{"delta": {"content": "..."}}]}}
       - {"type": "thinking", "data": {"thinking_step": {...}}}
       - {"type": "status", "data": {"status": "..."}}
       - {"type": "done"}
    """
    # Authenticate via JWT
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await ws_manager.connect(websocket, user_id)

    try:
        while True:
            # Wait for client message
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # Extract chat parameters
            messages = data.get("messages", [])
            config = data.get("config", {})
            system_prompt = data.get("system_prompt", "")
            session_id = data.get("session_id")
            agent_name = data.get("agent_name")
            scene_code = data.get("scene_code")
            vmd_agent_code = data.get("vmd_agent_code")

            if not messages:
                await websocket.send_json({"type": "error", "message": "No messages provided"})
                continue

            # Get user info for the stream
            user_role, org_id = await _get_user_context(user_id)

            # Run the agent stream and forward via WebSocket
            from app.agent.stream import run_agent_stream

            agent_stream = run_agent_stream(
                messages=messages,
                config=config,
                user_id=user_id,
                system_prompt=system_prompt,
                session_id=session_id,
                agent_name=agent_name,
                user_role=user_role,
                org_id=org_id,
                scene_code=scene_code,
                vmd_agent_code=vmd_agent_code,
            )

            await stream_agent_via_ws(websocket, user_id, agent_stream)

    except WebSocketDisconnect:
        logger.info(f"[WS/Chat] User {user_id} disconnected")
    except Exception as e:
        logger.error(f"[WS/Chat] Error: {e}")
    finally:
        ws_manager.disconnect(websocket, user_id)


@router.websocket("/ws/push")
async def websocket_push(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for server-push notifications.

    The client connects and receives push events from:
    - Auto-trigger service results
    - Real-time notifications
    - Dashboard refresh signals

    Client can send {"type": "ping"} for keepalive.
    """
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await ws_manager.connect(websocket, user_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"[WS/Push] User {user_id} disconnected")
    finally:
        ws_manager.disconnect(websocket, user_id)


@router.get("/api/ws/status")
async def ws_status():
    """Get WebSocket connection statistics."""
    return {
        "active_connections": ws_manager.active_connections,
        "active_users": ws_manager.active_users,
    }


# ── Internal helpers ──


async def _authenticate_ws(token: str) -> str | None:
    """Authenticate a WebSocket connection via JWT token (same logic as auth.py)."""
    import os

    import jwt as pyjwt

    try:
        supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        jwt_secret = os.getenv("JWT_SECRET")
        secret = supabase_jwt_secret or jwt_secret

        if not secret:
            logger.warning("[WS] No JWT secret configured")
            return None

        payload = pyjwt.decode(token, secret, algorithms=["HS256", "RS256", "ES256"])
        user_id = payload.get("sub")
        return user_id
    except Exception as e:
        logger.warning(f"[WS] Auth failed: {e}")
        return None


async def _get_user_context(user_id: str) -> tuple[str, str | None]:
    """Get user role and org_id for agent context."""
    try:
        from app.core.database import supabase

        if supabase:
            result = await supabase.table("users").select("role, org_id").eq("id", user_id).single().execute()
            if result.data:
                return result.data.get("role", "employee"), result.data.get("org_id")
    except Exception as e:
        logger.warning(f"[WS] Failed to get user context: {e}")
    return "employee", None
