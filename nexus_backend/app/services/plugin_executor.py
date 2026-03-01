"""
Plugin Executor Framework — executes installed marketplace plugins.

Provides a unified execution interface for all plugin categories:
- ERP connectors (Kingdee, Yonyou): sync data, query records
- Notification plugins (WeCom, DingTalk): send messages
- Productivity plugins (AI Report, Email Digest): generate content
- Security plugins (Compliance Check): run audits

Each executor handles the specific API protocol of its target system.

P0-3 Security: Added sandbox isolation with:
- URL allowlist validation (SSRF protection)
- Execution timeout enforcement
- Output size limits
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# P0-3: SSRF protection — only allow these domains for outbound requests
ALLOWED_DOMAINS: set[str] = {
    # Notification webhooks
    "qyapi.weixin.qq.com",
    "oapi.dingtalk.com",
    # ERP domains — add your actual domains here
    "api.kingdee.com",
    "api.yonyou.com",
}

# P0-3: Limits
PLUGIN_TIMEOUT_SECONDS = 30
PLUGIN_MAX_OUTPUT_SIZE = 50_000  # 50KB max output


def _validate_url(url: str) -> bool:
    """Validate URL against SSRF allowlist. Block private IPs and unknown domains."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # Block private/internal IPs
        if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False
        # Check if hostname starts with internal ranges
        if hostname.startswith(("10.", "172.16.", "192.168.", "169.254.")):
            return False

        # Check domain allowlist
        return hostname in ALLOWED_DOMAINS
    except Exception:
        return False


