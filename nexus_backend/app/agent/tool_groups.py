"""Agent工具分层配置
P1-4: 按场景分组工具,避免上下文溢出
"""

# 按场景分组工具
TOOL_GROUPS = {
    "crm": [
        "search_customers",
        "create_lead",
        "update_customer",
    ],
    "hr": [
        "search_employees",
        "create_leave_request",
        "search_attendance",
    ],
    "finance": [
        "search_invoices",
        "create_expense_claim",
        "search_contracts",
    ],
    "general": [
        "search_web",
        "send_email",
        "create_calendar_event",
    ]
}


def get_tools_for_scene(scene: str) -> list[str]:
    """根据场景获取工具列表"""
    return TOOL_GROUPS.get(scene, TOOL_GROUPS["general"])
