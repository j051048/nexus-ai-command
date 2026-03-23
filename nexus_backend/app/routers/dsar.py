"""
GDPR DSAR (Data Subject Access Request) Endpoints

Provides:
- POST /api/dsar/export          — Initiate data export request
- GET  /api/dsar/export/{id}     — Query export status
- POST /api/dsar/delete          — Initiate data deletion (Right to be Forgotten)
- GET  /api/dsar/delete/{id}     — Query deletion status
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import api_success
from app.services.dsar_service import DSARService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dsar", tags=["DSAR (GDPR)"])

# P0 Fix: TTL cache with maxsize to prevent unbounded memory growth
_DSAR_CACHE_MAXSIZE = 1000
_DSAR_CACHE_TTL = 86400  # 24 hours
_dsar_requests: dict[str, dict[str, Any]] = {}


def _dsar_cache_cleanup() -> None:
    """Evict expired entries from the DSAR request cache."""
    if len(_dsar_requests) <= _DSAR_CACHE_MAXSIZE:
        return
    now = time.time()
    expired_keys = [
        k for k, v in _dsar_requests.items()
        if now - v.get("_ts", 0) > _DSAR_CACHE_TTL
    ]
    for k in expired_keys:
        del _dsar_requests[k]
    # If still over limit after TTL eviction, remove oldest entries
    if len(_dsar_requests) > _DSAR_CACHE_MAXSIZE:
        sorted_keys = sorted(_dsar_requests, key=lambda k: _dsar_requests[k].get("_ts", 0))
        for k in sorted_keys[: len(_dsar_requests) - _DSAR_CACHE_MAXSIZE]:
            del _dsar_requests[k]


def _dsar_cache_set(request_id: str, data: dict[str, Any]) -> None:
    """Insert into the DSAR cache with automatic cleanup."""
    _dsar_cache_cleanup()
    data["_ts"] = time.time()
    _dsar_requests[request_id] = data


def _get_dsar_service() -> DSARService:
    """Factory for DSARService — injects Supabase client."""
    from app.core.database import supabase

    if not supabase:
        raise HTTPException(status_code=503, detail="Database not configured")
    return DSARService(supabase)


# ── Request/Response Models ──


class DSARExportRequest(BaseModel):
    reason: str | None = Field(None, description="Optional reason for the data export request")


class DSARDeleteRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for data deletion request")
    confirm: bool = Field(False, description="Must be true to confirm deletion")


class DSARStatusResponse(BaseModel):
    request_id: str
    type: str  # "export" or "delete"
    status: str  # "pending", "processing", "completed", "failed"
    created_at: str
    completed_at: str | None = None
    result: dict[str, Any] | None = None


# ── Export Endpoints ──


@router.post("/export", response_model=dict)
async def initiate_export(
    body: DSARExportRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Initiate a GDPR data export (Data Portability, Article 20).

    Collects all user data across system tables and returns a downloadable JSON.
    """
    request_id = str(uuid.uuid4())
    _dsar_cache_set(request_id, {
        "request_id": request_id,
        "type": "export",
        "user_id": user_id,
        "status": "processing",
        "reason": body.reason,
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "result": None,
    })

    try:
        service = _get_dsar_service()
        result = await service.export_user_data(user_id)
        _dsar_requests[request_id]["status"] = result.get("status", "completed")
        _dsar_requests[request_id]["completed_at"] = datetime.now(UTC).isoformat()
        _dsar_requests[request_id]["result"] = result
        logger.info(f"DSAR export completed for user {user_id}, request {request_id}")
    except Exception as e:
        logger.error(f"DSAR export failed for user {user_id}: {e}")
        _dsar_requests[request_id]["status"] = "failed"
        _dsar_requests[request_id]["completed_at"] = datetime.now(UTC).isoformat()
        _dsar_requests[request_id]["result"] = {"error": str(e)}
        raise HTTPException(status_code=500, detail="Data export failed")

    return api_success(
        data={"request_id": request_id, "status": _dsar_requests[request_id]["status"]},
        message="Data export request processed",
    )


@router.get("/export/{request_id}", response_model=dict)
async def get_export_status(
    request_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Query the status of a data export request."""
    record = _dsar_requests.get(request_id)
    if not record or record["type"] != "export":
        raise HTTPException(status_code=404, detail="Export request not found")
    if record["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return api_success(
        data={
            "request_id": record["request_id"],
            "type": record["type"],
            "status": record["status"],
            "created_at": record["created_at"],
            "completed_at": record.get("completed_at"),
            "result": record.get("result"),
        },
    )


# ── Delete Endpoints (Right to be Forgotten) ──


@router.post("/delete", response_model=dict)
async def initiate_delete(
    body: DSARDeleteRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Initiate a GDPR data deletion request (Right to be Forgotten, Article 17).

    This will anonymize personal data across all system tables.
    Audit logs are retained (anonymized) per legal obligation.
    Requires explicit confirmation (confirm=true).
    """
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Data deletion requires explicit confirmation. Set confirm=true to proceed.",
        )

    request_id = str(uuid.uuid4())
    _dsar_cache_set(request_id, {
        "request_id": request_id,
        "type": "delete",
        "user_id": user_id,
        "status": "processing",
        "reason": body.reason,
        "created_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "result": None,
    })

    try:
        service = _get_dsar_service()
        result = await service.delete_user_data(user_id)
        _dsar_requests[request_id]["status"] = result.get("status", "completed")
        _dsar_requests[request_id]["completed_at"] = datetime.now(UTC).isoformat()
        _dsar_requests[request_id]["result"] = result
        logger.info(f"DSAR delete completed for user {user_id}, request {request_id}")
    except Exception as e:
        logger.error(f"DSAR delete failed for user {user_id}: {e}")
        _dsar_requests[request_id]["status"] = "failed"
        _dsar_requests[request_id]["completed_at"] = datetime.now(UTC).isoformat()
        _dsar_requests[request_id]["result"] = {"error": str(e)}
        raise HTTPException(status_code=500, detail="Data deletion failed")

    return api_success(
        data={"request_id": request_id, "status": _dsar_requests[request_id]["status"]},
        message="Data deletion request processed",
    )


@router.get("/delete/{request_id}", response_model=dict)
async def get_delete_status(
    request_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Query the status of a data deletion request."""
    record = _dsar_requests.get(request_id)
    if not record or record["type"] != "delete":
        raise HTTPException(status_code=404, detail="Delete request not found")
    if record["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Redact full result details for delete requests (only show summary)
    result_summary = None
    if record.get("result"):
        result_summary = {
            "status": record["result"].get("status"),
            "tables_processed": list(record["result"].get("actions", {}).keys()),
            "errors": record["result"].get("errors", []),
        }

    return api_success(
        data={
            "request_id": record["request_id"],
            "type": record["type"],
            "status": record["status"],
            "created_at": record["created_at"],
            "completed_at": record.get("completed_at"),
            "result": result_summary,
        },
    )
