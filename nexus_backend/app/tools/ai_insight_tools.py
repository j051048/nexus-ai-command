"""
AI智能分析工具集
提供智能报告、异常检测、预测分析等AI增强功能
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .base_tool import BaseTool
from ._shared import _get_client, _validate_uuid
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# AI智能分析工具
# ============================================================================


class SmartReportTool(BaseTool):
    """生成综合组织报告"""

    name = "smart_report"
    description = "生成组织综合报告，聚合员工、资产、工单、考勤数据。当用户说'生成报告'、'组织概况'、'综合报告'时调用。"
    domain = "analytics"
    examples = [
        {"input": {"report_type": "daily"}, "output_summary": "返回当日全组织的员工/资产/工单/考勤汇总"},
        {"input": {"report_type": "weekly", "department_id": "uuid"}, "output_summary": "返回指定部门最近7天的综合报告"},
        {"input": {"report_type": "monthly"}, "output_summary": "返回最近30天全组织综合报告"},
    ]
    related_tools = ["anomaly_detection", "generate_weekly_report"]
    gotchas = "报告基于实时查询而非缓存，数据量大时可能较慢。部门ID必须是有效的UUID格式。"

    parameters = {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "description": "报告类型",
                "enum": ["daily", "weekly", "monthly"],
            },
            "department_id": {
                "type": "string",
                "description": "部门ID（可选，不填则全组织）",
            },
        },
        "required": ["report_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        report_type = args.get("report_type", "daily")
        department_id = args.get("department_id")

        if department_id and (err := _validate_uuid(department_id, "department_id")):
            return f"❌ {err}"

        type_labels = {"daily": "日报", "weekly": "周报", "monthly": "月报"}
        type_label = type_labels.get(report_type, report_type)

        # 确定时间范围
        now = datetime.now(UTC)
        if report_type == "daily":
            start_date = now.date().isoformat()
        elif report_type == "weekly":
            start_date = (now - timedelta(days=7)).date().isoformat()
        else:
            start_date = (now - timedelta(days=30)).date().isoformat()
        end_date = now.date().isoformat()

        try:
            # 1. 员工统计
            emp_query = (
                client.table("employees")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .eq("status", "active")
            )
            if department_id:
                emp_query = emp_query.eq("department_id", department_id)
            emp_result = await emp_query.execute()
            emp_count = emp_result.count or 0

            # 2. 资产统计
            asset_query = client.table("assets").select("id, status", count="exact").eq("organization_id", org_id)
            if department_id:
                asset_query = asset_query.eq("department_id", department_id)
            asset_result = await asset_query.execute()
            asset_total = asset_result.count or 0
            asset_in_use = sum(1 for a in (asset_result.data or []) if a.get("status") == "in_use")

            # 3. 工单统计
            wo_query = (
                client.table("work_orders")
                .select("id, status", count="exact")
                .eq("organization_id", org_id)
                .gte("created_at", start_date)
            )
            if department_id:
                wo_query = wo_query.eq("department_id", department_id)
            wo_result = await wo_query.execute()
            wo_total = wo_result.count or 0
            wo_pending = sum(1 for w in (wo_result.data or []) if w.get("status") in ("pending", "open"))
            wo_done = sum(1 for w in (wo_result.data or []) if w.get("status") in ("done", "closed", "completed"))

            # 4. 考勤统计
            att_query = (
                client.table("attendance_records")
                .select("id, status", count="exact")
                .eq("organization_id", org_id)
                .gte("date", start_date)
                .lte("date", end_date)
            )
            if department_id:
                att_query = att_query.eq("department_id", department_id)
            att_result = await att_query.execute()
            att_total = att_result.count or 0
            att_late = sum(1 for a in (att_result.data or []) if a.get("status") == "late")

            dept_note = f"（部门: {department_id[:8]}...）" if department_id else "（全组织）"

            return (
                f"📊 智能{type_label} {dept_note}\n"
                f"📅 统计周期: {start_date} ~ {end_date}\n\n"
                f"👥 **人员概况**\n"
                f"  - 在职员工: {emp_count} 人\n\n"
                f"🏷️ **资产概况**\n"
                f"  - 资产总数: {asset_total}\n"
                f"  - 使用中: {asset_in_use}\n"
                f"  - 利用率: {(asset_in_use / asset_total * 100) if asset_total else 0:.1f}%\n\n"
                f"📋 **工单概况**\n"
                f"  - 期间工单: {wo_total}\n"
                f"  - 待处理: {wo_pending}\n"
                f"  - 已完成: {wo_done}\n"
                f"  - 完成率: {(wo_done / wo_total * 100) if wo_total else 0:.1f}%\n\n"
                f"⏰ **考勤概况**\n"
                f"  - 考勤记录: {att_total}\n"
                f"  - 迟到次数: {att_late}\n"
                f"  - 准时率: {((att_total - att_late) / att_total * 100) if att_total else 0:.1f}%"
            )

        except Exception as e:
            logger.error(f"生成智能报告失败: {e}")
            return safe_tool_error(e, "生成智能报告")


class AnomalyDetectionTool(BaseTool):
    """检测组织数据异常"""

    name = "anomaly_detection"
    description = "检测组织数据中的异常情况，覆盖考勤、报销、库存范围。当用户说'检测异常'、'有没有异常'、'风险预警'时调用。"
    domain = "analytics"
    examples = [
        {"input": {"scope": "all"}, "output_summary": "返回考勤、报销、库存三个维度的异常检测结果"},
        {"input": {"scope": "attendance"}, "output_summary": "仅返回考勤异常，如频繁迟到员工"},
        {"input": {"scope": "inventory"}, "output_summary": "返回低于安全库存的物资预警"},
    ]
    related_tools = ["smart_report", "predictive_maintenance"]
    gotchas = "异常检测基于最近7天数据。报销异常阈值为平均值的3倍，非固定金额。库存预警依赖物资表中的最低库存设置。"

    parameters = {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "description": "检测范围",
                "enum": ["attendance", "expense", "inventory", "all"],
            },
        },
        "required": ["scope"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        scope = args.get("scope", "all")
        alerts: list[str] = []
        now = datetime.now(UTC)
        week_ago = (now - timedelta(days=7)).date().isoformat()

        try:
            # 考勤异常检测
            if scope in ("attendance", "all"):
                att_result = await (
                    client.table("attendance_records")
                    .select("employee_id, status")
                    .eq("organization_id", org_id)
                    .gte("date", week_ago)
                    .eq("status", "late")
                    .execute()
                )
                late_records = att_result.data or []
                if late_records:
                    # 按员工统计迟到次数
                    late_counts: dict[str, int] = {}
                    for rec in late_records:
                        eid = rec.get("employee_id", "unknown")
                        late_counts[eid] = late_counts.get(eid, 0) + 1

                    frequent_late = {k: v for k, v in late_counts.items() if v >= 3}
                    if frequent_late:
                        alerts.append(f"⏰ **考勤异常**: {len(frequent_late)} 名员工本周迟到 3 次以上")
                    if len(late_records) > 10:
                        alerts.append(f"⏰ **考勤预警**: 本周共 {len(late_records)} 次迟到记录，建议关注")

            # 报销异常检测
            if scope in ("expense", "all"):
                exp_result = await (
                    client.table("expense_claims")
                    .select("id, amount, employee_id")
                    .eq("organization_id", org_id)
                    .gte("created_at", week_ago)
                    .execute()
                )
                expenses = exp_result.data or []
                if expenses:
                    amounts = [float(e.get("amount", 0)) for e in expenses if e.get("amount")]
                    if amounts:
                        avg_amount = sum(amounts) / len(amounts)
                        high_expenses = [a for a in amounts if a > avg_amount * 3]
                        if high_expenses:
                            alerts.append(
                                f"💰 **报销异常**: {len(high_expenses)} 笔报销金额超过平均值3倍 "
                                f"(平均: ¥{avg_amount:,.0f})"
                            )

            # 库存异常检测
            if scope in ("inventory", "all"):
                inv_result = await (
                    client.table("inventory")
                    .select("id, name, quantity, min_quantity")
                    .eq("organization_id", org_id)
                    .execute()
                )
                items = inv_result.data or []
                low_stock = [
                    item
                    for item in items
                    if item.get("quantity") is not None
                    and item.get("min_quantity") is not None
                    and item["quantity"] <= item["min_quantity"]
                ]
                if low_stock:
                    names = ", ".join(i.get("name", "未知")[:10] for i in low_stock[:5])
                    alerts.append(f"📦 **库存预警**: {len(low_stock)} 项物资低于安全库存 ({names})")

            if not alerts:
                scope_labels = {
                    "attendance": "考勤",
                    "expense": "报销",
                    "inventory": "库存",
                    "all": "全部",
                }
                return f"✅ {scope_labels.get(scope, scope)}范围未检测到明显异常。"

            return "🔍 **异常检测报告**\n\n" + "\n\n".join(alerts)

        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return safe_tool_error(e, "异常检测")


class PredictiveMaintenanceTool(BaseTool):
    """预测资产维护需求"""

    name = "predictive_maintenance"
    description = "预测资产维护需求，识别超期未维护的使用中资产。当用户说'维护预测'、'哪些设备需要维护'、'预防性维护'时调用。"
    domain = "asset"
    examples = [
        {"input": {}, "output_summary": "返回所有使用中资产的维护预测建议"},
        {"input": {"asset_type": "computer"}, "output_summary": "仅返回电脑类资产的维护建议"},
    ]
    related_tools = ["anomaly_detection", "process_asset_lifecycle"]
    gotchas = "维护判断逻辑：无转移记录且购置超180天，或距上次操作超90天。不支持自定义维护周期阈值。"

    parameters = {
        "type": "object",
        "properties": {
            "asset_type": {
                "type": "string",
                "description": "资产类型（可选，不填则检查全部）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        asset_type = args.get("asset_type")

        try:
            # 查询使用中的资产
            asset_query = (
                client.table("assets")
                .select("id, name, asset_code, asset_type, purchase_date, status")
                .eq("organization_id", org_id)
                .eq("status", "in_use")
            )
            if asset_type:
                asset_query = asset_query.eq("asset_type", asset_type)
            asset_result = await asset_query.execute()
            assets = asset_result.data or []

            if not assets:
                return "📋 当前没有使用中的资产需要维护检查。"

            now = datetime.now(UTC)
            suggestions: list[str] = []

            for asset in assets:
                asset_id = asset["id"]
                asset_name = asset.get("name", "未知")
                asset_code = asset.get("asset_code", "")

                # 查询该资产最近的转移/维护记录
                transfer_result = await (
                    client.table("asset_transfers")
                    .select("id, created_at, transfer_type")
                    .eq("asset_id", asset_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                transfers = transfer_result.data or []

                # 判断是否需要维护
                needs_maintenance = False
                reason = ""

                if not transfers:
                    # 从未有转移记录，检查购置日期
                    purchase_date = asset.get("purchase_date")
                    if purchase_date:
                        try:
                            pd = datetime.fromisoformat(purchase_date).replace(tzinfo=UTC)
                            days_since = (now - pd).days
                            if days_since > 180:
                                needs_maintenance = True
                                reason = f"购置 {days_since} 天，无维护记录"
                        except (ValueError, TypeError):
                            pass
                else:
                    last_transfer = transfers[0]
                    last_date_str = last_transfer.get("created_at", "")
                    if last_date_str:
                        try:
                            last_date = datetime.fromisoformat(last_date_str.replace("Z", "+00:00"))
                            days_since = (now - last_date).days
                            if days_since > 90:
                                needs_maintenance = True
                                reason = f"距上次操作 {days_since} 天"
                        except (ValueError, TypeError):
                            pass

                if needs_maintenance:
                    suggestions.append(f"- 🔧 **{asset_name}** [{asset_code}] — {reason}")

            if not suggestions:
                type_note = f"（类型: {asset_type}）" if asset_type else ""
                return f"✅ 所有使用中的资产{type_note}暂无维护需求。"

            return f"🔧 **维护预测报告**\n以下 {len(suggestions)} 项资产建议安排维护:\n\n" + "\n".join(suggestions)

        except Exception as e:
            logger.error(f"维护预测失败: {e}")
            return safe_tool_error(e, "维护预测")


class AutoDispatchTool(BaseTool):
    """智能工单派遣建议"""

    name = "auto_dispatch"
    description = "推荐工单最佳处理人，按员工当前工作量排序。当用户说'派遣工单'、'谁来处理这个工单'、'智能分配'时调用。"
    domain = "project"
    examples = [
        {"input": {"order_id": "uuid"}, "output_summary": "返回该工单所属部门员工按工作量排序的派遣建议"},
    ]
    related_tools = ["smart_report", "process_onboarding"]
    gotchas = "仅提供建议，不会自动修改工单的指派人。工单必须已存在，否则返回错误。"

    parameters = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "工单ID",
            },
        },
        "required": ["order_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        order_id = args.get("order_id", "").strip()
        if not order_id:
            return "❌ 工单ID不能为空"
        if err := _validate_uuid(order_id, "order_id"):
            return f"❌ {err}"

        try:
            # 获取工单详情
            wo_result = await client.table("work_orders").select("*").eq("id", order_id).maybe_single().execute()
            order = wo_result.data
            if not order:
                return f"❌ 未找到ID为 {order_id} 的工单。"

            department_id = order.get("department_id")
            order_title = order.get("title", "未知")

            # 查询该部门员工
            emp_query = (
                client.table("employees").select("id, name").eq("organization_id", org_id).eq("status", "active")
            )
            if department_id:
                emp_query = emp_query.eq("department_id", department_id)
            emp_result = await emp_query.execute()
            employees = emp_result.data or []

            if not employees:
                return "❌ 当前部门暂无可用员工进行分配。"

            # 统计每个员工的未完成工单数（批量查询替代 N+1）
            all_emp_ids = [emp["id"] for emp in employees]
            all_wo_result = await (
                client.table("work_orders")
                .select("assignee_id")
                .in_("assignee_id", all_emp_ids)
                .in_("status", ["pending", "open", "in_progress"])
                .execute()
            )
            wo_counts: dict[str, int] = {}
            for wo in (all_wo_result.data or []):
                aid = wo["assignee_id"]
                wo_counts[aid] = wo_counts.get(aid, 0) + 1

            workloads: list[dict] = []
            for emp in employees:
                emp_id = emp["id"]
                workloads.append(
                    {
                        "id": emp_id,
                        "name": emp.get("name", "未知"),
                        "open_count": wo_counts.get(emp_id, 0),
                    }
                )

            # 按工作量排序，推荐最空闲的
            workloads.sort(key=lambda x: x["open_count"])

            lines = [
                "🎯 **工单智能派遣建议**\n",
                f"工单: {order_title} (ID: {order_id[:8]}...)\n",
                "推荐处理人（按工作量从低到高）:\n",
            ]

            for i, wl in enumerate(workloads[:5], 1):
                tag = " ⭐ 推荐" if i == 1 else ""
                lines.append(f"{i}. **{wl['name']}** — 当前待处理工单: {wl['open_count']}{tag}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"智能派遣失败: {e}")
            return safe_tool_error(e, "智能派遣")


class MeetingSummaryTool(BaseTool):
    """生成会议纪要"""

    name = "meeting_summary"
    description = "解析会议笔记原文，生成结构化会议纪要。当用户说'整理会议纪要'、'会议总结'时调用。"
    domain = "oa_leave"
    examples = [
        {"input": {"content": "参会人员：张三、李四\n决定：启动新项目\n行动事项：张三负责方案"}, "output_summary": "返回结构化纪要，含参会人、决定、行动事项"},
        {"input": {"content": "今天讨论了预算问题，决定下周再议"}, "output_summary": "无明确分段时返回内容摘要并提示优化格式"},
    ]
    related_tools = ["generate_weekly_report"]
    gotchas = "依赖笔记中出现'参会人员'、'决定'、'行动事项'等关键词来分段，无关键词时按原文列出。不调用大语言模型，纯规则解析。"

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "会议笔记原文",
            },
        },
        "required": ["content"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        content = args.get("content", "").strip()
        if not content:
            return "❌ 会议笔记内容不能为空"

        try:
            # 简单文本解析，提取关键信息
            lines = content.split("\n")
            attendees: list[str] = []
            decisions: list[str] = []
            action_items: list[str] = []
            next_steps: list[str] = []
            other_lines: list[str] = []

            current_section = "other"
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                lower = stripped.lower()
                # 检测段落标题
                if any(kw in lower for kw in ["参会", "出席", "与会", "attendee"]):
                    current_section = "attendees"
                    continue
                elif any(kw in lower for kw in ["决定", "决议", "结论", "decision"]):
                    current_section = "decisions"
                    continue
                elif any(kw in lower for kw in ["行动", "待办", "任务", "action"]):
                    current_section = "actions"
                    continue
                elif any(kw in lower for kw in ["下一步", "后续", "next"]):
                    current_section = "next"
                    continue

                # 去除列表符号
                clean = stripped.lstrip("-•·*1234567890.） )")

                if current_section == "attendees":
                    attendees.append(clean)
                elif current_section == "decisions":
                    decisions.append(clean)
                elif current_section == "actions":
                    action_items.append(clean)
                elif current_section == "next":
                    next_steps.append(clean)
                else:
                    other_lines.append(clean)

            # 组装结构化纪要
            result_parts = ["📝 **会议纪要**\n"]

            if attendees:
                result_parts.append("👥 **参会人员**")
                result_parts.append("  " + "、".join(attendees))
                result_parts.append("")

            if decisions:
                result_parts.append("✅ **关键决定**")
                for d in decisions:
                    result_parts.append(f"  - {d}")
                result_parts.append("")

            if action_items:
                result_parts.append("📋 **行动事项**")
                for a in action_items:
                    result_parts.append(f"  - [ ] {a}")
                result_parts.append("")

            if next_steps:
                result_parts.append("➡️ **后续计划**")
                for n in next_steps:
                    result_parts.append(f"  - {n}")
                result_parts.append("")

            if other_lines and not (attendees or decisions or action_items or next_steps):
                # 无结构化内容时，返回原文摘要
                result_parts.append("📄 **会议内容**")
                for line in other_lines[:20]:
                    result_parts.append(f"  - {line}")
                result_parts.append("")
                result_parts.append(
                    "💡 提示: 建议在笔记中使用「参会人员」「决定」「行动事项」「下一步」等标题以获得更好的结构化效果。"
                )

            return "\n".join(result_parts)

        except Exception as e:
            logger.error(f"生成会议纪要失败: {e}")
            return safe_tool_error(e, "生成会议纪要")


class OnboardingAssistantTool(BaseTool):
    """生成新员工入职清单"""

    name = "onboarding_assistant"
    description = "生成新员工入职清单，含账号配置、设备分配、培训计划等。当用户说'入职清单'、'新员工入职'、'入职准备'时调用。"
    domain = "hr"
    examples = [
        {"input": {"employee_id": "uuid"}, "output_summary": "返回该员工的完整入职清单，含可分配的闲置设备"},
        {"input": {"employee_id": "uuid", "department_id": "uuid"}, "output_summary": "返回入职清单，部门信息使用指定部门而非员工默认部门"},
    ]
    related_tools = ["process_onboarding", "auto_dispatch"]
    gotchas = "仅生成清单文本，不执行实际操作。如需一键执行入职流程请使用 process_onboarding 工具。"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "新员工ID",
            },
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
        },
        "required": ["employee_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        employee_id = args.get("employee_id", "").strip()
        department_id = args.get("department_id")

        if not employee_id:
            return "❌ 员工ID不能为空"
        if err := _validate_uuid(employee_id, "employee_id"):
            return f"❌ {err}"
        if department_id and (err := _validate_uuid(department_id, "department_id")):
            return f"❌ {err}"

        try:
            # 获取员工信息
            emp_result = await client.table("employees").select("*").eq("id", employee_id).maybe_single().execute()
            employee = emp_result.data
            if not employee:
                return f"❌ 未找到ID为 {employee_id} 的员工。"

            emp_name = employee.get("name", "未知")
            dept_id = department_id or employee.get("department_id")

            # 获取部门信息
            dept_name = "未分配"
            if dept_id:
                dept_result = await (
                    client.table("departments").select("name").eq("id", dept_id).maybe_single().execute()
                )
                if dept_result.data:
                    dept_name = dept_result.data.get("name", "未知")

            # 查询可用设备（闲置资产）
            idle_assets = await (
                client.table("assets")
                .select("id, name, asset_type, asset_code")
                .eq("organization_id", org_id)
                .eq("status", "idle")
                .limit(10)
                .execute()
            )
            available_assets = idle_assets.data or []

            # 组装入职清单
            lines = [
                "📋 **新员工入职清单**\n",
                f"👤 员工: {emp_name}",
                f"🏢 部门: {dept_name}\n",
                "---\n",
                "**一、账号与权限配置**",
                "  - [ ] 创建系统登录账号",
                "  - [ ] 配置角色权限",
                "  - [ ] 分配企业邮箱",
                "  - [ ] 加入部门沟通群组",
                "",
                "**二、办公设备分配**",
            ]

            if available_assets:
                # 按类型分组推荐
                type_groups: dict[str, list] = {}
                for asset in available_assets:
                    atype = asset.get("asset_type", "other")
                    if atype not in type_groups:
                        type_groups[atype] = []
                    type_groups[atype].append(asset)

                for atype, assets_list in type_groups.items():
                    first = assets_list[0]
                    lines.append(
                        f"  - [ ] {atype}: 可分配 **{first.get('name')}** "
                        f"[{first.get('asset_code')}] (共 {len(assets_list)} 台闲置)"
                    )
            else:
                lines.append("  - [ ] 暂无闲置设备，需申请采购")

            lines.extend(
                [
                    "",
                    "**三、培训计划**",
                    "  - [ ] 公司文化与制度培训（第1天）",
                    "  - [ ] 系统操作培训（第1-2天）",
                    "  - [ ] 部门业务培训（第1周）",
                    "  - [ ] 安全合规培训（第1周）",
                    "",
                    "**四、入职介绍**",
                    f"  - [ ] 部门负责人介绍会（{dept_name}）",
                    "  - [ ] 团队成员见面会",
                    "  - [ ] 办公环境导览",
                    "",
                    "**五、行政事项**",
                    "  - [ ] 录入考勤系统",
                    "  - [ ] 办理工牌/门禁卡",
                    "  - [ ] 签署劳动合同及保密协议",
                    "  - [ ] 社保公积金登记",
                ]
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"生成入职清单失败: {e}")
            return safe_tool_error(e, "生成入职清单")
