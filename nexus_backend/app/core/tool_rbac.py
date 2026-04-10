"""
P0-2: 工具 RBAC 白名单系统
"""

import logging

from app.core.database import supabase

logger = logging.getLogger(__name__)

# 工具权限配置
TOOL_PERMISSIONS = {
    "sales_rep": {
        "allowed": [
            "get_customer",
            "search_customers",
            "create_lead",
            "update_lead",
            "get_sales_lead",
            "list_sales_leads",
        ],
        "denied": ["delete_customer", "approve_payment", "delete_contract"],
    },
    "finance": {
        "allowed": [
            "get_invoice",
            "create_payment",
            "get_contract",
            "list_invoices",
            "get_payment_status",
        ],
        "denied": ["delete_invoice", "delete_payment"],
    },
    "manager": {
        "allowed": [
            "approve_expense",
            "approve_leave",
            "get_team_performance",
            "create_approval",
            "update_approval",
        ],
        "denied": ["delete_user", "change_salary"],
    },
    "admin": {"allowed": ["*"], "denied": []},  # 全部权限
}


async def check_tool_permission(
    user_id: str, tool_name: str, org_id: str = "default"
) -> tuple[bool, str]:
    """检查用户是否有权限调用工具"""
    try:
        # 获取用户角色
        result = (
            await supabase.table("users")
            .select("role")
            .eq("id", user_id)
            .eq("org_id", org_id)
            .single()
            .execute()
        )

        if not result.data:
            return False, "用户不存在"

        user_role = result.data.get("role", "user")
        perms = TOOL_PERMISSIONS.get(user_role, {"allowed": [], "denied": []})

        # 检查黑名单
        if tool_name in perms["denied"]:
            return False, f"角色 {user_role} 无权使用工具 {tool_name}"

        # 检查白名单
        if "*" in perms["allowed"] or tool_name in perms["allowed"]:
            return True, ""

        return False, f"角色 {user_role} 未授权工具 {tool_name}"

    except Exception as e:
        logger.error(f"Permission check failed: {e}")
        return False, "权限检查失败"
