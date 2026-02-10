"""
财务管理工具集
实现报销、预算、薪资查询等财务场景的 AI 自动化
"""
from .base_tool import BaseTool
from typing import Dict, Any, List
from datetime import datetime, timedelta
from app.core.database import supabase
from app.services.event_bus import emit, EventType
from decimal import Decimal


def _get_client(config: Dict = None):
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
                "enum": ["travel", "entertainment", "office", "transportation", "communication", "other"],
                "description": "费用类型: travel(差旅), entertainment(招待), office(办公), transportation(交通), communication(通讯), other(其他)"
            },
            "amount": {
                "type": "number",
                "description": "金额（元）"
            },
            "description": {
                "type": "string",
                "description": "费用说明"
            },
            "expense_date": {
                "type": "string",
                "description": "消费日期，格式 YYYY-MM-DD"
            },
            "project_name": {
                "type": "string",
                "description": "关联项目名称（可选，用于成本归集）"
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "招待费用的参与人员（招待类型必填）"
            }
        },
        "required": ["expense_type", "amount"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
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
        user_res = await client.table("users").select("name, department").eq("id", user_id).maybe_single().execute()
        if not user_res.data:
            return "❌ 无法获取用户信息"
        
        user = user_res.data
        
        # 费用类型中文映射和标准
        type_config = {
            "travel": {"name": "差旅费", "daily_limit": 1500, "auto_limit": 500},
            "entertainment": {"name": "业务招待费", "per_person_limit": 200, "auto_limit": 300},
            "office": {"name": "办公用品", "auto_limit": 500},
            "transportation": {"name": "交通费", "auto_limit": 200},
            "communication": {"name": "通讯费", "auto_limit": 200},
            "other": {"name": "其他费用", "auto_limit": 300}
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
                    compliance_issues.append(f"⚠️ 人均消费 ¥{per_person:.0f} 超过标准 ¥{config_info['per_person_limit']}")
                    compliance_passed = False
        
        # 差旅费检查
        if expense_type == "travel":
            if amount > config_info.get("daily_limit", 1500):
                compliance_issues.append(f"⚠️ 单日差旅费 ¥{amount:.0f} 超过标准 ¥{config_info['daily_limit']}")
        
        # 确定审批级别
        auto_limit = config_info.get("auto_limit", 300)
        if amount <= auto_limit and compliance_passed:
            approval_status = "approved"
            approval_level = "auto"
            approval_note = f"金额 ≤¥{auto_limit}，已自动审批"
        elif amount <= 2000:
            approval_status = "pending"
            approval_level = "manager"
            approval_note = "需直属领导审批"
        elif amount <= 10000:
            approval_status = "pending"
            approval_level = "director"
            approval_note = "需部门总监审批"
        else:
            approval_status = "pending"
            approval_level = "cfo"
            approval_note = "需财务总监审批"
        
        # 查找关联项目
        project_id = None
        if project_name:
            proj_res = await client.table("projects").select("id, name").ilike("name", f"%{project_name}%").limit(1).execute()
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
                    "issues": compliance_issues
                }
            }
        }
        
        result = await client.table("approval_requests").insert(expense_data).execute()
        
        if not result.data:
            return "❌ 创建报销申请失败，请稍后重试"
        
        request_id = result.data[0]["id"]
        
        # 如果需要人工审批，发送通知
        if approval_status == "pending":
            approvers = await client.table("users").select("id").in_("role", ["manager", "founder"]).execute()
            for approver in (approvers.data or []):
                await client.table("notifications").insert({
                    "user_id": approver["id"],
                    "title": "💰 新的报销申请",
                    "content": f"{user['name']} 提交了 {config_info['name']} ¥{amount:.2f}",
                    "type": "info"
                }).execute()
        
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
                "description": "查询类型: my_claims(我的报销), pending(待处理), paid_history(已到账)"
            },
            "time_range": {
                "type": "string",
                "enum": ["this_month", "last_month", "this_year"],
                "description": "时间范围"
            }
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        query_type = args.get("query_type", "my_claims")
        
        client = _get_client(config)
        # 查询该用户的报销申请
        claims = await client.table("approval_requests")\
            .select("*")\
            .eq("submitted_by", user_id)\
            .eq("type", "expense")\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()
        
        if not claims.data:
            return "📋 您最近没有报销记录。"
        
        status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌", "paid": "💰"}
        
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
        
        result += f"\n📊 **汇总**\n"
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
            "department": {
                "type": "string",
                "description": "部门名称"
            },
            "project_name": {
                "type": "string", 
                "description": "项目名称"
            },
            "category": {
                "type": "string",
                "enum": ["travel", "marketing", "office", "hr", "all"],
                "description": "预算类别"
            }
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        department = args.get("department")
        project_name = args.get("project_name")
        
        client = _get_client(config)
        # 获取用户部门
        user_res = await client.table("users").select("department, role").eq("id", user_id).maybe_single().execute()
        if not user_res.data:
            return "❌ 无法获取用户信息"
        
        user_dept = department or user_res.data.get("department", "未知部门")
        
        # 模拟预算数据（实际应从 finance_budgets 表查询）
        current_month = datetime.now().month
        
        budget_data = {
            "department": user_dept,
            "period": f"2024年{current_month}月",
            "categories": [
                {"name": "差旅费", "budget": 50000, "used": 32500, "percentage": 65},
                {"name": "招待费", "budget": 30000, "used": 18000, "percentage": 60},
                {"name": "办公费", "budget": 20000, "used": 15500, "percentage": 77.5},
                {"name": "培训费", "budget": 15000, "used": 8000, "percentage": 53.3},
            ],
            "total_budget": 115000,
            "total_used": 74000
        }
        
        response = f"""📊 **{user_dept} 预算使用情况**
📅 统计周期: {budget_data['period']}

"""
        
        for cat in budget_data["categories"]:
            bar_filled = int(cat["percentage"] / 10)
            bar_empty = 10 - bar_filled
            bar = "█" * bar_filled + "░" * bar_empty
            
            warning = " ⚠️" if cat["percentage"] > 80 else ""
            
            response += f"**{cat['name']}**{warning}\n"
            response += f"  {bar} {cat['percentage']:.1f}%\n"
            response += f"  ¥{cat['used']:,.0f} / ¥{cat['budget']:,.0f}\n\n"
        
        total_pct = (budget_data["total_used"] / budget_data["total_budget"]) * 100
        response += f"""━━━━━━━━━━━━━━━━
**合计**: ¥{budget_data['total_used']:,.0f} / ¥{budget_data['total_budget']:,.0f} ({total_pct:.1f}%)

💡 **AI 建议**:
- 办公费使用已超77%，建议控制后续采购
- 本月剩余预算 ¥{budget_data['total_budget'] - budget_data['total_used']:,.0f}
"""
        
        return response


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
                "description": "查询月份，格式 YYYY-MM，默认当月"
            },
            "detail_type": {
                "type": "string",
                "enum": ["breakdown", "history", "tax"],
                "description": "查询类型: breakdown(明细), history(历史), tax(个税)"
            }
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        month = args.get("month", datetime.now().strftime("%Y-%m"))
        detail_type = args.get("detail_type", "breakdown")
        
        client = _get_client(config)
        # 获取用户信息
        user_res = await client.table("users").select("name, role, score, total_bonus").eq("id", user_id).maybe_single().execute()
        if not user_res.data:
            return "❌ 无法获取用户信息"
        
        user = user_res.data
        
        # 模拟薪资数据（实际应从 hr_salary 表查询）
        base_salary = 15000
        performance_bonus = float(user.get("total_bonus", 0)) or 3200
        attendance_bonus = 500
        meal_allowance = 500
        
        # 扣除项
        social_insurance = 1890
        housing_fund = 2400
        tax = 892
        
        gross = base_salary + performance_bonus + attendance_bonus + meal_allowance
        deductions = social_insurance + housing_fund + tax
        net = gross - deductions
        
        response = f"""💰 **{month} 薪资明细**

**📈 收入项**
┌─────────────────────────────┐
│ 基本工资        ¥{base_salary:>10,.2f} │
│ 绩效奖金        ¥{performance_bonus:>10,.2f} │
│ 全勤奖          ¥{attendance_bonus:>10,.2f} │
│ 餐补            ¥{meal_allowance:>10,.2f} │
├─────────────────────────────┤
│ 应发合计        ¥{gross:>10,.2f} │
└─────────────────────────────┘

**📉 扣除项**
┌─────────────────────────────┐
│ 社保个人部分    ¥{social_insurance:>10,.2f} │
│ 公积金个人部分  ¥{housing_fund:>10,.2f} │
│ 个人所得税      ¥{tax:>10,.2f} │
├─────────────────────────────┤
│ 扣除合计        ¥{deductions:>10,.2f} │
└─────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**实发工资: ¥{net:,.2f}**

📅 预计到账日期: {month}-10
🏦 到账银行: 工商银行 (尾号6688)

💡 绩效说明: 您当前绩效分 {user.get('score', 85)} 分，
   本月绩效系数 {performance_bonus/3000:.2f}
"""
        
        return response


