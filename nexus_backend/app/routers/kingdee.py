"""Kingdee ERP integration endpoints.

The first launch should expose real integration plumbing, not demo payloads.
These endpoints proxy to a configured Kingdee-compatible HTTP gateway and fail
closed when credentials are missing.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

router = APIRouter(prefix="/api/kingdee", tags=["Kingdee"])

DEFAULT_TIMEOUT_SECONDS = 15.0


def _required_setting(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    raise api_error(
        ErrorCode.INTEGRATION_CONNECT_FAILED,
        details={
            "provider": "kingdee",
            "missing": names[0],
            "hint": "Configure KINGDEE_BASE_URL and KINGDEE_API_KEY before enabling Kingdee workflows.",
        },
    )


def _endpoint_url(path_template_env: str, default_path: str, **params: str) -> str:
    base_url = (
        _required_setting("KINGDEE_BASE_URL", "KINGDEE_K3CLOUD_BASE_URL").rstrip("/")
        + "/"
    )
    path_template = os.getenv(path_template_env, default_path).lstrip("/")
    path = path_template.format(**params)
    return urljoin(base_url, path)


def _headers(org_id: str, user_id: str) -> dict[str, str]:
    api_key = _required_setting("KINGDEE_API_KEY", "KINGDEE_K3CLOUD_API_KEY")
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Nexus-Organization-ID": org_id,
        "X-Nexus-User-ID": user_id,
    }


def _parse_response(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    return {"text": response.text}


async def _kingdee_identity(
    request: Request,
    user_id: str = Depends(get_current_user_id),
) -> tuple[str, str]:
    """Resolve Kingdee auth before any integration or payload validation work."""
    org_id = await get_current_org_id(request)
    return user_id, org_id


async def _kingdee_request(
    method: str,
    url: str,
    *,
    org_id: str,
    user_id: str,
    json: dict[str, Any] | None = None,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            response = await client.request(
                method,
                url,
                headers=_headers(org_id, user_id),
                json=json,
            )
            response.raise_for_status()
            return _parse_response(response)
    except httpx.TimeoutException as exc:
        raise api_error(
            ErrorCode.INTEGRATION_CONNECT_FAILED,
            details={"provider": "kingdee", "reason": "timeout"},
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise api_error(
            ErrorCode.INTEGRATION_SYNC_FAILED,
            details={
                "provider": "kingdee",
                "status_code": exc.response.status_code,
                "response": exc.response.text[:500],
            },
        ) from exc
    except httpx.HTTPError as exc:
        raise api_error(
            ErrorCode.INTEGRATION_CONNECT_FAILED,
            details={"provider": "kingdee", "reason": type(exc).__name__},
        ) from exc


@router.get("/inventory/{item_id}")
async def get_inventory(
    item_id: str,
    identity: tuple[str, str] = Depends(_kingdee_identity),
):
    """Query inventory from the configured Kingdee gateway."""
    user_id, org_id = identity
    url = _endpoint_url(
        "KINGDEE_INVENTORY_PATH",
        "/inventory/{item_id}",
        item_id=item_id,
    )
    data = await _kingdee_request("GET", url, org_id=org_id, user_id=user_id)
    return api_success(data={"provider": "kingdee", "inventory": data})


@router.post("/sync/salary")
async def sync_salary(
    request: Request,
    identity: tuple[str, str] = Depends(_kingdee_identity),
):
    """Send salary sync payload to the configured Kingdee gateway."""
    user_id, org_id = identity
    payload = await request.json()
    url = _endpoint_url("KINGDEE_SALARY_SYNC_PATH", "/salary/sync")
    data = await _kingdee_request(
        "POST",
        url,
        org_id=org_id,
        user_id=user_id,
        json={**payload, "organization_id": org_id, "requested_by": user_id},
    )
    return api_success(data={"provider": "kingdee", "sync_result": data})
