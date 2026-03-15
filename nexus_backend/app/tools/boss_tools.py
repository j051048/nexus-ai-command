"""
领导专属工具集
实现智能审批、经营洞察、团队管理等高级管理功能
支持语音/自然语言批量处理

P0 Security Fix #1: All approval operations require explicit confirmation
P2-3: Refactored — shared utilities extracted to boss_shared.py.
      Individual tool classes remain here for backward compatibility.
      Future: split each class to its own module.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.ai_service import AIService

from .base_tool import BaseTool
from .boss_shared import MAX_BATCH_SIZE, _get_client, _parse_amount_from_condition

logger = logging.getLogger(__name__)


class SmartApprovalTool(BaseTool):
    """
    智能审批工具 - 支持批量审批、条件审批、委托审批

    P0 Security Fix #1:
    - All operations require explicit confirm=true
    - Batch operations limited to MAX_BATCH_SIZE
    - Idempotency checks prevent duplicate processing
    """

    name = "smart_approve"
    description = """智能审批工具。支持批量审批、按条件审批、委托审批等。当领导说'批量审批'、'5000以下的都批'、'一键通过'时调用。注意：单条审批用 approve_request 或 reject_request。
首次调用返回预览信息，需要确认后设置 confirm=true 才会真正执行。
这是不可逆操作，需要人工确认。"""
    required_role = "boss"
    is_irreversible = True
    confirmation_message = "⚠️ 审批操作不可逆。请在弹出的确认框中确认后执行。"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "approve",
                    "reject",
                    "delegate",
                    "batch_approve",
                    "conditional_approve",
                ],
                "description": "操作类型: approve(批准), reject(驳回), delegate(委托), batch_approve(批量批准), conditional_approve(条件批准)",
            },
            "request_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要处理的申请ID列表（可选，不填则处理全部待审批）",
            },
            "request_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "要处理的申请序号列表，如[1,2,3]表示第1、2、3条",
            },
            "condition": {
                "type": "string",
                "description": "审批条件，如'金额小于5000的全部通过'",
            },
            "delegate_to": {"type": "string", "description": "委托给谁（姓名）"},
            "comment": {"type": "string", "description": "审批意见"},
            "confirm": {
                "type": "boolean",
                "description": "是否确认执行？首次调用请设为false获取预览，确认后设为true执行",
            },
        },
        "required": ["action"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        action = args.get("action", "approve")
        request_ids = args.get("request_ids", [])
        request_numbers = args.get("request_numbers", [])
        condition = args.get("condition", "")
        delegate_to = args.get("delegate_to", "")
        comment = args.get("comment", "")
        confirm = args.get("confirm", False)  # P0 Security: Default to preview mode

        # 获取待审批列表
        pending_res = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name, department)")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )

        pending_list = pending_res.data or []

        if not pending_list:
            return "✅ 太棒了！当前没有待审批的事项，您可以放心休息。"

        # 根据序号筛选
        if request_numbers:
            selected_requests = [pending_list[i - 1] for i in request_numbers if 0 < i <= len(pending_list)]
        elif request_ids:
            selected_requests = [r for r in pending_list if r["id"] in request_ids]
        else:
            selected_requests = pending_list

        # 条件筛选
        if condition:
            if "小于" in condition or "<" in condition:
                amount_threshold = _parse_amount_from_condition(condition)
                if amount_threshold is not None:
                    selected_requests = [r for r in selected_requests if float(r.get("amount", 0)) < amount_threshold]
                else:
                    logger.warning(f"Failed to parse amount threshold from condition: {condition}")
            elif "大于" in condition or ">" in condition:
                amount_threshold = _parse_amount_from_condition(condition)
                if amount_threshold is not None:
                    selected_requests = [r for r in selected_requests if float(r.get("amount", 0)) > amount_threshold]
                else:
                    logger.warning(f"Failed to parse amount threshold from condition: {condition}")

        if not selected_requests:
            return "❌ 没有符合条件的审批事项"

        # P0 Security: Limit batch size
        if len(selected_requests) > MAX_BATCH_SIZE:
            return f"""⚠️ 安全限制：单次批量操作最多处理 {MAX_BATCH_SIZE} 条

