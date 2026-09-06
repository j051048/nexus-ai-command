"""Tenant-scoped business checks for the tools that actually mutate records."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecordCheck:
    table: str
    argument: str
    tenant_column: str = "organization_id"


PRE_FLIGHT_RULES: dict[str, RecordCheck] = {
    "update_customer": RecordCheck("customers", "customer_id"),
    "update_customer_stage": RecordCheck("customers", "customer_id"),
    "add_follow_up": RecordCheck("customers", "customer_id"),
    "update_asset": RecordCheck("assets", "asset_id"),
    "transfer_asset": RecordCheck("assets", "asset_id"),
    "update_work_order": RecordCheck("work_orders", "order_id"),
}


async def run_preflight_checks(
    tool_name: str,
    tool_args: dict[str, Any],
    supabase_client: Any = None,
    *,
    org_id: str | None = None,
) -> tuple[bool, str]:
    rule = PRE_FLIGHT_RULES.get(tool_name)
    if rule is None:
        return True, ""
    record_id = tool_args.get(rule.argument)
    if not isinstance(record_id, str) or not record_id.strip():
        return False, f"缺少有效参数：{rule.argument}"
    if not org_id or supabase_client is None:
        return False, "无法验证企业权限，请重新登录或稍后重试"
    try:
        result = await (
            supabase_client.table(rule.table)
            .select("id")
            .eq(rule.tenant_column, org_id)
            .eq("id", record_id)
            .limit(1)
            .execute()
        )
    except Exception:  # broad-except: required checks must fail closed
        logger.exception("Required preflight failed: tool=%s", tool_name)
        return False, "暂时无法验证记录，操作未执行，请稍后重试"
    if not result.data:
        return False, "记录不存在或当前企业无权访问"
    return True, ""
