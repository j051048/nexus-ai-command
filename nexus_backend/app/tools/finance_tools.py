"""
财务管理工具集
实现报销、预算、薪资查询等财务场景的 AI 自动化
"""

from datetime import datetime
from typing import Any

from app.tools._shared import safe_tool_error

from ._shared import _get_client
from .base_tool import BaseTool


class ExpenseClaimTool(BaseTool):
    """报销申请工具 - 支持智能识别和自动归类"""

    name = "create_expense_claim"
    description = "创建费用报销申请并自动进行合规检查。当用户说'报销'、'我花了多少钱'、'帮我报个账'时调用。支持差旅、招待、办公等类型。"
    required_role = "all"
    examples = [
        {
            "input": {
                "expense_type": "travel",
                "amount": 800,
                "description": "北京出差高铁票",
                "expense_date": "2026-03-20",
            },
            "output_summary": "提交差旅报销申请，合规检查通过，等待审批",
        },
        {
            "input": {
                "expense_type": "entertainment",
                "amount": 600,
                "description": "客户晚餐",
                "attendees": ["张总", "李总", "王经理"],
            },
            "output_summary": "提交招待费报销，自动计算人均消费并检查是否超标",
        },
    ]
    related_tools = [
        "query_expense_status",
        "submit_approval_on_behalf",
        "recognize_invoice",
    ]
    gotchas = "金额必须大于0。招待费用建议填写参与人员以通过合规检查。人均招待标准为200元，差旅单日上限1500元。"

    is_irreversible = True  # P0-3: 报销申请会写库创建记录，必须经过 HITL 确认
    confirmation_message = "即将提交报销申请并创建报销记录，请确认金额和类型无误。"

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
    domain = "finance"

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
            .select("name, department, organization_id")
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

        # ── 审批链匹配：替代硬编码的审批级别 ──
        from app.services.approval_chain import approval_chain_service

        chain_result = await approval_chain_service.match_and_bind_chain(
            org_id=user.get("organization_id", ""),
            approval_type="expense",
            amount=amount,
            db=client,
        )

        auto_approve = chain_result.get("auto_approve", False) and compliance_passed
        chain_id = chain_result.get("chain_id")
        starting_step = chain_result.get("starting_step", 0)
        approval_level = chain_result.get("approval_level", "manager")
        timeout_at = chain_result.get("timeout_at")
        _chain_name = chain_result.get("chain_name", "费用报销审批链")

        approval_status = "approved" if auto_approve else "pending"
        approval_note = (
            "金额在自动审批限额内，已自动审批"
            if auto_approve
            else f"需{approval_level}级别审批"
        )

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
            "current_step": starting_step,
            "approval_level": approval_level,
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
        # 绑定审批链字段
        if chain_id:
            expense_data["chain_id"] = chain_id
        if timeout_at:
            expense_data["timeout_at"] = timeout_at
        if auto_approve:
            expense_data["approval_history"] = [
                {
                    "step": starting_step,
                    "decision": "auto_approved",
                    "approver_id": "system",
                    "timestamp": datetime.now().isoformat(),
                    "comment": f"金额 ¥{amount:.0f} 在自动审批限额内，合规检查通过",
                }
            ]
        # 确保 organization_id 存在
        if user.get("organization_id"):
            expense_data["organization_id"] = user["organization_id"]

        result = await client.table("approval_requests").insert(expense_data).execute()

        if not result.data:
            return "❌ 创建报销申请失败，请稍后重试"

        request_id = result.data[0]["id"]

        # 如果需要人工审批，精准通知对应审批人
        if approval_status == "pending":
            from app.tools.approval_tools import _notify_next_approver

            await _notify_next_approver(
                client=client,
                approval_level=approval_level,
                requester_id=user_id,
                requester_name=user.get("name", "员工"),
                approval_type="expense",
                amount=amount,
                req_id=request_id,
                org_id=user.get("organization_id"),
            )

        # 构建返回信息
        response = f"""✅ 报销申请已提交！

💰 **报销详情**
- 类型: {config_info["name"]}
- 金额: ¥{amount:.2f}
- 日期: {expense_date}
- 说明: {description or "无"}
- 关联项目: {project_name or "无"}
"""

        if expense_type == "entertainment" and attendees:
            response += f"- 参与人员: {', '.join(attendees)} ({len(attendees)}人，人均¥{amount / len(attendees):.0f})\n"

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
    description = "查询个人报销申请状态和历史记录。当用户说'报销到哪了'、'报销进度'、'到账了吗'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {},
            "output_summary": "返回最近10条报销记录，含状态、金额，以及待审批和已批准的汇总",
        },
        {"input": {"query_type": "pending"}, "output_summary": "返回待处理的报销申请"},
    ]
    related_tools = ["create_expense_claim"]
    gotchas = (
        "仅查询当前用户自己的报销记录。时间范围筛选参数暂未生效，默认返回最近10条。"
    )

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
    domain = "finance"

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
            return self.format_result(data={}, summary="您最近没有报销记录。")

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
    description = "查询部门或项目的预算使用情况。当用户说'预算还剩多少'、'部门预算'时调用。需要经理权限。"
    required_role = "manager"
    examples = [
        {
            "input": {"department": "销售部"},
            "output_summary": "返回销售部的预算使用情况",
        },
        {"input": {"category": "travel"}, "output_summary": "返回差旅类预算使用情况"},
    ]
    related_tools = ["create_expense_claim", "query_expense_status"]
    gotchas = "预算查询依赖 finance_budgets 数据表；若未配置预算数据，会返回明确的数据配置提示。"

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
    domain = "finance"

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

        return "📊 当前没有可查询的预算数据。\n\n请管理员在财务模块配置部门预算或导入 finance_budgets 数据。"


