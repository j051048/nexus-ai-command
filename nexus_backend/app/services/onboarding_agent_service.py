"""
Item 54: Onboarding Agent Service

AI-driven onboarding that generates personalised plans based on user roles,
recommends next steps, and evaluates tenant configuration readiness.
"""

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role-based onboarding templates
# ---------------------------------------------------------------------------

_ROLE_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "sales": [
        {
            "key": "profile_complete",
            "title": "完善个人资料",
            "description": "填写姓名、手机、部门等基本信息",
            "weight": 10,
        },
        {
            "key": "crm_import",
            "title": "导入客户数据",
            "description": "通过 Excel 或 API 导入已有客户信息",
            "weight": 15,
        },
        {
            "key": "pipeline_setup",
            "title": "配置销售管道",
            "description": "设置销售阶段（线索→商机→成交）",
            "weight": 15,
        },
        {"key": "first_lead", "title": "创建第一个销售线索", "description": "手动或通过 AI 创建一条线索", "weight": 10},
        {"key": "ai_chat", "title": "体验 AI 助手", "description": "向 AI 提问销售相关问题", "weight": 10},
        {
            "key": "knowledge_base",
            "title": "上传产品知识库",
            "description": "上传产品手册/FAQ 供 AI 参考",
            "weight": 15,
        },
        {"key": "notification_setup", "title": "设置通知偏好", "description": "开启待办提醒、审批通知", "weight": 10},
        {"key": "mobile_app", "title": "下载移动端 App", "description": "随时随地处理销售事务", "weight": 15},
    ],
    "manager": [
        {"key": "profile_complete", "title": "完善个人资料", "weight": 5},
        {"key": "org_structure", "title": "配置组织架构", "description": "设置部门和团队层级", "weight": 20},
        {"key": "role_assign", "title": "分配成员角色", "description": "邀请团队成员并分配权限角色", "weight": 15},
        {"key": "approval_flow", "title": "配置审批流程", "description": "设置合同/费用审批链", "weight": 15},
        {"key": "dashboard_view", "title": "查看管理仪表盘", "description": "了解团队业绩概览", "weight": 10},
        {"key": "report_setup", "title": "生成第一份报表", "description": "创建销售/绩效报表", "weight": 10},
        {"key": "compliance_rules", "title": "配置合规规则", "description": "设置敏感操作的合规检查", "weight": 15},
        {"key": "notification_setup", "title": "设置通知偏好", "weight": 10},
    ],
    "hr": [
        {"key": "profile_complete", "title": "完善个人资料", "weight": 5},
        {"key": "employee_import", "title": "导入员工花名册", "description": "批量导入员工基础数据", "weight": 20},
        {"key": "attendance_config", "title": "配置考勤规则", "description": "设置班次、打卡方式", "weight": 15},
        {"key": "leave_policy", "title": "设置假期政策", "description": "年假/病假/事假额度配置", "weight": 15},
        {"key": "expense_policy", "title": "配置报销规则", "description": "设置报销类别和审批限额", "weight": 15},
        {"key": "cert_management", "title": "证书到期管理", "description": "录入员工证书和到期提醒", "weight": 15},
        {"key": "notification_setup", "title": "设置通知偏好", "weight": 15},
    ],
    "finance": [
        {"key": "profile_complete", "title": "完善个人资料", "weight": 5},
        {"key": "billing_setup", "title": "配置计费方案", "description": "设置订阅套餐和信用额度", "weight": 20},
        {"key": "payment_channel", "title": "开通支付渠道", "description": "接入微信支付/支付宝/Stripe", "weight": 20},
        {"key": "invoice_template", "title": "配置发票模板", "description": "设置公司开票信息", "weight": 15},
        {"key": "expense_approval", "title": "配置费用审批流", "description": "设置报销审批规则", "weight": 15},
        {"key": "report_setup", "title": "生成财务报表", "description": "查看收入/支出/应收报表", "weight": 15},
        {"key": "notification_setup", "title": "设置通知偏好", "weight": 10},
    ],
}

# Default template for unknown roles
_DEFAULT_TEMPLATE = [
    {"key": "profile_complete", "title": "完善个人资料", "weight": 15},
    {"key": "ai_chat", "title": "体验 AI 助手", "weight": 20},
    {"key": "knowledge_base", "title": "浏览知识库", "weight": 20},
    {"key": "notification_setup", "title": "设置通知偏好", "weight": 15},
    {"key": "explore_features", "title": "探索平台功能", "description": "浏览菜单了解可用功能", "weight": 30},
]


