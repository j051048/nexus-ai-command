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

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/chat")
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

    connected = await ws_manager.connect(websocket, user_id)
    if not connected:
        return

    try:
        while True:
            # Wait for client message
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            if data.get("type") in ("ping", "pong"):
                ws_manager.record_pong(websocket)
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


@router.websocket("/push")
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

    connected = await ws_manager.connect(websocket, user_id)
    if not connected:
        return

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                if data.get("type") in ("ping", "pong"):
                    ws_manager.record_pong(websocket)
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"[WS/Push] User {user_id} disconnected")
    finally:
        ws_manager.disconnect(websocket, user_id)


@router.get("/status")
async def ws_status():
    """Get WebSocket connection statistics."""
    from app.services.websocket_manager import MAX_CONNECTIONS_GLOBAL, MAX_CONNECTIONS_PER_USER

    return {
        "active_connections": ws_manager.active_connections,
        "active_users": ws_manager.active_users,
        "limits": {
            "per_user": MAX_CONNECTIONS_PER_USER,
            "global": MAX_CONNECTIONS_GLOBAL,
        },
    }


# ── Internal helpers ──


async def _authenticate_ws(token: str) -> str | None:
    """Authenticate a WebSocket connection via JWT token.

    Reuses the same two-stage strategy as auth.py:
    1. ES256/RS256 → JWKS public key from Supabase
    2. HS256 → shared secret (SUPABASE_JWT_SECRET / JWT_SECRET)
    """
    import os

    import jwt as pyjwt
    from jwt import PyJWKClient

    try:
        supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        jwt_secret = os.getenv("JWT_SECRET")
        supabase_url = os.getenv("SUPABASE_URL", "")

        # Read token header to determine algorithm
        claimed_alg = None
        try:
            unverified_header = pyjwt.get_unverified_header(token)
            claimed_alg = unverified_header.get("alg")
        except Exception:
            pass

        payload = None

        # Strategy 1: JWKS for ES256/RS256 tokens
        if supabase_url and claimed_alg in ("ES256", "RS256"):
            try:
                jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
                jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600)
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = pyjwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256", "RS256"],
                    audience="authenticated",
                    options={"verify_exp": True, "require": ["sub", "exp"]},
                )
                logger.debug(f"[WS] JWT verified via JWKS ({claimed_alg})")
            except pyjwt.ExpiredSignatureError:
                logger.debug("[WS] Token expired")
                return None
            except Exception as e:
                logger.error(f"[WS] JWKS verification failed: {e}")

        # Strategy 2: HS256 shared secret
        if not payload:
            secrets = [s for s in [supabase_jwt_secret, jwt_secret] if s]
            for secret in secrets:
                try:
                    payload = pyjwt.decode(
                        token,
                        secret,
                        algorithms=["HS256"],
                        audience="authenticated",
                        options={"verify_exp": True, "require": ["sub", "exp"]},
                    )
                    logger.debug("[WS] JWT verified via shared secret (HS256)")
                    break
                except pyjwt.ExpiredSignatureError:
                    logger.debug("[WS] Token expired")
                    return None
                except Exception:
                    continue

        if not payload:
            logger.warning("[WS] All JWT verification strategies failed")
            return None

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