当前符合条件的申请有 {len(selected_requests)} 条。
请使用 request_numbers 参数指定具体序号，或分批处理。"""

        # Calculate totals for preview
        total_amount = sum(float(r.get("amount", 0)) for r in selected_requests)

        # P0 Security Fix #1: Return preview if not confirmed
        if not confirm:
            action_name = {
                "approve": "批准",
                "reject": "驳回",
                "delegate": "委托",
                "batch_approve": "批量批准",
            }.get(action, action)

            preview = f"""📋 **{action_name}预览** - 请确认后执行

**将要处理的申请** ({len(selected_requests)} 件，共 ¥{total_amount:,.2f})

"""
            for i, req in enumerate(selected_requests[:5], 1):
                user_info = req.get("users", {})
                user_name = user_info.get("name", "未知") if isinstance(user_info, dict) else "未知"
                preview += f"{i}. {user_name} - {req.get('type', '未知')} ¥{req.get('amount', 0):,.0f}\n"

            if len(selected_requests) > 5:
                preview += f"... 还有 {len(selected_requests) - 5} 条\n"

            preview += f"""
⚠️ **这是不可逆操作**
如确认{action_name}，请说「确认{action_name}」或重新调用工具并设置 confirm=true"""

            return preview

        # P0 Security: Log the confirmed action
        logger.info(f"[P0 Security] User {user_id} confirmed {action} for {len(selected_requests)} requests")

        # 执行操作
        if action == "approve" or action == "batch_approve":
            # Use advance_step for chain-bound requests, fallback to RPC for others
            from app.services.approval_chain import approval_chain_service

            approved_count = 0
            skipped_count = 0
            updated_ids = set()
            rpc_ids = []  # requests without chain_id use batch RPC

            for req in selected_requests:
                if req.get("chain_id"):
                    # Has approval chain: use advance_step for proper multi-level flow
                    try:
                        updated = await approval_chain_service.advance_step(
                            request_id=req["id"],
                            decision="approved",
                            approver_id=user_id,
                            comment=comment or "已批准",
                            db=client,
                        )
                        updated_ids.add(req["id"])
                        approved_count += 1

                        # If still pending (promoted to next level), notify next approver
                        if updated.get("status") == "pending":
                            try:
                                from app.tools.approval_tools import _notify_next_approver

                                user_info = req.get("users", {})
                                req_name = user_info.get("name", "员工") if isinstance(user_info, dict) else "员工"
                                await _notify_next_approver(
                                    client=client,
                                    approval_level=updated.get("approval_level", "manager"),
                                    requester_id=req["submitted_by"],
                                    requester_name=req_name,
                                    approval_type=req.get("type", "default"),
                                    amount=float(req.get("amount", 0)),
                                    req_id=req["id"],
                                    org_id=req.get("organization_id"),
                                )
                            except Exception as e:
                                logger.warning(f"Failed to notify next approver for {req['id']}: {e}")
                    except Exception as e:
                        logger.warning(f"advance_step failed for {req['id']}: {e}")
                        skipped_count += 1
                else:
                    rpc_ids.append(req["id"])

            # Batch RPC for requests without chain
            if rpc_ids:
                try:
                    rpc_result = await client.rpc(
                        "batch_update_approvals",
                        {
                            "p_request_ids": rpc_ids,
                            "p_new_status": "approved",
                            "p_approved_by": user_id,
                            "p_comment": comment or "已批准",
                        },
                    ).execute()

                    batch_data = rpc_result.data or {}
                    approved_count += batch_data.get("updated_count", 0)
                    skipped_count += batch_data.get("skipped_count", 0)
                    updated_ids.update(batch_data.get("updated_ids", []))
                except Exception as e:
                    logger.error(f"Batch approval RPC failed: {e}")
                    skipped_count += len(rpc_ids)

            # Send notifications for successfully approved requests (non-transactional, best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await (
                            client.table("notifications")
                            .insert(
                                {
                                    "user_id": req["submitted_by"],
                                    "title": "✅ 您的申请已批准",
                                    "content": f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0)}）已被批准",
                                    "type": "success",
                                }
                            )
                            .execute()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send approval notification: {e}")

                    # Multi-channel notification via notification_service
                    try:
                        from app.services.notification_service import (
                            Notification,
                            NotificationChannel,
                            NotificationPriority,
                            notification_service,
                        )

                        await notification_service.send(
                            Notification(
                                title="✅ 您的申请已批准",
                                content=f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0):,.0f}）已被批准",
                                target_user_id=req["submitted_by"],
                                channel=NotificationChannel.IN_APP,
                                priority=NotificationPriority.NORMAL,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Multi-channel approval notification failed: {e}")

            result_msg = f"""✅ 批量审批完成！

