"""Safe outbound connector delivery for solution artifacts.

Connector rows store an environment-variable reference, never a credential. The
referenced value may be a HTTPS URL or JSON with ``url`` and optional ``token``.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

_CONFIG_REF_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,119}$")
_SENSITIVE_FIELDS = {
    "standard_cost",
    "gross_margin_percent",
    "cost_usd",
    "internal_note",
    "internal_notes",
}


def _configuration(config_ref: str | None) -> dict[str, Any]:
    if not config_ref or not _CONFIG_REF_RE.fullmatch(config_ref):
        raise ValueError("连接器必须引用合法的服务器环境变量")
    raw = os.getenv(config_ref, "").strip()
    if not raw:
        raise ValueError(f"服务器尚未配置 {config_ref}")
    if raw.startswith("{"):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("连接器配置必须是 JSON 对象")
        return parsed
    return {"url": raw}


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("连接器仅允许 HTTPS 地址")
    try:
        address = ipaddress.ip_address(parsed.hostname)
        if address.is_private or address.is_loopback or address.is_link_local:
            raise ValueError("连接器不允许访问内网地址")
    except ValueError as exc:
        if "不允许" in str(exc):
            raise
    allowed = {
        value.strip().casefold()
        for value in os.getenv("SOLUTION_CONNECTOR_ALLOWED_HOSTS", "").split(",")
        if value.strip()
    }
    if allowed and parsed.hostname.casefold() not in allowed:
        raise ValueError("连接器域名不在服务器允许列表")
    return url


def prepare_solution_payload(
    connector: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    """Enforce explicit capability and remove internal commercial fields."""
    capabilities = {
        str(value).strip().casefold()
        for value in connector.get("capabilities") or []
        if value
    }
    if "solution.delivery" not in capabilities:
        raise ValueError("连接器未授权接收客户方案")
    if "solution.delivery.internal" in capabilities:
        return payload

    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: redact(item)
                for key, item in value.items()
                if str(key).casefold() not in _SENSITIVE_FIELDS
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    return redact(payload)


async def deliver_solution_payload(
    connector: dict[str, Any], payload: dict[str, Any]
) -> dict[str, Any]:
    if connector.get("status") != "active":
        raise ValueError("连接器未启用")
    config = _configuration(connector.get("config_ref"))
    url = _validate_url(str(config.get("url") or ""))
    outbound_payload = prepare_solution_payload(connector, payload)
    headers = {"Content-Type": "application/json", "User-Agent": "Nexus-Solution/1.0"}
    if config.get("token"):
        headers["Authorization"] = f"Bearer {config['token']}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=5)) as client:
        response = await client.post(url, json=outbound_payload, headers=headers)
        response.raise_for_status()
    external_id = response.headers.get("x-request-id")
    try:
        body = response.json()
        if isinstance(body, dict):
            external_id = body.get("id") or body.get("request_id") or external_id
    except ValueError:
        body = None
    return {
        "ok": True,
        "status_code": response.status_code,
        "external_id": external_id,
        "response_received": body is not None,
    }