def _truncate_output(result: dict) -> dict:
    """Truncate oversized output to prevent memory abuse."""
    import json

    serialized = json.dumps(result, default=str)
    if len(serialized) > PLUGIN_MAX_OUTPUT_SIZE:
        result["_truncated"] = True
        if "data" in result:
            result["data"] = str(result["data"])[:PLUGIN_MAX_OUTPUT_SIZE // 2]
    return result


class BasePluginExecutor(ABC):
    """Abstract executor for a plugin category."""

    @abstractmethod
    async def execute(self, action: str, params: dict, config: dict) -> dict:
        """Execute a plugin action with the given params and config."""
        ...

    @abstractmethod
    def supported_actions(self) -> list[str]:
        """Return the list of supported action names."""
        ...


class WebhookNotificationExecutor(BasePluginExecutor):
    """Executor for webhook-based notification plugins (WeCom Bot, DingTalk, etc.)."""

    async def execute(self, action: str, params: dict, config: dict) -> dict:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing webhook_url in plugin config"}

        # P0-3: SSRF protection
        if not _validate_url(webhook_url):
            return {"success": False, "error": f"URL not in allowlist: {urlparse(webhook_url).hostname}"}

        if action == "send_message":
            return await self._send_webhook_message(webhook_url, params)
        elif action == "send_markdown":
            return await self._send_webhook_markdown(webhook_url, params)
        else:
            return {"success": False, "error": f"Unsupported action: {action}"}

    def supported_actions(self) -> list[str]:
        return ["send_message", "send_markdown"]

    async def _send_webhook_message(self, url: str, params: dict) -> dict:
        import httpx

        content = params.get("content", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={"msgtype": "text", "text": {"content": content}},
                )
                return {"success": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def _send_webhook_markdown(self, url: str, params: dict) -> dict:
        import httpx

        title = params.get("title", "通知")
        content = params.get("content", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={"msgtype": "markdown", "markdown": {"title": title, "text": content}},
                )
                return {"success": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}


class ERPConnectorExecutor(BasePluginExecutor):
    """Executor for ERP plugins (Kingdee, Yonyou)."""

    async def execute(self, action: str, params: dict, config: dict) -> dict:
        api_url = config.get("api_url") or config.get("server_url")
        api_key = config.get("api_key") or config.get("token")

        if not api_url:
            return {"success": False, "error": "Missing API URL in plugin config"}

        # P0-3: SSRF protection
        if not _validate_url(api_url):
            return {"success": False, "error": f"URL not in allowlist: {urlparse(api_url).hostname}"}

        if action == "query":
            return await self._query_erp(api_url, api_key, params)
        elif action == "sync":
            return await self._sync_erp(api_url, api_key, params)
        elif action == "health_check":
            return await self._health_check(api_url, api_key)
        else:
            return {"success": False, "error": f"Unsupported action: {action}"}

    def supported_actions(self) -> list[str]:
        return ["query", "sync", "health_check"]

    async def _query_erp(self, api_url: str, api_key: str | None, params: dict) -> dict:
        import httpx

        endpoint = params.get("endpoint", "/api/data")
        query_params = params.get("query", {})
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{api_url.rstrip('/')}{endpoint}", params=query_params, headers=headers)
                return {"success": resp.status_code == 200, "data": resp.json(), "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def _sync_erp(self, api_url: str, api_key: str | None, params: dict) -> dict:
        import httpx

        endpoint = params.get("endpoint", "/api/sync")
        data = params.get("data", {})
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{api_url.rstrip('/')}{endpoint}", json=data, headers=headers)
                return {"success": resp.status_code in (200, 201), "data": resp.json(), "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}

    async def _health_check(self, api_url: str, api_key: str | None) -> dict:
        import httpx

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{api_url.rstrip('/')}/health", headers=headers)
                return {"success": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}


class AIReportExecutor(BasePluginExecutor):
    """Executor for AI report generation plugins."""

    async def execute(self, action: str, params: dict, config: dict) -> dict:
        if action == "generate":
            return await self._generate_report(params, config)
        else:
            return {"success": False, "error": f"Unsupported action: {action}"}

    def supported_actions(self) -> list[str]:
        return ["generate"]

    async def _generate_report(self, params: dict, config: dict) -> dict:
        report_type = params.get("report_type", config.get("report_type", "weekly"))
        try:
            from app.agent.proactive_runner import run_proactive_agent

            user_id = params.get("user_id", "system")
            org_id = params.get("org_id")

            result = await run_proactive_agent(
                prompt=f"请生成一份 {report_type} 智能报表，包含关键业务指标、趋势分析和行动建议。",
                user_id=user_id,
                org_id=org_id,
                agent_name="ai_report",
                scene_code="report_generation",
            )

            return {
                "success": result["success"],
                "report": result.get("response", ""),
                "report_type": report_type,
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}


class ComplianceCheckExecutor(BasePluginExecutor):
    """Executor for compliance/security audit plugins."""

    async def execute(self, action: str, params: dict, config: dict) -> dict:
        if action == "check":
            return await self._run_compliance_check(params)
        else:
            return {"success": False, "error": f"Unsupported action: {action}"}

    def supported_actions(self) -> list[str]:
        return ["check"]

    async def _run_compliance_check(self, params: dict) -> dict:
        content = params.get("content", "")
        if not content:
            return {"success": False, "error": "No content to check"}

        try:
            from app.agent.proactive_runner import run_proactive_agent

            result = await run_proactive_agent(
                prompt=f"请对以下内容进行合规性审查，检查是否存在违规风险：\n\n{content[:3000]}",
                user_id=params.get("user_id", "system"),
                org_id=params.get("org_id"),
                agent_name="compliance_checker",
            )

            return {
                "success": result["success"],
                "compliance_report": result.get("response", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}


# ── Executor Registry ──

EXECUTOR_REGISTRY: dict[str, BasePluginExecutor] = {
    # Notification plugins
    "plugin_wecom_bot": WebhookNotificationExecutor(),
    "plugin_dingtalk": WebhookNotificationExecutor(),
    # ERP plugins
    "plugin_kingdee": ERPConnectorExecutor(),
    "plugin_yonyou": ERPConnectorExecutor(),
    # Productivity plugins
    "plugin_ai_report": AIReportExecutor(),
    "plugin_email_digest": AIReportExecutor(),
    # Security plugins
    "plugin_compliance_check": ComplianceCheckExecutor(),
}


async def execute_plugin(
    plugin_id: str,
    action: str,
    params: dict,
    org_id: str,
    db: Any = None,
) -> dict:
    """
    Main entry point: execute a plugin action.

    1. Look up the installed plugin config from DB
    2. Find the appropriate executor
    3. Execute the action with plugin config + params
    """
    # Get executor
    executor = EXECUTOR_REGISTRY.get(plugin_id)
    if not executor:
        return {"success": False, "error": f"No executor for plugin: {plugin_id}"}

    # Validate action
    if action not in executor.supported_actions():
        return {
            "success": False,
            "error": f"Unsupported action '{action}'. Supported: {executor.supported_actions()}",
        }

    # Get plugin config from DB
    config = {}
    if db:
        try:
            result = (
                await db.table("installed_plugins")
                .select("config, is_active")
                .eq("organization_id", org_id)
                .eq("plugin_id", plugin_id)
                .single()
                .execute()
            )
            if not result.data:
                return {"success": False, "error": f"Plugin {plugin_id} is not installed"}
            if not result.data.get("is_active"):
                return {"success": False, "error": f"Plugin {plugin_id} is disabled"}
            config = result.data.get("config", {})
        except Exception as e:
            logger.warning(f"Failed to load plugin config: {e}")

    # Execute with sandbox isolation
    try:
        result = await asyncio.wait_for(
            executor.execute(action, params, config),
            timeout=PLUGIN_TIMEOUT_SECONDS,
        )
        return _truncate_output(result)
    except TimeoutError:
        logger.error(f"Plugin execution timed out ({plugin_id}/{action})")
        return {"success": False, "error": f"Plugin execution timed out after {PLUGIN_TIMEOUT_SECONDS}s"}
    except Exception as e:
        logger.error(f"Plugin execution failed ({plugin_id}/{action}): {e}")
        return {"success": False, "error": str(e)[:200]}