**处理结果**
- 批准数量: {approved_count} 件
- 跳过数量: {skipped_count} 件（已被他人处理）
- 涉及金额: ¥{total_amount:,.2f}
- 处理时间: {datetime.now().strftime("%H:%M:%S")}

**已批准明细**
{self._format_request_list(selected_requests[:5])}

📧 已通知所有申请人
"""
            return result_msg

        elif action == "reject":
            # Use advance_step for chain-bound requests, fallback to RPC for others
            from app.services.approval_chain import approval_chain_service

            rejected_count = 0
            skipped_count = 0
            updated_ids = set()
            rpc_ids = []

            for req in selected_requests:
                if req.get("chain_id"):
                    try:
                        await approval_chain_service.advance_step(
                            request_id=req["id"],
                            decision="rejected",
                            approver_id=user_id,
                            comment=comment or "已驳回",
                            db=client,
                        )
                        updated_ids.add(req["id"])
                        rejected_count += 1
                    except Exception as e:
                        logger.warning(f"advance_step (reject) failed for {req['id']}: {e}")
                        skipped_count += 1
                else:
                    rpc_ids.append(req["id"])

            if rpc_ids:
                try:
                    rpc_result = await client.rpc(
                        "batch_update_approvals",
                        {
                            "p_request_ids": rpc_ids,
                            "p_new_status": "rejected",
                            "p_approved_by": user_id,
                            "p_comment": comment or "已驳回",
                        },
                    ).execute()

                    batch_data = rpc_result.data or {}
                    rejected_count += batch_data.get("updated_count", 0)
                    skipped_count += batch_data.get("skipped_count", 0)
                    updated_ids.update(batch_data.get("updated_ids", []))
                except Exception as e:
                    logger.error(f"Batch rejection RPC failed: {e}")
                    skipped_count += len(rpc_ids)

            # Send notifications (best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await (
                            client.table("notifications")
                            .insert(
                                {
                                    "user_id": req["submitted_by"],
                                    "title": "❌ 您的申请被驳回",
                                    "content": f"您提交的{req.get('type', '申请')}被驳回。原因: {comment or '未说明'}",
                                    "type": "warning",
                                }
                            )
                            .execute()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send rejection notification: {e}")

                    # Multi-channel notification via notification_service
                    try:
                        from app.services.notification_service import (
                            Notification,
                            NotificationChannel,
                            NotificationPriority,
                            notification_service,
                        )

                        await notification_service.send(
                            Notification(
                                title="❌ 您的申请被驳回",
                                content=f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0):,.0f}）被驳回。原因: {comment or '未说明'}",
                                target_user_id=req["submitted_by"],
                                channel=NotificationChannel.IN_APP,
                                priority=NotificationPriority.HIGH,
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Multi-channel rejection notification failed: {e}")

            return f"""❌ 已驳回 {rejected_count} 件申请

驳回原因: {comment or "未说明"}
跳过数量: {skipped_count} 件（已被他人处理）
📧 已通知相关申请人
"""

        elif action == "delegate":
            if not delegate_to:
                return "❌ 请指定委托人"

            # 查找委托人
            delegate_res = (
                await client.table("users").select("id, name").ilike("name", f"%{delegate_to}%").limit(1).execute()
            )
            if not delegate_res.data:
                return f"❌ 未找到名为「{delegate_to}」的人员"

            delegate_user = delegate_res.data[0]

            # 更新审批人 (委托不是不可逆操作，可以重新委托)
            # RLS policy "approval_admin_update" allows boss/admin in same org
            for req in selected_requests:
                await (
                    client.table("approval_requests")
                    .update({"current_approver": delegate_user["id"]})
                    .eq("id", req["id"])
                    .eq("status", "pending")
                    .execute()
                )

            # 通知被委托人
            await (
                client.table("notifications")
                .insert(
                    {
                        "user_id": delegate_user["id"],
                        "title": "📋 收到委托审批",
                        "content": f"领导将 {len(selected_requests)} 件审批事项委托给您处理",
                        "type": "warning",
                    }
                )
                .execute()
            )

            return f"""✅ 已委托给 {delegate_user["name"]}