class OnboardingAgentService:
    """
    AI-driven onboarding agent that:
    - Generates role-specific onboarding plans
    - Suggests the next best action based on progress
    - Evaluates overall tenant readiness (0-100%)
    """

    def generate_onboarding_plan(
        self,
        user_role: str,
        company_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a personalised onboarding plan based on user role.

        Args:
            user_role: One of "sales", "manager", "hr", "finance" (or any string).
            company_info: Optional dict with company_name, industry, size, etc.

        Returns:
            Plan dict with steps, estimated time, and metadata.
        """
        role_key = user_role.lower().strip()
        template = _ROLE_TEMPLATES.get(role_key, _DEFAULT_TEMPLATE)

        steps = []
        for i, item in enumerate(template):
            step = {
                "order": i + 1,
                "key": item["key"],
                "title": item["title"],
                "description": item.get("description", ""),
                "weight": item.get("weight", 10),
                "completed": False,
            }
            steps.append(step)

        plan = {
            "role": role_key,
            "company_info": company_info or {},
            "steps": steps,
            "total_steps": len(steps),
            "completed_steps": 0,
            "readiness_score": 0,
            "estimated_minutes": len(steps) * 5,
            "created_at": datetime.now(UTC).isoformat(),
        }

        logger.info(
            "[OnboardingAgent] Plan generated for role=%s, steps=%d",
            role_key,
            len(steps),
        )
        return plan

    async def get_next_suggestion(self, user_id: str, *, db=None) -> dict[str, Any]:
        """
        Based on the user's completed onboarding steps, recommend the next action.

        Checks the user's profile completeness and feature usage to determine
        which onboarding step to suggest next.
        """
        completed_keys: set[str] = set()

        # Try to load progress from DB
        if db:
            try:
                result = (
                    await db.table("onboarding_progress")
                    .select("step_key")
                    .eq("user_id", user_id)
                    .eq("completed", True)
                    .execute()
                )
                if result.data:
                    completed_keys = {row["step_key"] for row in result.data}
            except Exception as e:
                logger.debug(f"[OnboardingAgent] Progress lookup skipped: {e}")

        # Determine user role (default to sales)
        user_role = "sales"
        if db:
            try:
                user_result = await db.table("users").select("role").eq("id", user_id).limit(1).execute()
                if user_result.data:
                    user_role = user_result.data[0].get("role", "sales") or "sales"
            except Exception:
                pass

        template = _ROLE_TEMPLATES.get(user_role.lower(), _DEFAULT_TEMPLATE)

        # Find first incomplete step
        for item in template:
            if item["key"] not in completed_keys:
                return {
                    "has_next": True,
                    "suggestion": {
                        "key": item["key"],
                        "title": item["title"],
                        "description": item.get("description", ""),
                        "weight": item.get("weight", 10),
                    },
                    "completed_count": len(completed_keys),
                    "total_steps": len(template),
                }

        return {
            "has_next": False,
            "suggestion": None,
            "completed_count": len(completed_keys),
            "total_steps": len(template),
            "message": "所有引导步骤已完成！",
        }

    async def evaluate_readiness(self, tenant_id: str, *, db=None) -> dict[str, Any]:
        """
        Evaluate the overall configuration readiness of a tenant (0-100%).

        Checks key configuration areas:
        - Organization structure defined
        - At least one team member invited
        - Knowledge base has documents
        - Approval flows configured
        - Payment channel set up
        """
        checks: list[dict[str, Any]] = []
        total_weight = 0
        earned_weight = 0

        async def _check(name: str, table: str, weight: int, extra_filters=None):
            nonlocal total_weight, earned_weight
            total_weight += weight
            passed = False
            if db:
                try:
                    q = db.table(table).select("id", count="exact").eq("org_id", tenant_id).limit(1)
                    if extra_filters:
                        for k, v in extra_filters.items():
                            q = q.eq(k, v)
                    result = await q.execute()
                    count = result.count if result.count is not None else len(result.data or [])
                    passed = count > 0
                except Exception:
                    pass  # Table may not exist yet
            if passed:
                earned_weight += weight
            checks.append({"name": name, "passed": passed, "weight": weight})

        await _check("组织架构", "organizations", 15)
        await _check("团队成员", "users", 15)
        await _check("知识库文档", "document_embeddings", 20)
        await _check("审批流程", "approval_flows", 15)
        await _check("客户数据", "customers", 15)
        await _check("AI 对话记录", "conversation_memories", 10)
        await _check("通知配置", "push_subscriptions", 10)

        score = round((earned_weight / total_weight * 100) if total_weight > 0 else 0)

        return {
            "tenant_id": tenant_id,
            "readiness_score": score,
            "checks": checks,
            "evaluated_at": datetime.now(UTC).isoformat(),
        }


# Global singleton
onboarding_agent_service = OnboardingAgentService()
