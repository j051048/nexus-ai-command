"""
Robot / RPA Command Endpoint MVP.

Provides a stub interface for future robot and RPA device management.  All
endpoints return synthetic data with development warnings so that frontend
integration work can proceed before real device drivers are available.

Endpoints:
    POST /api/robot/command           - Queue a command for a robot device
    GET  /api/robot/devices           - List registered devices
    GET  /api/robot/status/{device_id} - Get device status
"""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/robot", tags=["Robot/RPA"])

_DEV_WARNING = "Robot/RPA interface is in development. No real device connections."


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CommandType(str, Enum):
    """Supported robot command types."""
    MOVE = "move"
    CLICK = "click"
    TYPE = "type"
    SCREENSHOT = "screenshot"
    RUN_SCRIPT = "run_script"
    CUSTOM = "custom"


class CommandPriority(str, Enum):
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
    parameters: Dict[str, Any] = Field(
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
    last_seen: Optional[str] = None
    capabilities: List[str] = []


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
    devices: List[DeviceInfo]
    count: int
    _is_stub: bool = True
    _dev_warning: str = _DEV_WARNING


class DeviceStatusResponse(BaseModel):
    """Response for a device status query."""
    device_id: str
    status: str
    last_heartbeat: Optional[str] = None
    current_task: Optional[str] = None
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
    queued_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "[Robot] command_queued command_id=%s device=%s type=%s user=%s (stub)",
        command_id,
        command.device_id,
        command.command_type.value,
        user_id,
    )

    return api_success(data=CommandResponse(
        command_id=command_id,
        device_id=command.device_id,
        command_type=command.command_type.value,
        status="queued",
        queued_at=queued_at,
        _is_stub=True,
        _dev_warning=_DEV_WARNING,
    ).model_dump())


@router.get("/devices")
async def list_devices(
    user_id: str = Depends(get_current_user_id),
):
    """List all registered robot devices.

    Currently returns an empty list with a development warning since the
    device registry has not been implemented yet.
    """
    logger.info("[Robot] list_devices called by user=%s (stub)", user_id)

    return api_success(data=DeviceListResponse(
        devices=[],
        count=0,
        _is_stub=True,
        _dev_warning=_DEV_WARNING,
    ).model_dump())


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

    return api_success(data=DeviceStatusResponse(
        device_id=device_id,
        status="offline",
        last_heartbeat=None,
        current_task=None,
        queue_depth=0,
        _is_stub=True,
        _dev_warning=_DEV_WARNING,
    ).model_dump())