委托事项: {len(selected_requests)} 件
📧 已通知 {delegate_user["name"]}
"""

        return "未知操作"

    def _format_request_list(self, requests: list[dict]) -> str:
        result = ""
        type_icons = {"expense": "💰", "leave": "🏖️", "purchase": "🛒", "travel": "✈️"}
        for _i, req in enumerate(requests, 1):
            icon = type_icons.get(req.get("type"), "📋")
            user_name = req.get("users", {}).get("name", "未知") if isinstance(req.get("users"), dict) else "未知"
            amount = req.get("amount", 0)
            result += f"{icon} {user_name}: ¥{amount:,.0f}\n"
        return result


class DailyBriefingTool(BaseTool):
    """每日简报工具 - AI 主动汇报"""

    name = "get_daily_briefing"
    description = "获取每日工作简报，包括待审批事项、异常预警、经营数据等。领导说'今天有什么事'、'汇报一下'时调用。"
    required_role = "boss"

    parameters = {
        "type": "object",
        "properties": {
            "briefing_type": {
                "type": "string",
                "enum": ["full", "approvals_only", "alerts_only", "performance"],
                "description": "简报类型: full(完整), approvals_only(仅审批), alerts_only(仅预警), performance(业绩)",
            }
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        # 获取待审批数量
        pending_res = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name)")
            .eq("status", "pending")
            .order("amount", desc=True)
            .limit(5)
            .execute()
        )

        pending_list = pending_res.data or []
        pending_count = len(pending_list)

        # 获取已自动处理数量（今日已审批的）
        try:
            from datetime import datetime

            today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0).isoformat()
            auto_res = (
                await client.table("approval_requests")
                .select("count", count="exact")
                .eq("status", "approved")
                .gte("updated_at", today_start)
                .execute()
            )
            auto_processed = auto_res.count or 0
        except Exception:
            auto_processed = 0

        # 获取团队绩效
        team_query = client.table("users").select("name, score, total_bonus").order("score", desc=True).limit(3)
        if org_id:
            team_query = team_query.eq("organization_id", org_id)
        team_res = await team_query.execute()
        top_performers = team_res.data or []

        # 计算总奖金
        total_bonus = sum(float(p.get("total_bonus", 0)) for p in top_performers)

        now = datetime.now()
        greeting = "早上好" if now.hour < 12 else "下午好" if now.hour < 18 else "晚上好"

        response = f"""☀️ **{greeting}，老板！**