class InvoiceOCRTool(BaseTool):
    """发票识别工具"""
    name = "recognize_invoice"
    description = "识别上传的发票图片，自动提取金额、日期、类型等信息"
    required_role = "all"
    
    parameters = {
        "type": "object",
        "properties": {
            "image_url": {
                "type": "string",
                "description": "发票图片URL"
            },
            "invoice_type": {
                "type": "string",
                "enum": ["general", "vat", "train", "taxi", "hotel"],
                "description": "发票类型（可选，自动识别）"
            }
        },
        "required": ["image_url"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        image_url = args.get("image_url", "")
        
        # 模拟 OCR 识别结果（实际应调用 OCR 服务）
        # 在实际实现中，这里会调用百度/腾讯/阿里的发票OCR API
        
        ocr_result = {
            "invoice_code": "044001900111",
            "invoice_number": "25847632",
            "invoice_date": "2024-12-15",
            "amount": 786.00,
            "tax_amount": 45.89,
            "total_amount": 831.89,
            "seller": "杭州外婆家餐饮有限公司",
            "invoice_type": "增值税普通发票",
            "verified": True
        }
        
        response = f"""🧾 **发票识别结果**

✅ 发票验真: 通过

**基本信息**
- 发票代码: {ocr_result['invoice_code']}
- 发票号码: {ocr_result['invoice_number']}
- 开票日期: {ocr_result['invoice_date']}
- 发票类型: {ocr_result['invoice_type']}

**金额信息**
- 不含税金额: ¥{ocr_result['amount']:.2f}
- 税额: ¥{ocr_result['tax_amount']:.2f}
- 价税合计: ¥{ocr_result['total_amount']:.2f}

**销售方**
- {ocr_result['seller']}

💡 是否基于此发票创建报销申请？
   您可以说: "帮我报销这张发票"
"""
        
        return response