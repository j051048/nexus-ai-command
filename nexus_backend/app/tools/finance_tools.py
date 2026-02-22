"""
财务管理工具集
实现报销、预算、薪资查询等财务场景的 AI 自动化
"""

from datetime import datetime
from typing import Any

from app.core.database import supabase

from .base_tool import BaseTool


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


class ExpenseClaimTool(BaseTool):
    """报销申请工具 - 支持智能识别和自动归类"""

    name = "create_expense_claim"
    description = "创建费用报销申请。当用户说'报销'、'我花了XX钱'、'帮我报个账'时调用。支持差旅、招待、办公等类型。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "expense_type": {
                "type": "string",
                "enum": [
                    "travel",
                    "entertainment",
                    "office",
                    "transportation",
                    "communication",
                    "other",
                ],
                "description": "费用类型: travel(差旅), entertainment(招待), office(办公), transportation(交通), communication(通讯), other(其他)",
            },
            "amount": {"type": "number", "description": "金额（元）"},
            "description": {"type": "string", "description": "费用说明"},
            "expense_date": {
                "type": "string",
                "description": "消费日期，格式 YYYY-MM-DD",
            },
            "project_name": {
                "type": "string",
                "description": "关联项目名称（可选，用于成本归集）",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "招待费用的参与人员（招待类型必填）",
            },
        },
        "required": ["expense_type", "amount"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        expense_type = args.get("expense_type", "other")
        amount = float(args.get("amount", 0))
        description = args.get("description", "")
        expense_date = args.get("expense_date", datetime.now().strftime("%Y-%m-%d"))
        project_name = args.get("project_name")
        attendees = args.get("attendees", [])

        if amount <= 0:
            return "❌ 报销金额必须大于0"

        # 获取用户信息
        user_res = (
            await client.table("users")
            .select("name, department")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if not user_res.data:
            return "❌ 无法获取用户信息"

        user = user_res.data

        # 费用类型中文映射和标准
        type_config = {
            "travel": {"name": "差旅费", "daily_limit": 1500, "auto_limit": 500},
            "entertainment": {
                "name": "业务招待费",
                "per_person_limit": 200,
                "auto_limit": 300,
            },
            "office": {"name": "办公用品", "auto_limit": 500},
            "transportation": {"name": "交通费", "auto_limit": 200},
            "communication": {"name": "通讯费", "auto_limit": 200},
            "other": {"name": "其他费用", "auto_limit": 300},
        }

        config_info = type_config.get(expense_type, type_config["other"])

        # 合规检查
        compliance_issues = []
        compliance_passed = True

        # 招待费检查
        if expense_type == "entertainment":
            if not attendees:
                compliance_issues.append("⚠️ 招待费用建议填写参与人员")
            else:
                per_person = amount / len(attendees)
                if per_person > config_info.get("per_person_limit", 200):
                    compliance_issues.append(
                        f"⚠️ 人均消费 ¥{per_person:.0f} 超过标准 ¥{config_info['per_person_limit']}"
                    )
                    compliance_passed = False

        # 差旅费检查
        if expense_type == "travel" and amount > config_info.get("daily_limit", 1500):
            compliance_issues.append(
                f"⚠️ 单日差旅费 ¥{amount:.0f} 超过标准 ¥{config_info['daily_limit']}"
            )

        # 确定审批级别
        auto_limit = config_info.get("auto_limit", 300)
        if amount <= auto_limit and compliance_passed:
            approval_status = "approved"
            approval_note = f"金额 ≤¥{auto_limit}，已自动审批"
        elif amount <= 2000:
            approval_status = "pending"
            _approval_level = "manager"
            approval_note = "需直属领导审批"
        elif amount <= 10000:
            approval_status = "pending"
            _approval_level = "director"
            approval_note = "需部门总监审批"
        else:
            approval_status = "pending"
            _approval_level = "cfo"
            approval_note = "需财务总监审批"

        # 查找关联项目
        project_id = None
        if project_name:
            proj_res = (
                await client.table("projects")
                .select("id, name")
                .ilike("name", f"%{project_name}%")
                .limit(1)
                .execute()
            )
            if proj_res.data:
                project_id = proj_res.data[0]["id"]
                project_name = proj_res.data[0]["name"]

        # 创建报销记录（使用现有的 approval_requests 表）
        expense_data = {
            "submitted_by": user_id,
            "type": "expense",
            "amount": amount,
            "description": f"[{config_info['name']}] {description}",
            "status": approval_status,
            "metadata": {
                "expense_type": expense_type,
                "expense_date": expense_date,
                "project_id": project_id,
                "project_name": project_name,
                "attendees": attendees,
                "compliance_check": {
                    "passed": compliance_passed,
                    "issues": compliance_issues,
                },
            },
        }

        result = await client.table("approval_requests").insert(expense_data).execute()

        if not result.data:
            return "❌ 创建报销申请失败，请稍后重试"

        # request_id = result.data[0]["id"]

        # 如果需要人工审批，发送通知
        if approval_status == "pending":
            approvers = (
                await client.table("users")
                .select("id")
                .in_("role", ["manager", "founder"])
                .execute()
            )
            for approver in approvers.data or []:
                await client.table("notifications").insert(
                    {
                        "user_id": approver["id"],
                        "title": "💰 新的报销申请",
                        "content": f"{user['name']} 提交了 {config_info['name']} ¥{amount:.2f}",
                        "type": "info",
                    }
                ).execute()

        # 构建返回信息
        response = f"""✅ 报销申请已提交！

💰 **报销详情**
- 类型: {config_info['name']}
- 金额: ¥{amount:.2f}
- 日期: {expense_date}
- 说明: {description or "无"}
- 关联项目: {project_name or "无"}
"""

        if expense_type == "entertainment" and attendees:
            response += f"- 参与人员: {', '.join(attendees)} ({len(attendees)}人，人均¥{amount/len(attendees):.0f})\n"

        response += f"""
🔍 **合规检查**
{chr(10).join(compliance_issues) if compliance_issues else "✅ 所有检查通过"}

🔄 **审批状态**
- {approval_note}
- 状态: {"✅ 已自动审批，预计3个工作日到账" if approval_status == "approved" else "⏳ 等待审批中"}
"""

        return response


class ExpenseQueryTool(BaseTool):
    """报销查询工具"""

    name = "query_expense_status"
    description = "查询报销申请状态、报销历史、到账情况等"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["my_claims", "pending", "paid_history"],
                "description": "查询类型: my_claims(我的报销), pending(待处理), paid_history(已到账)",
            },
            "time_range": {
                "type": "string",
                "enum": ["this_month", "last_month", "this_year"],
                "description": "时间范围",
            },
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        # 查询该用户的报销申请
        claims = (
            await client.table("approval_requests")
            .select("*")
            .eq("submitted_by", user_id)
            .eq("type", "expense")
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        if not claims.data:
            return "📋 您最近没有报销记录。"

        status_icons = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "paid": "💰",
        }

        result = "💰 **您最近的报销记录**\n\n"

        total_pending = 0
        total_approved = 0

        for claim in claims.data:
            status_icon = status_icons.get(claim["status"], "❓")
            amount = float(claim.get("amount", 0))
            desc = claim.get("description", "")[:30]

            if claim["status"] == "pending":
                total_pending += amount
            elif claim["status"] == "approved":
                total_approved += amount

            result += f"{status_icon} ¥{amount:.2f} - {desc}\n"

        result += "\n📊 **汇总**\n"
        result += f"- 待审批: ¥{total_pending:.2f}\n"
        result += f"- 已批准待付款: ¥{total_approved:.2f}\n"

        return result


class BudgetQueryTool(BaseTool):
    """预算查询工具"""

    name = "query_budget"
    description = "查询部门或项目的预算使用情况"
    required_role = "manager"

    parameters = {
        "type": "object",
        "properties": {
            "department": {"type": "string", "description": "部门名称"},
            "project_name": {"type": "string", "description": "项目名称"},
            "category": {
                "type": "string",
                "enum": ["travel", "marketing", "office", "hr", "all"],
                "description": "预算类别",
            },
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        args.get("department")
        client = _get_client(config)
        # 获取用户部门
        user_res = (
            await client.table("users")
            .select("department, role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if not user_res.data:
            return "❌ 无法获取用户信息"

        return "📊 暂无预算数据。\n\n💡 预算管理功能正在建设中，请联系管理员配置部门预算。"


class SalaryQueryTool(BaseTool):
    """薪资查询工具"""

    name = "query_salary"
    description = "查询个人薪资明细、到账记录等（仅能查询自己的薪资）"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "month": {
                "type": "string",
                "description": "查询月份，格式 YYYY-MM，默认当月",
            },
            "detail_type": {
                "type": "string",
                "enum": ["breakdown", "history", "tax"],
                "description": "查询类型: breakdown(明细), history(历史), tax(个税)",
            },
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        month = args.get("month", datetime.now().strftime("%Y-%m"))
        client = _get_client(config)
        try:
            result = (
                await client.table("hr_salary_records")
                .select("*")
                .eq("user_id", user_id)
                .eq("period", month)
                .maybe_single()
                .execute()
            )
            if result.data:
                d = result.data
                return f"""💰 {month} 薪资明细:

- 基本工资: ¥{d.get('base_salary', 0):,.2f}
- 绩效奖金: ¥{d.get('bonus', 0):,.2f}
- 扣除合计: ¥{d.get('deductions', 0):,.2f}
- 实发工资: ¥{d.get('net_salary', 0):,.2f}
- 发放状态: {d.get('status', '未知')}"""
            return f"💰 未找到 {month} 的薪资记录。请联系人事部门确认。"
        except Exception:
            return "💰 薪资数据表尚未配置。请联系管理员设置薪资模块。"


class InvoiceOCRTool(BaseTool):
    """发票识别工具"""

    name = "recognize_invoice"
    description = "识别上传的发票图片，自动提取金额、日期、类型等信息"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "image_url": {"type": "string", "description": "发票图片URL"},
            "invoice_type": {
                "type": "string",
                "enum": ["general", "vat", "train", "taxi", "hotel"],
                "description": "发票类型（可选，自动识别）",
            },
        },
        "required": ["image_url"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        image_url = args.get("image_url", "")
        invoice_type = args.get("invoice_type", "auto")

        if not image_url:
            return "❌ 请提供发票图片URL。"

        try:
            from app.services.ai_service import AIService

            type_hint = f"（提示类型: {invoice_type}）" if invoice_type != "auto" else ""
            result = await AIService.call_llm(
                f"请识别以下发票信息，提取结构化数据：\n图片URL: {image_url}\n{type_hint}",
                "你是发票OCR识别专家。请从发票中提取以下字段并以中文列表格式返回：\n"
                "- 发票号码\n- 开票日期\n- 金额（不含税）\n- 税额\n- 价税合计\n"
                "- 开票单位\n- 发票类型\n如果无法识别某字段，标注'未识别'。"
            )
            return f"🧾 发票识别结果:\n\n{result}"
        except Exception as e:
            return f"🧾 发票识别失败: {str(e)}\n\n请手动填写发票信息。"
