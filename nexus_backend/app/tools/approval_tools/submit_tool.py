import contextlib
import logging
from datetime import datetime
from typing import Any

import app.tools.approval_tools as _pkg

from ..base_tool import BaseTool
from ._constants import AI_ASSISTANT_ID, _LEVEL_NAMES
from ._helpers import _notify_next_approver

logger = logging.getLogger(__name__)


class SubmitApprovalOnBehalfTool(BaseTool):
    """AI助手代员工提交审批申请 - 自动使用当前登录用户的身份"""

    name = "submit_approval_on_behalf"
    description = "代表当前用户提交审批申请（出差、请假、报销、采购）。当用户说'提交审批'、'发起申请'时调用。注意：明确说'请假'请用 create_leave_request，明确说'报销'请用 create_expense_claim。"
    required_role = "ai_assistant"  # 允许通过 AI 调用
    examples = [
        {
            "input": {
                "type": "travel",
                "description": "出差北京拜访客户",
                "amount": 3000,
                "start_date": "2026-03-25",
                "end_date": "2026-03-27",
            },
            "output_summary": "已提交出差审批，等待部门经理审批",
        },
        {
            "input": {
                "type": "purchase",
                "description": "采购10台显示器",
                "amount": 15000,
            },
            "output_summary": "已提交采购审批，审批链匹配为多级审批",
        },
    ]
    related_tools = [
        "create_leave_request",
        "create_expense_claim",
        "get_pending_approvals",
    ]
    gotchas = "用户明确说请假或报销时应优先使用专用工具而非本工具。老板角色无法通过此工具提交审批。同类型同金额的待审批申请会被防重复拦截。"

    parameters = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["travel", "leave", "expense", "purchase"],
                "description": "审批类型：travel=出差, leave=请假, expense=报销, purchase=采购",
            },
            "amount": {
                "type": "number",
                "minimum": 0,
                "maximum": 99999999,
                "description": "金额（如适用，默认0）",
            },
            "description": {"type": "string", "description": "详细说明申请事由"},
            "start_date": {"type": "string", "description": "开始日期（如适用）"},
            "end_date": {"type": "string", "description": "结束日期（如适用）"},
        },
        "required": ["type", "description"],
    }
    domain = "approval"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        from datetime import datetime

        client = _pkg._get_client(config)
        # 使用当前登录用户的 ID（从 JWT 解析出来的）
        employee_id = user_id
        approval_type = args.get("type")
        amount = args.get("amount", 0)
        description = args.get("description")
        start_date = args.get("start_date", "")
        end_date = args.get("end_date", "")

        logger.info(f"[AI审批] 当前用户ID: {user_id}, 申请类型: {approval_type}")

        # ── 输入校验 ──
        # 金额校验：涉及金额的审批类型必须 > 0
        _amount_types = {
            "reimbursement",
            "expense",
            "purchase",
            "budget",
            "报销",
            "采购",
            "预算",
        }
        if approval_type in _amount_types or amount:
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return self.format_result(data=None, summary="金额格式错误，请提供有效的数字金额")
            if amount <= 0:
                return self.format_result(data=None, summary="审批金额必须大于0")

        # 日期校验
        if start_date or end_date:
            now = datetime.now()
            try:
                if start_date:
                    s = datetime.strptime(start_date, "%Y-%m-%d")
                    if s.year < now.year - 1 or s.year > now.year + 1:
                        return self.format_result(data=None, summary=f"开始日期 {start_date} 年份异常，当前日期是 {now.strftime('%Y-%m-%d')}")
                if end_date:
                    e = datetime.strptime(end_date, "%Y-%m-%d")
                    if e.year < now.year - 1 or e.year > now.year + 1:
                        return self.format_result(data=None, summary=f"结束日期 {end_date} 年份异常，当前日期是 {now.strftime('%Y-%m-%d')}")
                if start_date and end_date and e < s:
                    return self.format_result(data=None, summary="结束日期不能早于开始日期")
            except ValueError:
                return self.format_result(data=None, summary="日期格式错误，请使用 YYYY-MM-DD 格式")

        # 防重复提交：检查同用户是否有近期完全相同的待审批申请
        try:
            dup_query = (
                client.table("approval_requests")
                .select("id")
                .eq("submitted_by", employee_id)
                .eq("type", approval_type)
                .eq("status", "pending")
            )
            if amount:
                dup_query = dup_query.eq("amount", amount)
            dup_res = await dup_query.limit(1).execute()
            if dup_res.data:
                return self.format_result(data=None, summary=f"您已有一条相同类型（{approval_type}）的待审批申请，请勿重复提交")
        except Exception:
            pass  # 去重检查失败不应阻塞主流程

        # 验证员工存在
        employee_check = (
            await client.table("users")
            .select("id, name, role, organization_id")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not employee_check.data:
            return self.format_result(data=None, summary=f"找不到您的用户信息（ID: {employee_id}）")

        actual_employee = employee_check.data
        employee_name = actual_employee.get("name", "未知")
        employee_org_id = actual_employee.get("organization_id")

        if actual_employee.get("role") == "founder":
            return self.format_result(data=None, summary="老板无需通过AI提交审批申请，您可以直接审批")

        # 构建详情
        full_details = description
        if start_date or end_date:
            full_details += f"\n日期：{start_date} 至 {end_date}"

        # ── 审批链匹配：根据类型和金额决定走自动批准还是多级链路 ──
        from app.services.approval_chain import approval_chain_service

        chain_result = await approval_chain_service.match_and_bind_chain(
            org_id=employee_org_id or "",
            approval_type=approval_type,
            amount=float(amount) if amount else 0,
            db=client,
        )

        auto_approve = chain_result.get("auto_approve", False)
        chain_id = chain_result.get("chain_id")
        starting_step = chain_result.get("starting_step", 0)
        approval_level = chain_result.get("approval_level", "manager")
        timeout_at = chain_result.get("timeout_at")
        chain_name = chain_result.get("chain_name", "默认审批链")

        # 插入审批记录 — 携带审批链信息
        try:
            insert_data = {
                "submitted_by": employee_id,
                "on_behalf_of": employee_id,
                "submitted_via": "ai_assistant",
                "type": approval_type,
                "amount": amount,
                "description": full_details,
                "status": "approved" if auto_approve else "pending",
                "ai_reason": f"由AI助手豆豆代{actual_employee.get('name', employee_name)}提交",
                "current_step": starting_step,
                "approval_level": approval_level,
                "approval_history": (
                    [
                        {
                            "step": 0,
                            "decision": "auto_approved",
                            "approver_id": "system",
                            "timestamp": datetime.now().isoformat(),
                            "comment": f"金额 ¥{amount} 在自动审批限额内",
                        }
                    ]
                    if auto_approve
                    else []
                ),
            }
            if chain_id:
                insert_data["chain_id"] = chain_id
            if timeout_at:
                insert_data["timeout_at"] = timeout_at
            if employee_org_id:
                insert_data["organization_id"] = employee_org_id
            logger.debug(f"[AI审批] 准备插入数据: {insert_data}")

            result = (
                await client.table("approval_requests").insert(insert_data).execute()
            )
            logger.debug("[AI审批] 插入结果成功")
        except Exception as e:
            logger.exception(f"[AI审批] 插入失败: {e}")
            return self.format_result(data=None, summary=f"提交失败：数据库错误 - {str(e)}")

        if result.data:
            req_id = result.data[0].get("id")
            # 记录审计日志
            await (
                client.table("audit_logs")
                .insert(
                    {
                        "action": "approval_submitted_via_ai",
                        "actor_user_id": AI_ASSISTANT_ID,
                        "target_id": req_id,
                        "target_table": "approval_requests",
                        "details_json": {
                            "employee_id": employee_id,
                            "employee_name": actual_employee.get("name"),
                            "type": approval_type,
                            "amount": amount,
                            "chain_name": chain_name,
                            "auto_approve": auto_approve,
                        },
                    }
                )
                .execute()
            )

            if auto_approve:
                # 小额自动批准 — 通知提交人
                with contextlib.suppress(Exception):
                    await (
                        client.table("notifications")
                        .insert(
                            {
                                "user_id": employee_id,
                                "title": "✅ 审批已自动通过",
                                "content": f"您的{approval_type}申请（¥{amount}）金额较小，已由系统自动批准。",
                                "type": "success",
                                "action_url": "/approval",
                            }
                        )
                        .execute()
                    )
                return self.format_result(
                    data={"request_id": req_id, "type": approval_type, "amount": amount, "auto_approved": True},
                    summary=f"已为您（{employee_name}）提交{approval_type}申请（单号：{req_id[:8]}...），金额 ¥{amount} 在自动审批限额内，系统已自动批准",
                    actions=[
                        {"label": "查看待审批", "tool": "get_pending_approvals", "args": {}},
                        {"label": "创建请假", "tool": "create_leave_request", "args": {}},
                    ],
                )
            else:
                # 大额需多级审批 — 通知第一个节点审批人
                await _notify_next_approver(
                    client=client,
                    approval_level=approval_level,
                    requester_id=employee_id,
                    requester_name=employee_name,
                    approval_type=approval_type,
                    amount=amount,
                    req_id=req_id,
                    org_id=employee_org_id,
                )
                level_names = {
                    "manager": "部门经理",
                    "director": "总监",
                    "cfo": "财务总监",
                    "ceo": "总经理/CEO",
                    "board": "董事会",
                    "founder": "老板",
                }
                level_label = level_names.get(approval_level, approval_level)
                return self.format_result(
                    data={"request_id": req_id, "type": approval_type, "amount": amount, "chain_name": chain_name, "approval_level": approval_level},
                    summary=f"已为您（{employee_name}）提交{approval_type}申请（单号：{req_id[:8]}...），等待{level_label}审批",
                    actions=[
                        {"label": "查看待审批", "tool": "get_pending_approvals", "args": {}},
                        {"label": "创建报销", "tool": "create_expense_claim", "args": {}},
                    ],
                )

        return self.format_result(data=None, summary="提交失败，请稍后重试")