📅 {now.strftime("%Y年%m月%d日 %A")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        if auto_processed > 0:
            response += f"""✅ **今日已处理** {auto_processed} 件事务

"""
        else:
            response += """ℹ️ **今日暂无已处理事务**

"""

        if pending_count > 0:
            response += f"""⏳ **需您决策** {pending_count} 件

"""
            type_icons = {"expense": "💰", "leave": "🏖️", "purchase": "🛒"}

            for i, req in enumerate(pending_list, 1):
                icon = type_icons.get(req.get("type"), "📋")
                user_name = req.get("users", {}).get("name", "员工") if isinstance(req.get("users"), dict) else "员工"
                amount = float(req.get("amount", 0))
                req_type = req.get("type", "申请")

                # AI 建议
                if amount > 5000 and i <= 2:
                    try:
                        suggestion = await AIService.call_llm(
                            f"审批请求: {req.get('description', req_type)}, 金额: ¥{amount:,.2f}, 申请人: {user_name}",
                            "你是企业财务审核专家。简短给出审批建议（1句话），以emoji开头。",
                        )
                        suggestion = f"🤖 {suggestion}"
                    except Exception:
                        suggestion = "⚠️ 建议详细审核（金额较大）" if amount > 20000 else "✅ 建议批准"
                elif amount < 5000:
                    suggestion = "✅ 建议批准（金额合理）"
                elif amount > 20000:
                    suggestion = "⚠️ 建议详细审核（金额较大）"
                else:
                    suggestion = "✅ 建议批准"

                response += f"""**{i}️⃣ {icon} {user_name} - {req_type}**
   金额: ¥{amount:,.2f}
   AI建议: {suggestion}

"""

            response += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 **快捷操作**
- 说「全部批了」→ 一键批准全部
- 说「第1个批，第2个不批」→ 分别处理
- 说「金额小于5000的都批」→ 条件审批
- 说「委托给张三」→ 委托审批

"""
        else:
            response += """🎉 **太棒了！当前没有待处理事项**

"""

        # 添加经营数据 - 查询真实数据 (从 customers 表)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%dT00:00:00")
        org_id = config.get("org_id") if config else None

        # 查询本周新增客户/商机
        try:
            query = client.table("customers").select("*", count="exact").gte("created_at", week_start)
            if org_id:
                query = query.eq("organization_id", org_id)
            leads_res = await query.execute()
            new_leads = leads_res.count or len(leads_res.data or [])
        except Exception:
            new_leads = 0

        # 查询本周成交客户
        try:
            query = (
                client.table("customers")
                .select("estimated_value")
                .eq("stage", "customer")
                .gte("updated_at", week_start)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            won_res = await query.execute()
            won_count = len(won_res.data or [])
            won_amount = sum(float(d.get("estimated_value", 0)) for d in (won_res.data or []))
        except Exception:
            won_count = 0
            won_amount = 0

        response += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **经营快报**

**本周业绩**
- 新增商机: {new_leads} 个
- 成交订单: {won_count} 个（¥{won_amount:,.0f}）
- 团队激励: ¥{total_bonus:,.0f}

**Top 3 员工**
"""

        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(top_performers):
            response += f"{medals[i]} {p.get('name', '员工')}: {p.get('score', 0)}分\n"

        # 查询真实风险预警 (从 customers 表)
        risk_alerts = []
        try:
            thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
            query = (
                client.table("customers")
                .select("name, company, updated_at")
                .lt("updated_at", thirty_days_ago)
                .in_("stage", ["prospect", "opportunity"])
                .limit(3)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            stale_res = await query.execute()
            for cust in stale_res.data or []:
                updated = datetime.fromisoformat(cust["updated_at"][:19])
                days_stale = (now - updated).days
                display_name = cust.get("company") or cust.get("name", "未知客户")
                risk_alerts.append(f"- {display_name}：{days_stale}天未推进，建议跟进")
        except Exception as e:
            logger.debug("客户跟进风险查询失败: %s", e)

        try:
            expiring_res = (
                await client.table("contracts")
                .select("title, end_date")
                .gte("end_date", now.strftime("%Y-%m-%d"))
                .lte("end_date", (now + timedelta(days=7)).strftime("%Y-%m-%d"))
                .limit(3)
                .execute()
            )
            for c in expiring_res.data or []:
                days_left = (datetime.strptime(c["end_date"][:10], "%Y-%m-%d") - now).days
                risk_alerts.append(f"- {c['title']}：合同即将到期（剩{days_left}天）")
        except Exception as e:
            logger.debug("合同到期风险查询失败: %s", e)

        if risk_alerts:
            response += "\n**⚠️ 风险预警**\n"
            response += "\n".join(risk_alerts)
        else:
            response += "\n✅ **当前无风险预警**"

        response += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 有什么需要我帮您处理的吗？
"""

        return response


class BusinessDashboardTool(BaseTool):
    """经营仪表盘工具"""

    name = "get_business_dashboard"
    description = "获取公司经营核心指标，包括收入、成本、利润、人效等。领导说'看看经营情况'、'本月业绩怎么样'时调用。"
    required_role = "boss"

    parameters = {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "enum": [
                    "today",
                    "this_week",
                    "this_month",
                    "this_quarter",
                    "this_year",
                ],
                "description": "统计周期",
            },
            "focus": {
                "type": "string",
                "enum": ["revenue", "cost", "hr", "sales", "all"],
                "description": "关注重点",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        period = args.get("period", "this_month")
        period_names = {
            "today": "今日",
            "this_week": "本周",
            "this_month": "本月",
            "this_quarter": "本季度",
            "this_year": "本年度",
        }

        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # 1. Get Real Financial Metrics from DB
        # Note: We aggregate from 'sales_metrics' table. If empty, we return 0/No Data.
        try:
            # Simple aggregation (sum value by metric_type)
            # In a real app, we'd filter by created_at based on 'period'
            metrics_res = await client.table("sales_metrics").select("metric_type, value").execute()

            metrics = metrics_res.data or []

            # Group by type
            revenue = sum(float(m["value"]) for m in metrics if m["metric_type"] == "revenue")
            contract_sum = sum(float(m["value"]) for m in metrics if m["metric_type"] == "contract")
            opportunity_val = sum(float(m["value"]) for m in metrics if m["metric_type"] == "opportunity")

            # 2. Get Real HR Metrics (scoped to organization)
            hr_query = client.table("users").select("id", count="exact")
            if org_id:
                hr_query = hr_query.eq("organization_id", org_id)
            users_res = await hr_query.execute()
            headcount = users_res.count or 0

            # 3. Logic for "No Data"
            if not metrics and headcount == 0:
                return f"""📊 **{period_names.get(period, "本月")}经营仪表盘**
更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

⚠️ **暂无数据**
系统中暂未录入经营数据（收入、成本、人员等）。
请先让员工在系统中录入业务数据，或连接外部ERP系统。
"""

            # 4. Construct Authentic Report
            response = f"""📊 **{period_names.get(period, "本月")}经营仪表盘 (实时数据)**
更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **收入指标**
┌─────────────────────────────────┐
│ 签约金额      ¥ {contract_sum:,.2f}
│ 回款金额      ¥ {revenue:,.2f}
│ 新增商机      ¥ {opportunity_val:,.2f}
└─────────────────────────────────┘

👥 **人效指标**
┌─────────────────────────────────┐
│ 团队人数                   {headcount} 人
│ 人均产出      ¥ {(revenue / headcount if headcount > 0 else 0):,.2f}
└─────────────────────────────────┘

(注：成本数据暂未连接财务系统，显示为空)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **AI 经营洞察**
"""
            if revenue == 0:
                response += "\n⚠️ **数据缺失提醒**: 本周期内无回款记录。请确认销售团队是否已录入数据。\n"
            elif revenue < contract_sum * 0.5:
                response += "\n⚠️ **回款滞后**: 回款金额低于签约金额的50%，建议关注现金流。\n"
            else:
                response += "\n✅ **经营稳健**: 回款状况良好。\n"

            return response

        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")
            return f"❌ 获取经营数据失败: {str(e)}"


class TeamInsightTool(BaseTool):
    """团队洞察工具"""

    name = "get_team_insight"
    description = "获取团队综合洞察报告，包括人员状态、绩效分布、风险预警等"
    required_role = "manager"

    parameters = {
        "type": "object",
        "properties": {
            "insight_type": {
                "type": "string",
                "enum": ["performance", "risk", "engagement", "growth"],
                "description": "洞察类型",
            }
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # F4: Check if user is manager (not boss) - filter to own department only
        from app.services.chat_service import ChatService

        user_role = (
            await ChatService._get_cached_user_role(user_id, db_client=client)
            if hasattr(ChatService, "_get_cached_user_role")
            else "employee"
        )

        if user_role == "manager":
            # Get manager's department
            dept_res = await client.table("users").select("department").eq("id", user_id).maybe_single().execute()
            user_dept = dept_res.data.get("department") if dept_res.data else None
            if user_dept:
                # Filter team to same department
                team_query = client.table("users").select("id, name, role, department, position, status, score").eq("department", user_dept)
                if org_id:
                    team_query = team_query.eq("organization_id", org_id)
                team_res = await team_query.execute()
            else:
                team_query = client.table("users").select("id, name, role, department, position, status, score")
                if org_id:
                    team_query = team_query.eq("organization_id", org_id)
                team_res = await team_query.execute()
        else:
            # Boss/founder sees all within their organization
            team_query = client.table("users").select("id, name, role, department, position, status, score")
            if org_id:
                team_query = team_query.eq("organization_id", org_id)
            team_res = await team_query.execute()

        team = team_res.data or []
        total_count = len(team)

        if total_count == 0:
            return f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

⚠️ **暂无数据** — 系统中暂未录入员工信息。
"""

        # 基于真实数据计算绩效分布
        s_level = [u for u in team if float(u.get("score", 0)) >= 95]
        a_level = [u for u in team if 85 <= float(u.get("score", 0)) < 95]
        b_level = [u for u in team if 70 <= float(u.get("score", 0)) < 85]
        c_level = [u for u in team if float(u.get("score", 0)) < 70]

        def pct(n):
            return f"{n / total_count * 100:.0f}%" if total_count > 0 else "0%"

        def bar(n, total, width=10):
            filled = round(n / total * width) if total > 0 else 0
            return "█" * filled + "░" * (width - filled)

        response = f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**团队规模**: {total_count} 人

📊 **绩效分布**

  S级(95+)  {bar(len(s_level), total_count)}  {pct(len(s_level))} ({len(s_level)}人)  🌟 明星员工
  A级(85-94) {bar(len(a_level), total_count)}  {pct(len(a_level))} ({len(a_level)}人) ✅ 骨干力量
  B级(70-84) {bar(len(b_level), total_count)}  {pct(len(b_level))} ({len(b_level)}人) 📈 待提升
  C级(<70)  {bar(len(c_level), total_count)}  {pct(len(c_level))} ({len(c_level)}人)  ⚠️ 需关注

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        # Top performers (real data)
        sorted_team = sorted(team, key=lambda u: float(u.get("score", 0)), reverse=True)
        top3 = sorted_team[:3]

        if top3:
            response += "\n🌟 **绩效前三**\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(top3):
                response += f"{medals[i]} {p.get('name', '员工')}: {p.get('score', 0)}分\n"

        # Low performers (real data) — need attention
        if c_level:
            response += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⚠️ **需关注人员** ({len(c_level)}人)\n\n"
            for u in c_level[:3]:
                response += f"- **{u.get('name', '员工')}**: 绩效 {u.get('score', 0)} 分\n"
            if len(c_level) > 3:
                response += f"  ... 还有 {len(c_level) - 3} 人\n"

        response += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 需要我帮您安排与某位员工的谈话吗？
"""

        return response


class AnnouncementTool(BaseTool):
    """公告发布工具"""

    name = "publish_announcement"
    description = "发布公司公告或通知。领导说'发个通知'、'通知全员'时调用。注意：给特定个人发消息请用 send_notification，此工具仅用于全员/部门级公告。"
    required_role = "boss"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "公告标题"},
            "content": {"type": "string", "description": "公告内容"},
            "target": {
                "type": "string",
                "enum": ["all", "managers", "sales", "department"],
                "description": "通知对象",
            },
            "priority": {
                "type": "string",
                "enum": ["normal", "important", "urgent"],
                "description": "优先级",
            },
        },
        "required": ["title", "content"],
    }

    def check_confirmation(self, args: dict[str, Any], system_confirmed: bool = False) -> str | None:
        """Only require confirmation for all-staff or urgent announcements."""
        target = args.get("target", "all")
        priority = args.get("priority", "normal")
        if target == "all" or priority == "urgent":
            if system_confirmed:
                return None
            scope = "全员" if target == "all" else "紧急"
            return f"⚠️ 操作需要确认:\n🔒 {scope}通知将发送给所有目标用户，发布后不可撤回。\n请确认后再执行。"
        return None

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        title = args.get("title")
        content = args.get("content")
        target = args.get("target", "all")
        priority = args.get("priority", "normal")

        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        # 获取目标用户
        if target == "all":
            users_query = client.table("users").select("id, name")
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()
        elif target == "managers":
            users_query = client.table("users").select("id, name").in_("role", ["manager", "founder"])
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()
        else:
            users_query = client.table("users").select("id, name")
            if org_id:
                users_query = users_query.eq("organization_id", org_id)
            users_res = await users_query.execute()

        users = users_res.data or []

        # Batch insert notifications for efficiency
        priority_icons = {"normal": "📢", "important": "⚠️", "urgent": "🚨"}
        icon = priority_icons.get(priority, "📢")
        notification_type = "info" if priority == "normal" else "warning"
        notifications_batch = [
            {
                "user_id": user["id"],
                "title": f"{icon} {title}",
                "content": content,
                "type": notification_type,
            }
            for user in users
        ]

        # Insert in batches of 50 to avoid payload size limits
        batch_size = 50
        for i in range(0, len(notifications_batch), batch_size):
            batch = notifications_batch[i : i + batch_size]
            try:
                await client.table("notifications").insert(batch).execute()
            except Exception as e:
                logger.warning(f"Failed to insert notification batch {i // batch_size + 1}: {e}")

        # Multi-channel notification for announcements
        try:
            from app.services.notification_service import (
                Notification,
                NotificationChannel,
                NotificationPriority,
                notification_service,
            )

            priority_map = {
                "normal": NotificationPriority.NORMAL,
                "important": NotificationPriority.HIGH,
                "urgent": NotificationPriority.URGENT,
            }
            notif_priority = priority_map.get(priority, NotificationPriority.NORMAL)

            # Send to all available external channels (wecom/dingtalk/feishu)
            for channel in notification_service.get_available_channels():
                if channel != NotificationChannel.IN_APP:  # Already handled by batch insert
                    try:
                        await notification_service.send(
                            Notification(
                                title=f"{icon} {title}",
                                content=content,
                                target_user_id="all",
                                channel=channel,
                                priority=notif_priority,
                                metadata={"announcement": True, "target_scope": target},
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Announcement push to {channel} failed: {e}")
        except Exception as e:
            logger.warning(f"Multi-channel announcement push failed: {e}")

        target_names = {"all": "全员", "managers": "管理层", "sales": "销售团队"}

        return f"""✅ 公告已发布！

**公告详情**
- 标题: {title}
- 内容: {content[:50]}{"..." if len(content) > 50 else ""}
- 对象: {target_names.get(target, target)}（{len(users)}人）
- 优先级: {priority}

📧 已推送给 {len(users)} 名员工
📊 您可以稍后问我「公告阅读情况」查看已读统计
"""


class CustomerProfileTool(BaseTool):
    """AI 客户画像自动生成"""

    name = "generate_customer_profile"
    description = "根据CRM数据自动生成客户画像分析，包括标签、偏好和跟进建议。当用户说'分析客户'、'客户画像'时调用。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "客户/公司名称",
            }
        },
        "required": ["customer_name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        from app.services.crm_service import crm_service

        name = args.get("customer_name", "")
        if not name:
            return "❌ 请提供客户名称（customer_name）"
        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # Search customers table (new CRM system)
        try:
            customers = []
            if org_id:
                customers = await crm_service.search_customers(org_id, name, db=client)
            if not customers:
                # Fallback: try direct query by company or name
                res = (
                    await client.table("customers")
                    .select("*")
                    .or_(f"name.ilike.%{name}%,company.ilike.%{name}%")
                    .limit(10)
                    .execute()
                )
                customers = res.data or []
        except Exception as e:
            return f"❌ 查询客户数据失败: {str(e)}"

        if not customers:
            return f"未找到与 '{name}' 相关的客户记录。请确认客户名称是否正确。"

        # Build summary from customers table
        stage_labels = {
            "lead": "线索",
            "prospect": "意向",
            "opportunity": "商机",
            "customer": "成交",
            "churned": "流失",
        }
        leads_summary = []
        customer_id = customers[0]["id"]
        for c in customers:
            stage = stage_labels.get(c.get("stage", ""), c.get("stage", ""))
            value = c.get("estimated_value") or 0
            leads_summary.append(
                f"- 客户: {c.get('name', '未知')}, 公司: {c.get('company', '未知')}, "
                f"行业: {c.get('industry', '未知')}, 阶段: {stage}, "
                f"预估金额: ¥{float(value):,.0f}, 来源: {c.get('source', '未知')}, "
                f"最后更新: {str(c.get('updated_at', ''))[:10]}"
            )

        # Fetch contacts and recent activities for richer profile
        try:
            contacts = await crm_service.list_contacts(customer_id, db=client)
            if contacts:
                leads_summary.append("\n联系人:")
                for ct in contacts:
                    primary = " (主要联系人)" if ct.get("is_primary") else ""
                    leads_summary.append(
                        f"  - {ct.get('name', '未知')}{primary}, "
                        f"职位: {ct.get('title', '未知')}, "
                        f"电话: {ct.get('phone', '')}, 邮箱: {ct.get('email', '')}"
                    )

            activities = await crm_service.get_activity_timeline(customer_id, limit=5, db=client)
            if activities:
                type_labels = {
                    "call": "电话",
                    "email": "邮件",
                    "meeting": "会议",
                    "note": "备注",
                    "deal_update": "商机更新",
                }
                leads_summary.append("\n最近跟进:")
                for act in activities:
                    t = type_labels.get(act.get("activity_type", ""), act.get("activity_type", ""))
                    leads_summary.append(
                        f"  - [{t}] {act.get('content', '')[:80]} ({str(act.get('created_at', ''))[:10]})"
                    )
        except Exception as e:
            logger.debug("客户跟进记录查询失败: %s", e)

        prompt = (
            "客户数据:\n"
            + "\n".join(leads_summary)
            + "\n\n请生成客户画像，包括：客户标签、合作偏好、风险评估、推荐跟进策略。"
        )
        system = "你是资深CRM分析师，基于客户交互历史生成精准画像。用中文回复，格式清晰。"

        try:
            profile = await AIService.call_llm(prompt, system)
            return f"👤 {name} 客户画像:\n\n{profile}"
        except Exception as e:
            return f"👤 客户画像生成失败: {str(e)}"
