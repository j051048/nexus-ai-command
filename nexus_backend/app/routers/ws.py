"""
WebSocket Router — provides real-time bidirectional communication.

Endpoints:
  /ws/chat    — Real-time agent chat streaming (alternative to SSE)
  /ws/push    — Server-push channel for notifications and trigger results
"""

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.services.websocket_manager import stream_agent_via_ws, ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# P1-11: Maximum incoming WebSocket message size (64 KB)
WS_MAX_MESSAGE_SIZE = 64 * 1024


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
    user_id, token_exp = await _authenticate_ws(token)
    if not user_id:
        logger.error("[WS/Chat] Auth failed for token starting with: %s***", token[:4])
        await websocket.close(code=4001, reason="Authentication failed")
        return

    connected = await ws_manager.connect(websocket, user_id)
    if not connected:
        return

    # P1: Schedule token expiry check — auto-disconnect when JWT expires
    _token_expiry_task = None
    if token_exp:

        async def _check_token_expiry():
            remaining = token_exp - time.time()
            if remaining > 0:
                await asyncio.sleep(remaining)
            logger.info(f"[WS/Chat] Token expired for user {user_id}, disconnecting")
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "登录已过期，请重新登录",
                        "code": "TOKEN_EXPIRED",
                    }
                )
                await websocket.close(code=4002, reason="Token expired")
            except Exception:
                pass  # Connection may already be closed

        _token_expiry_task = asyncio.create_task(_check_token_expiry())

    try:
        while True:
            # Wait for client message
            raw = await websocket.receive_text()

            # P1-11: Reject oversized messages
            if len(raw) > WS_MAX_MESSAGE_SIZE:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"消息过大（{len(raw)} 字节），上限 {WS_MAX_MESSAGE_SIZE} 字节",
                    }
                )
                continue

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
                await websocket.send_json(
                    {"type": "error", "message": "No messages provided"}
                )
                continue

            # P1 Security: Prompt Firewall + Content Moderation (same as /api/chat)
            last_user_msg = next(
                (m for m in reversed(messages) if m.get("role") == "user"), None
            )
            if last_user_msg:
                user_content = last_user_msg.get("content", "")
                # Layer 1: Prompt Firewall
                try:
                    from app.core.prompt_firewall import prompt_firewall

                    fw_result = await prompt_firewall.scan_input(
                        user_content, user_id=user_id
                    )
                    if not fw_result.is_safe:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"⚠️ 安全拦截: 检测到风险等级 {fw_result.risk_level.value} 的异常输入",
                            }
                        )
                        continue
                    # Use sanitized input
                    if (
                        fw_result.sanitized_input
                        and fw_result.sanitized_input != user_content
                    ):
                        last_user_msg["content"] = fw_result.sanitized_input
                except Exception as e:
                    logger.warning(
                        f"[WS/Chat] Firewall check failed (non-blocking): {e}"
                    )

                # Layer 2: Content Moderation
                try:
                    from app.services.content_moderation import check_user_input

                    is_safe, warning = check_user_input(user_content)
                    if not is_safe:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"⚠️ 安全拦截: {warning}",
                            }
                        )
                        continue
                except Exception as e:
                    logger.warning(
                        f"[WS/Chat] Moderation check failed (non-blocking): {e}"
                    )

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
        if _token_expiry_task and not _token_expiry_task.done():
            _token_expiry_task.cancel()
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
    # 1. 认证（从 query param 获取 token）
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("WS Connection attempt without token")
        await websocket.close(code=1008, reason="Policy violation")
        return

    user_id, _ = await _authenticate_ws(token)
    if not user_id:
        logger.error("[WS/Push] Auth failed for token starting with: %s***", token[:4])
        await websocket.close(code=1008, reason="Policy violation")
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
    from app.services.websocket_manager import (
        MAX_CONNECTIONS_GLOBAL,
        MAX_CONNECTIONS_PER_USER,
    )

    return {
        "active_connections": ws_manager.active_connections,
        "active_users": ws_manager.active_users,
        "limits": {
            "per_user": MAX_CONNECTIONS_PER_USER,
            "global": MAX_CONNECTIONS_GLOBAL,
        },
    }