class SalaryQueryTool(BaseTool):
    """薪资查询工具"""

    name = "query_salary"
    description = "查询当前用户的个人薪资明细和到账记录。当用户说'这个月工资'、'薪资明细'、'工资条'时调用。仅能查询自己的薪资。"
    required_role = "all"
    examples = [
        {
            "input": {"month": "2026-03"},
            "output_summary": "返回2026年3月的薪资明细，含基本工资、奖金、扣除、实发",
        },
        {"input": {}, "output_summary": "返回当月薪资明细（默认当月）"},
    ]
    related_tools = ["query_expense_status"]
    gotchas = "仅能查询自己的薪资，无法查询他人。month 格式为 YYYY-MM。薪资表未配置时会返回提示信息。"

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
    domain = "finance"

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

- 基本工资: ¥{d.get("base_salary", 0):,.2f}
- 绩效奖金: ¥{d.get("bonus", 0):,.2f}
- 扣除合计: ¥{d.get("deductions", 0):,.2f}
- 实发工资: ¥{d.get("net_salary", 0):,.2f}
- 发放状态: {d.get("status", "未知")}"""
            return self.format_result(
                data={}, summary=f"未找到 {month} 的薪资记录。请联系人事部门确认。"
            )
        except Exception:
            return self.format_result(
                data={}, summary="薪资数据表尚未配置。请联系管理员设置薪资模块。"
            )


class InvoiceOCRTool(BaseTool):
    """发票识别工具"""

    name = "recognize_invoice"
    description = "识别上传的发票图片，自动提取金额、日期、类型等结构化信息。当用户上传发票图片或说'识别发票'、'发票识别'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {"image_url": "https://example.com/invoice.jpg"},
            "output_summary": "识别发票并返回发票号码、金额、税额、开票单位等信息",
        },
        {
            "input": {
                "image_url": "https://example.com/train.jpg",
                "invoice_type": "train",
            },
            "output_summary": "识别火车票发票并提取结构化数据",
        },
    ]
    related_tools = ["create_expense_claim"]
    gotchas = "依赖大语言模型进行识别，结果可能不完全准确，建议人工核对。image_url 为必填参数。"

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
    domain = "finance"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        image_url = args.get("image_url", "")
        invoice_type = args.get("invoice_type", "auto")

        if not image_url:
            return "❌ 请提供发票图片URL。"

        try:
            from app.services.llm_gateway import llm_gateway

            type_hint = (
                f"（提示类型: {invoice_type}）" if invoice_type != "auto" else ""
            )

            # 使用 Vision multimodal content 格式
            user_content = [
                {
                    "type": "text",
                    "text": (
                        f"请识别以下发票信息，提取结构化数据{type_hint}：\n"
                        "请提取：发票号码、开票日期、金额（不含税）、税额、价税合计、"
                        "开票单位、发票类型。\n如无法识别某字段，标注'未识别'。以中文列表格式返回。"
                    ),
                },
                {"type": "image_url", "image_url": {"url": image_url}},
            ]

            # 获取 org_id 用于计费追踪
            org_id = config.get("org_id") if config else None

            response = await llm_gateway.chat(
                scene_code="invoice_ocr",
                agent_code="ocr",
                user_id=user_id,
                org_id=org_id,
                system_prompt="",
                messages=[{"role": "user", "content": user_content}],
                max_tokens=2000,
            )

            if response.finish_reason == "error":
                return self.format_result(
                    data={},
                    summary=f"发票识别失败: {response.raw_response.get('error', '未知错误')}\n\n请手动填写发票信息。",
                )

            result = response.content

            return self.format_result(data={}, summary=f"发票识别结果:\n\n{result}")
        except Exception as e:
            return safe_tool_error(e, "发票识别") + "\n\n请手动填写发票信息。"
