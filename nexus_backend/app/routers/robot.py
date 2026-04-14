"""
Robot / RPA Command Endpoint MVP + WeChat Work Integration.

Provides:
1. Stub interface for future robot and RPA device management
2. WeChat Work (企业微信) callback endpoints for message integration

Robot Endpoints:
    POST /api/robot/command           - Queue a command for a robot device
    GET  /api/robot/devices           - List registered devices
    GET  /api/robot/status/{device_id} - Get device status

WeChat Work Endpoints:
    GET  /api/wecom/callback          - URL verification (企微验证)
    POST /api/wecom/callback          - Message callback (消息处理)
"""

import logging
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import APIRouter, Depends, Request, Query, Response
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/robot", tags=["Robot/RPA"])

_DEV_WARNING = "Robot/RPA interface is in development. No real device connections."


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommandType(StrEnum):
    """Supported robot command types."""

    MOVE = "move"
    CLICK = "click"
    TYPE = "type"
    SCREENSHOT = "screenshot"
    RUN_SCRIPT = "run_script"
    CUSTOM = "custom"


class CommandPriority(StrEnum):
    """Priority levels for queued commands."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RobotCommand(BaseModel):
    """A command to be executed by a robot device."""

    device_id: str = Field(..., description="Target device identifier")
    command_type: CommandType = Field(..., description="Type of command to execute")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Command-specific parameters",
    )
    priority: CommandPriority = Field(
        default=CommandPriority.NORMAL,
        description="Execution priority",
    )


class DeviceInfo(BaseModel):
    """Information about a registered robot device."""

    device_id: str
    name: str
    status: str
    device_type: str
    last_seen: str | None = None
    capabilities: list[str] = []


class CommandResponse(BaseModel):
    """Response after queuing a robot command."""

    command_id: str
    device_id: str
    command_type: str
    status: str
    queued_at: str
    _is_stub: bool = True
    _dev_warning: str = _DEV_WARNING


class DeviceListResponse(BaseModel):
    """Response for listing registered devices."""

    devices: list[DeviceInfo]
    count: int
    _is_stub: bool = True
    _dev_warning: str = _DEV_WARNING


class DeviceStatusResponse(BaseModel):
    """Response for a device status query."""

    device_id: str
    status: str
    last_heartbeat: str | None = None
    current_task: str | None = None
    queue_depth: int = 0
    _is_stub: bool = True
    _dev_warning: str = _DEV_WARNING


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/command")
async def queue_command(
    command: RobotCommand,
    user_id: str = Depends(get_current_user_id),
):
    """Queue a command for a robot device.

    This is a **stub** endpoint.  The command is acknowledged and assigned a
    tracking ID but no real device communication takes place.
    """
    command_id = str(uuid.uuid4())
    queued_at = datetime.now(UTC).isoformat()

    logger.info(
        "[Robot] command_queued command_id=%s device=%s type=%s user=%s (stub)",
        command_id,
        command.device_id,
        command.command_type.value,
        user_id,
    )

    return api_success(
        data=CommandResponse(
            command_id=command_id,
            device_id=command.device_id,
            command_type=command.command_type.value,
            status="queued",
            queued_at=queued_at,
            _is_stub=True,
            _dev_warning=_DEV_WARNING,
        ).model_dump()
    )


@router.get("/devices")
async def list_devices(
    user_id: str = Depends(get_current_user_id),
):
    """List all registered robot devices.

    Currently returns an empty list with a development warning since the
    device registry has not been implemented yet.
    """
    logger.info("[Robot] list_devices called by user=%s (stub)", user_id)

    return api_success(
        data=DeviceListResponse(
            devices=[],
            count=0,
            _is_stub=True,
            _dev_warning=_DEV_WARNING,
        ).model_dump()
    )


@router.get("/status/{device_id}")
async def get_device_status(
    device_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get the current status of a specific robot device.

    Returns a synthetic ``offline`` status for any device ID since the real
    device communication layer is not yet available.
    """
    logger.info(
        "[Robot] get_device_status device=%s user=%s (stub)",
        device_id,
        user_id,
    )

    return api_success(
        data=DeviceStatusResponse(
            device_id=device_id,
            status="offline",
            last_heartbeat=None,
            current_task=None,
            queue_depth=0,
            _is_stub=True,
            _dev_warning=_DEV_WARNING,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# WeChat Work (企业微信) Endpoints
# ---------------------------------------------------------------------------

wecom_router = APIRouter(prefix="/api/wecom", tags=["WeChat Work"])


@wecom_router.get("/callback")
async def wecom_verify(
    msg_signature: str = Query(..., description="微信签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
    echostr: str = Query("", description="回声字符串"),
):
    """企业微信 URL 验证回调

    企微管理后台配置回调 URL 时，会向此端点发送 GET 请求验证。
    验证通过后返回 echostr 即可。
    """
    from app.services.wecom_service import wecom_service

    is_valid, result = wecom_service.verify_signature(
        msg_signature, timestamp, nonce, echostr
    )

    if is_valid:
        logger.info("[WeCom] URL verification successful")
        return Response(content=result, media_type="text/plain")
    else:
        logger.warning(f"[WeCom] URL verification failed: {result}")
        return Response(content="verification failed", status_code=403)


@wecom_router.post("/callback")
async def wecom_message(
    request: Request,
    msg_signature: str = Query(..., description="微信签名"),
    timestamp: str = Query(..., description="时间戳"),
    nonce: str = Query(..., description="随机数"),
):
    """企业微信消息回调

    接收来自企微的消息推送，处理文本消息并返回 AI 回复。
    非文本消息返回"暂不支持"提示。
    """
    from app.services.wecom_service import wecom_service

    # 验证签名
    is_valid, _ = wecom_service.verify_signature(msg_signature, timestamp, nonce)
    if not is_valid:
        logger.warning("[WeCom] Message signature verification failed")
        return Response(content="invalid signature", status_code=403)

    # 解析消息
    body = await request.body()
    xml_body = body.decode("utf-8")

    # 注意: 实际生产环境需要先解密消息（AES 解密）
    # 此处简化处理，假设消息已解密或使用明文模式
    msg = wecom_service.parse_xml_message(xml_body)

    if not msg:
        return Response(content="", media_type="application/xml")

    msg_type = msg.get("MsgType", "")
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")

    logger.info(f"[WeCom] Received message type={msg_type} from={from_user[:8]}...")

    # 处理文本消息
    if msg_type == "text":
        reply_content = await wecom_service.handle_text_message(msg)
    elif msg_type == "event":
        event_type = msg.get("Event", "")
        if event_type == "subscribe":
            reply_content = "欢迎使用 Nexus AI 助手！发送任何文字消息即可与 AI 对话。"
        else:
            reply_content = ""
    else:
        reply_content = wecom_service.handle_unsupported_message(msg_type)

    if reply_content:
        reply_xml = wecom_service.format_text_reply(from_user, to_user, reply_content)
        return Response(content=reply_xml, media_type="application/xml")

    return Response(content="", media_type="application/xml")


# Expose wecom_router for registration in startup/routers.py
router_wecom = wecom_router