# ── Internal helpers ──


async def _authenticate_ws(token: str) -> tuple[str | None, float | None]:
    """Authenticate a WebSocket connection via JWT token.

    Returns (user_id, exp_timestamp) on success, (None, None) on failure.

    Reuses the same two-stage strategy as auth.py:
    1. ES256/RS256 → JWKS public key from Supabase
    2. HS256 → shared secret (SUPABASE_JWT_SECRET / JWT_SECRET)
    """
    import os

    import jwt as pyjwt
    from jwt import PyJWKClient, PyJWTError

    try:
        supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        jwt_secret = os.getenv("JWT_SECRET")
        supabase_url = os.getenv("SUPABASE_URL", "")

        unverified_header = {}
        try:
            unverified_header = pyjwt.get_unverified_header(token)
        except Exception as e:
            logger.warning(f"[WS/Auth] Could not read JWT header: {e}")
            return None, None

        claimed_alg = unverified_header.get("alg")
        payload = None

        # --- Strategy 1: JWKS for ES256/RS256 tokens (Typical for Supabase) ---
        if supabase_url and claimed_alg in ("ES256", "RS256"):
            try:
                # Use standard Supabase path for JWKS
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
                logger.debug(f"[WS/Auth] Verified via JWKS ({claimed_alg})")
            except pyjwt.ExpiredSignatureError:
                logger.warning("[WS/Auth] Token expired (JWKS)")
                return None, None
            except Exception as e:
                logger.debug(f"[WS/Auth] JWKS attempt failed (falling back): {e}")

        # --- Strategy 2: HS256 shared secret (Manual tokens or Legacy Supabase) ---
        if not payload:
            secrets = [s for s in [supabase_jwt_secret, jwt_secret] if s]
            if not secrets:
                logger.error("[WS/Auth] No JWT secrets configured in environment")
                return None, None

            for index, secret in enumerate(secrets):
                try:
                    payload = pyjwt.decode(
                        token,
                        secret,
                        algorithms=["HS256"],
                        audience="authenticated",
                        options={"verify_exp": True, "require": ["sub", "exp"]},
                    )
                    logger.debug(f"[WS/Auth] Verified via secret #{index} (HS256)")
                    break
                except pyjwt.ExpiredSignatureError:
                    logger.warning("[WS/Auth] Token expired (HS256)")
                    return None, None
                except PyJWTError as e:
                    logger.debug(
                        f"[WS/Auth] HS256 secret #{index} attempt failed: {str(e)}"
                    )
                    continue

        if not payload:
            logger.warning(
                f"[WS/Auth] Token verification failed for all strategies (Alg: {claimed_alg})"
            )
            return None, None

        user_id = payload.get("sub")
        if not user_id:
            logger.error("[WS/Auth] Payload missing 'sub' field")
            return None, None

        # P1: Extract exp for token expiry monitoring
        token_exp = payload.get("exp")
        return str(user_id), float(token_exp) if token_exp else None
    except Exception as e:
        logger.error(f"[WS/Auth] Unexpected error: {e}", exc_info=True)
        return None, None


async def _get_user_context(user_id: str) -> tuple[str, str | None]:
    """Get user role and org_id for agent context.

    P1 Security: Query uses user_id filter for isolation.
    The global supabase client is acceptable here because we're reading
    the user's own record (filtered by id), not arbitrary tenant data.
    """
    try:
        from app.core.database import supabase

        if supabase:
            result = (
                await supabase.table("users")
                .select("role, org_id")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            if result.data:
                return result.data.get("role", "employee"), result.data.get("org_id")
    except Exception as e:
        logger.warning(f"[WS] Failed to get user context: {e}")
    return "employee", None
