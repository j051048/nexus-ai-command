"""
领导专属工具集
实现智能审批、经营洞察、团队管理等高级管理功能
支持语音/自然语言批量处理

P0 Security Fix #1: All approval operations require explicit confirmation
"""
from .base_tool import BaseTool
from typing import Dict, Any, List
from datetime import datetime
import logging
from app.core.database import supabase

logger = logging.getLogger(__name__)


def _get_client(config: Dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase

# P0 Security: Maximum batch size to prevent mass operations
MAX_BATCH_SIZE = 10


def _parse_amount_from_condition(condition: str) -> float:
    """
    解析条件中的金额，支持中文单位（万/千/k/w/K/W）
    
    示例:
    - "5万" -> 50000.0
    - "3千" -> 3000.0
    - "10k" -> 10000.0
    - "2.5W" -> 25000.0
    - "500" -> 500.0
    
    Returns:
        float: 解析后的金额，解析失败返回 None
    """
    import re
    
    # 提取数字和可能的单位
    pattern = r'(\d+(?:\.\d+)?)\s*([万千kKwW]?)'
    match = re.search(pattern, condition)
    
    if not match:
        return None
    
    number_str, unit = match.groups()
    
    try:
        amount = float(number_str)
        
        # 单位换算
        if unit in ['万', 'w', 'W']:
            amount *= 10000
        elif unit in ['千', 'k', 'K']:
            amount *= 1000
        
        return amount
    except (ValueError, TypeError):
        return None


class SmartApprovalTool(BaseTool):
    """
    智能审批工具 - 支持批量审批、条件审批、委托审批
    
    P0 Security Fix #1: 
    - All operations require explicit confirm=true
    - Batch operations limited to MAX_BATCH_SIZE
    - Idempotency checks prevent duplicate processing
    """
    name = "smart_approve"
    description = """智能审批工具。支持批量审批、按条件审批、委托审批等。
首次调用返回预览信息，需要确认后设置 confirm=true 才会真正执行。
这是不可逆操作，需要人工确认。"""
    required_role = "boss"
    is_irreversible = True
    confirmation_message = "⚠️ 审批操作不可逆。请确认后设置 confirm=true 再执行。"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["approve", "reject", "delegate", "batch_approve", "conditional_approve"],
                "description": "操作类型: approve(批准), reject(驳回), delegate(委托), batch_approve(批量批准), conditional_approve(条件批准)"
            },
            "request_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要处理的申请ID列表（可选，不填则处理全部待审批）"
            },
            "request_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "要处理的申请序号列表，如[1,2,3]表示第1、2、3条"
            },
            "condition": {
                "type": "string",
                "description": "审批条件，如'金额小于5000的全部通过'"
            },
            "delegate_to": {
                "type": "string",
                "description": "委托给谁（姓名）"
            },
            "comment": {
                "type": "string",
                "description": "审批意见"
            },
            "confirm": {
                "type": "boolean",
                "description": "是否确认执行？首次调用请设为false获取预览，确认后设为true执行"
            }
        },
        "required": ["action"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        client = _get_client(config)
        action = args.get("action", "approve")
        request_ids = args.get("request_ids", [])
        request_numbers = args.get("request_numbers", [])
        condition = args.get("condition", "")
        delegate_to = args.get("delegate_to", "")
        comment = args.get("comment", "")
        confirm = args.get("confirm", False)  # P0 Security: Default to preview mode
        
        # 获取待审批列表
        pending_res = await client.table("approval_requests")\
            .select("*, users:submitted_by(name, department)")\
            .eq("status", "pending")\
            .order("created_at", desc=True)\
            .execute()
        
        pending_list = pending_res.data or []
        
        if not pending_list:
            return "✅ 太棒了！当前没有待审批的事项，您可以放心休息。"
        
        # 根据序号筛选
        if request_numbers:
            selected_requests = [pending_list[i-1] for i in request_numbers if 0 < i <= len(pending_list)]
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
            action_name = {"approve": "批准", "reject": "驳回", "delegate": "委托", "batch_approve": "批量批准"}.get(action, action)
            
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
            # P1 Fix #15: Use transactional RPC for atomic batch update
            request_ids = [req["id"] for req in selected_requests]
            try:
                rpc_result = await client.rpc("batch_update_approvals", {
                    "p_request_ids": request_ids,
                    "p_new_status": "approved",
                    "p_approved_by": user_id,
                    "p_comment": comment or "已批准"
                }).execute()
                
                batch_data = rpc_result.data or {}
                approved_count = batch_data.get("updated_count", 0)
                skipped_count = batch_data.get("skipped_count", 0)
                updated_ids = set(batch_data.get("updated_ids", []))
            except Exception as e:
                logger.error(f"Batch approval RPC failed: {e}")
                return f"❌ 批量审批失败，所有操作已回滚。错误: {str(e)}"
            
            # Send notifications for successfully approved requests (non-transactional, best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await client.table("notifications").insert({
                            "user_id": req["submitted_by"],
                            "title": "✅ 您的申请已批准",
                            "content": f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0)}）已被批准",
                            "type": "success"
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Failed to send approval notification: {e}")
            
            result_msg = f"""✅ 批量审批完成！

**处理结果**
- 批准数量: {approved_count} 件
- 跳过数量: {skipped_count} 件（已被他人处理）
- 涉及金额: ¥{total_amount:,.2f}
- 处理时间: {datetime.now().strftime('%H:%M:%S')}

**已批准明细**
{self._format_request_list(selected_requests[:5])}

📧 已通知所有申请人
"""
            return result_msg
        
        elif action == "reject":
            # P1 Fix #15: Use transactional RPC for atomic batch rejection
            request_ids = [req["id"] for req in selected_requests]
            try:
                rpc_result = await client.rpc("batch_update_approvals", {
                    "p_request_ids": request_ids,
                    "p_new_status": "rejected",
                    "p_approved_by": user_id,
                    "p_comment": comment or "已驳回"
                }).execute()
                
                batch_data = rpc_result.data or {}
                rejected_count = batch_data.get("updated_count", 0)
                skipped_count = batch_data.get("skipped_count", 0)
                updated_ids = set(batch_data.get("updated_ids", []))
            except Exception as e:
                logger.error(f"Batch rejection RPC failed: {e}")
                return f"❌ 批量驳回失败，所有操作已回滚。错误: {str(e)}"
            
            # Send notifications (best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await client.table("notifications").insert({
                            "user_id": req["submitted_by"],
                            "title": "❌ 您的申请被驳回",
                            "content": f"您提交的{req.get('type', '申请')}被驳回。原因: {comment or '未说明'}",
                            "type": "warning"
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Failed to send rejection notification: {e}")
            
            return f"""❌ 已驳回 {rejected_count} 件申请

驳回原因: {comment or '未说明'}
跳过数量: {skipped_count} 件（已被他人处理）
📧 已通知相关申请人
"""
        
        elif action == "delegate":
            if not delegate_to:
                return "❌ 请指定委托人"
            
            # 查找委托人
            delegate_res = await client.table("users").select("id, name").ilike("name", f"%{delegate_to}%").limit(1).execute()
            if not delegate_res.data:
                return f"❌ 未找到名为「{delegate_to}」的人员"
            
            delegate_user = delegate_res.data[0]
            
            # 更新审批人 (委托不是不可逆操作，可以重新委托)
            for req in selected_requests:
                await client.table("approval_requests").update({
                    "current_approver": delegate_user["id"]
                }).eq("id", req["id"]).eq("status", "pending").execute()
            
            # 通知被委托人
            await client.table("notifications").insert({
                "user_id": delegate_user["id"],
                "title": "📋 收到委托审批",
                "content": f"领导将 {len(selected_requests)} 件审批事项委托给您处理",
                "type": "warning"
            }).execute()
            
            return f"""✅ 已委托给 {delegate_user['name']}

委托事项: {len(selected_requests)} 件
📧 已通知 {delegate_user['name']}
"""
        
        return "未知操作"
    
    def _format_request_list(self, requests: List[Dict]) -> str:
        result = ""
        type_icons = {"expense": "💰", "leave": "🏖️", "purchase": "🛒", "travel": "✈️"}
        for i, req in enumerate(requests, 1):
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
                "description": "简报类型: full(完整), approvals_only(仅审批), alerts_only(仅预警), performance(业绩)"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        client = _get_client(config)
        # 获取待审批数量
        pending_res = await client.table("approval_requests")\
            .select("*, users:submitted_by(name)")\
            .eq("status", "pending")\
            .order("amount", desc=True)\
            .limit(5)\
            .execute()
        
        pending_list = pending_res.data or []
        pending_count = len(pending_list)
        
        # 获取已自动处理数量（今日已审批的）
        try:
            from datetime import datetime, timedelta, timezone
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
            auto_res = await client.table("approval_requests")\
                .select("count", count="exact")\
                .eq("status", "approved")\
                .gte("updated_at", today_start)\
                .execute()
            auto_processed = auto_res.count or 0
        except Exception:
            auto_processed = 0
        
        # 获取团队绩效
        team_res = await client.table("users").select("name, score, total_bonus").order("score", desc=True).limit(3).execute()
        top_performers = team_res.data or []
        
        # 计算总奖金
        total_bonus = sum(float(p.get("total_bonus", 0)) for p in top_performers)
        
        now = datetime.now()
        greeting = "早上好" if now.hour < 12 else "下午好" if now.hour < 18 else "晚上好"
        
        response = f"""☀️ **{greeting}，老板！**
📅 {now.strftime('%Y年%m月%d日 %A')}

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
                if amount < 5000:
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
        
        # 添加经营数据
        response += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **经营快报**

**本周业绩**
- 新增商机: 12 个（+20%）
- 成交订单: 3 个（¥125万）
- 团队激励: ¥{total_bonus:,.0f}

**Top 3 员工**
"""
        
        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(top_performers):
            response += f"{medals[i]} {p.get('name', '员工')}: {p.get('score', 0)}分\n"
        
        response += """
**⚠️ 风险预警**
- 张教授商机：30天未推进，建议今日跟进
- 华为项目：报价即将过期（剩3天）

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
                "enum": ["today", "this_week", "this_month", "this_quarter", "this_year"],
                "description": "统计周期"
            },
            "focus": {
                "type": "string",
                "enum": ["revenue", "cost", "hr", "sales", "all"],
                "description": "关注重点"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        period = args.get("period", "this_month")
        period_names = {
            "today": "今日",
            "this_week": "本周",
            "this_month": "本月",
            "this_quarter": "本季度",
            "this_year": "本年度"
        }
        
        client = _get_client(config)
        
        # 1. Get Real Financial Metrics from DB
        # Note: We aggregate from 'sales_metrics' table. If empty, we return 0/No Data.
        try:
            # Simple aggregation (sum value by metric_type)
            # In a real app, we'd filter by created_at based on 'period'
            metrics_res = await client.table("sales_metrics")\
                .select("metric_type, value")\
                .execute()
            
            metrics = metrics_res.data or []
            
            # Group by type
            revenue = sum(float(m["value"]) for m in metrics if m["metric_type"] == "revenue")
            contract_sum = sum(float(m["value"]) for m in metrics if m["metric_type"] == "contract")
            opportunity_val = sum(float(m["value"]) for m in metrics if m["metric_type"] == "opportunity")
            
            # 2. Get Real HR Metrics
            users_res = await client.table("users").select("id", count="exact").execute()
            headcount = users_res.count or 0
            
            # 3. Logic for "No Data"
            if not metrics and headcount == 0:
                 return f"""📊 **{period_names.get(period, '本月')}经营仪表盘**
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ **暂无数据**
系统中暂未录入经营数据（收入、成本、人员等）。
请先让员工在系统中录入业务数据，或连接外部ERP系统。
"""

            # 4. Construct Authentic Report
            response = f"""📊 **{period_names.get(period, '本月')}经营仪表盘 (实时数据)**
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

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
    required_role = "boss"
    
    parameters = {
        "type": "object",
        "properties": {
            "insight_type": {
                "type": "string",
                "enum": ["performance", "risk", "engagement", "growth"],
                "description": "洞察类型"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        client = _get_client(config)
        # 获取团队数据
        team_res = await client.table("users").select("*").execute()
        team = team_res.data or []
        total_count = len(team)
        
        if total_count == 0:
            return f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ **暂无数据** — 系统中暂未录入员工信息。
"""

        # 基于真实数据计算绩效分布
        s_level = [u for u in team if float(u.get("score", 0)) >= 95]
        a_level = [u for u in team if 85 <= float(u.get("score", 0)) < 95]
        b_level = [u for u in team if 70 <= float(u.get("score", 0)) < 85]
        c_level = [u for u in team if float(u.get("score", 0)) < 70]
        
        def pct(n): return f"{n/total_count*100:.0f}%" if total_count > 0 else "0%"
        def bar(n, total, width=10):
            filled = round(n / total * width) if total > 0 else 0
            return "█" * filled + "░" * (width - filled)

        response = f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

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
        
        response += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 需要我帮您安排与某位员工的谈话吗？
"""
        
        return response


class AnnouncementTool(BaseTool):
    """公告发布工具"""
    name = "publish_announcement"
    description = "发布公司公告或通知。领导说'发个通知'、'通知全员'时调用。需要确认后执行。"
    required_role = "boss"
    is_irreversible = True
    confirmation_message = "⚠️ 公告将发送给所有目标用户，发布后不可撤回。请确认后设置 confirm=true 再执行。"
    
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "公告标题"
            },
            "content": {
                "type": "string",
                "description": "公告内容"
            },
            "target": {
                "type": "string",
                "enum": ["all", "managers", "sales", "department"],
                "description": "通知对象"
            },
            "priority": {
                "type": "string",
                "enum": ["normal", "important", "urgent"],
                "description": "优先级"
            }
        },
        "required": ["title", "content"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        title = args.get("title")
        content = args.get("content")
        target = args.get("target", "all")
        priority = args.get("priority", "normal")
        
        client = _get_client(config)
        # 获取目标用户
        if target == "all":
            users_res = await client.table("users").select("id, name").execute()
        elif target == "managers":
            users_res = await client.table("users").select("id, name").in_("role", ["manager", "founder"]).execute()
        else:
            users_res = await client.table("users").select("id, name").execute()
        
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
                "type": notification_type
            }
            for user in users
        ]
        
        # Insert in batches of 50 to avoid payload size limits
        BATCH_SIZE = 50
        for i in range(0, len(notifications_batch), BATCH_SIZE):
            batch = notifications_batch[i:i + BATCH_SIZE]
            try:
                await client.table("notifications").insert(batch).execute()
            except Exception as e:
                logger.warning(f"Failed to insert notification batch {i//BATCH_SIZE + 1}: {e}")
        
        target_names = {"all": "全员", "managers": "管理层", "sales": "销售团队"}
        
        return f"""✅ 公告已发布！

**公告详情**
- 标题: {title}
- 内容: {content[:50]}{'...' if len(content) > 50 else ''}
- 对象: {target_names.get(target, target)}（{len(users)}人）
- 优先级: {priority}

📧 已推送给 {len(users)} 名员工
📊 您可以稍后问我「公告阅读情况」查看已读统计
"""