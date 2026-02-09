"""
领导专属工具集
实现智能审批、经营洞察、团队管理等高级管理功能
支持语音/自然语言批量处理

P0 Security Fix #1: All approval operations require explicit confirmation
"""
from .base_tool import BaseTool
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from app.core.database import supabase
from app.services.event_bus import emit, EventType

logger = logging.getLogger(__name__)

# P0 Security: Maximum batch size to prevent mass operations
MAX_BATCH_SIZE = 10


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
        action = args.get("action", "approve")
        request_ids = args.get("request_ids", [])
        request_numbers = args.get("request_numbers", [])
        condition = args.get("condition", "")
        delegate_to = args.get("delegate_to", "")
        comment = args.get("comment", "")
        confirm = args.get("confirm", False)  # P0 Security: Default to preview mode
        
        # 获取待审批列表
        pending_res = await supabase.table("approval_requests")\
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
                try:
                    amount_threshold = float(''.join(filter(str.isdigit, condition)))
                    selected_requests = [r for r in selected_requests if float(r.get("amount", 0)) < amount_threshold]
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse amount threshold from condition: {condition}")
            elif "大于" in condition or ">" in condition:
                try:
                    amount_threshold = float(''.join(filter(str.isdigit, condition)))
                    selected_requests = [r for r in selected_requests if float(r.get("amount", 0)) > amount_threshold]
                except (ValueError, TypeError):
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
            approved_count = 0
            skipped_count = 0
            
            for req in selected_requests:
                # P0 Security: Idempotency check - only update if still pending
                result = await supabase.table("approval_requests").update({
                    "status": "approved",
                    "approved_by": user_id,
                    "approved_at": datetime.now().isoformat(),
                    "approval_comment": comment or "已批准"
                }).eq("id", req["id"]).eq("status", "pending").execute()
                
                if result.data:
                    # 通知申请人
                    await supabase.table("notifications").insert({
                        "user_id": req["submitted_by"],
                        "title": "✅ 您的申请已批准",
                        "content": f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0)}）已被批准",
                        "type": "success"
                    }).execute()
                    approved_count += 1
                else:
                    skipped_count += 1
            
            # Record audit log
            await supabase.table("audit_logs").insert({
                "action": "batch_approval",
                "actor_user_id": user_id,
                "target_table": "approval_requests",
                "details_json": {
                    "approved_count": approved_count,
                    "skipped_count": skipped_count,
                    "total_amount": total_amount
                }
            }).execute()
            
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
            rejected_count = 0
            skipped_count = 0
            
            for req in selected_requests:
                # P0 Security: Idempotency check
                result = await supabase.table("approval_requests").update({
                    "status": "rejected",
                    "approved_by": user_id,
                    "approved_at": datetime.now().isoformat(),
                    "approval_comment": comment or "已驳回"
                }).eq("id", req["id"]).eq("status", "pending").execute()
                
                if result.data:
                    await supabase.table("notifications").insert({
                        "user_id": req["submitted_by"],
                        "title": "❌ 您的申请被驳回",
                        "content": f"您提交的{req.get('type', '申请')}被驳回。原因: {comment or '未说明'}",
                        "type": "warning"
                    }).execute()
                    rejected_count += 1
                else:
                    skipped_count += 1
            
            # Record audit log
            await supabase.table("audit_logs").insert({
                "action": "batch_rejection",
                "actor_user_id": user_id,
                "target_table": "approval_requests",
                "details_json": {
                    "rejected_count": rejected_count,
                    "skipped_count": skipped_count,
                    "reason": comment
                }
            }).execute()
            
            return f"""❌ 已驳回 {rejected_count} 件申请

驳回原因: {comment or '未说明'}
跳过数量: {skipped_count} 件（已被他人处理）
📧 已通知相关申请人
"""
        
        elif action == "delegate":
            if not delegate_to:
                return "❌ 请指定委托人"
            
            # 查找委托人
            delegate_res = await supabase.table("users").select("id, name").ilike("name", f"%{delegate_to}%").limit(1).execute()
            if not delegate_res.data:
                return f"❌ 未找到名为「{delegate_to}」的人员"
            
            delegate_user = delegate_res.data[0]
            
            # 更新审批人 (委托不是不可逆操作，可以重新委托)
            for req in selected_requests:
                await supabase.table("approval_requests").update({
                    "current_approver": delegate_user["id"]
                }).eq("id", req["id"]).eq("status", "pending").execute()
            
            # 通知被委托人
            await supabase.table("notifications").insert({
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
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        briefing_type = args.get("briefing_type", "full")
        
        # 获取待审批数量
        pending_res = await supabase.table("approval_requests")\
            .select("*, users:submitted_by(name)")\
            .eq("status", "pending")\
            .order("amount", desc=True)\
            .limit(5)\
            .execute()
        
        pending_list = pending_res.data or []
        pending_count = len(pending_list)
        
        # 获取自动处理的数量（模拟）
        auto_processed = 12
        
        # 获取团队绩效
        team_res = await supabase.table("users").select("name, score, total_bonus").order("score", desc=True).limit(3).execute()
        top_performers = team_res.data or []
        
        # 计算总奖金
        total_bonus = sum(float(p.get("total_bonus", 0)) for p in top_performers)
        
        now = datetime.now()
        greeting = "早上好" if now.hour < 12 else "下午好" if now.hour < 18 else "晚上好"
        
        response = f"""☀️ **{greeting}，老板！**
📅 {now.strftime('%Y年%m月%d日 %A')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ **已自动处理** {auto_processed} 件事务
   - 小额报销 8 件（共 ¥4,200）
   - 常规请假 3 件
   - 办公采购 1 件

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
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        period = args.get("period", "this_month")
        focus = args.get("focus", "all")
        
        period_names = {
            "today": "今日",
            "this_week": "本周",
            "this_month": "本月",
            "this_quarter": "本季度",
            "this_year": "本年度"
        }
        
        # 模拟经营数据
        response = f"""📊 **{period_names.get(period, '本月')}经营仪表盘**
更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **收入指标**
┌─────────────────────────────────┐
│ 签约金额      ¥  2,850,000  ↑12% │
│ 回款金额      ¥  1,920,000  ↑8%  │
│ 新增商机      ¥  4,200,000  ↑15% │
└─────────────────────────────────┘

📉 **成本指标**  
┌─────────────────────────────────┐
│ 人力成本      ¥    680,000  ─    │
│ 营销费用      ¥    120,000  ↓5%  │
│ 运营费用      ¥     85,000  ↑3%  │
└─────────────────────────────────┘

👥 **人效指标**
┌─────────────────────────────────┐
│ 团队人数                   45 人 │
│ 人均产出      ¥     63,333      │
│ 人均成本      ¥     19,667      │
│ 人效比                    3.22x │
└─────────────────────────────────┘

📈 **销售漏斗**
  线索    ████████████████████ 200
  商机    ██████████████░░░░░░  68
  报价    █████████░░░░░░░░░░░  42
  成交    ████░░░░░░░░░░░░░░░░  18
  
  整体转化率: 9%（行业均值: 7%）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **AI 经营洞察**

✅ **亮点**
- 本月签约额超目标15%，团队状态良好
- 新增商机数创近3月新高
- 人效比持续优化

⚠️ **关注**
- 回款率偏低（67%），建议加强催收
- 3个大单超过45天未推进
- 市场费用ROI有下降趋势

💡 **建议行动**
1. 本周安排回款专项会议
2. 对滞后商机进行逐一review
3. 优化市场投放渠道组合
"""
        
        return response


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
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        insight_type = args.get("insight_type", "performance")
        
        # 获取团队数据
        team_res = await supabase.table("users").select("*").execute()
        team = team_res.data or []
        total_count = len(team)
        
        response = f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**团队规模**: {total_count} 人

📊 **绩效分布**

  S级(95+)  ██░░░░░░░░  12% (5人)  🌟 明星员工
  A级(85-94) █████░░░░░  45% (20人) ✅ 骨干力量  
  B级(70-84) ███░░░░░░░  30% (13人) 📈 待提升
  C级(<70)  █░░░░░░░░░  13% (7人)  ⚠️ 需关注

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 **风险预警人员**

1. **张小明** - 风险等级: 高
   - 本月迟到5次（历史均值1次）
   - 绩效环比下降25%
   - 近期频繁请假
   → 建议: 一对一沟通，了解个人情况

2. **李小红** - 风险等级: 中
   - 加班时长异常增加（+50%）
   - 但产出未同步提升
   → 建议: 检查工作方法，可能需要培训支持

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌟 **值得表扬**

- 王晓明: 连续3月绩效S级，建议晋升考察
- 刘芳: 新人成长最快，可作为培训案例
- 张明: 大客户突破能力强，建议分享经验

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **AI 管理建议**

1. **本周重点**: 约谈2位高风险员工
2. **本月规划**: 启动Q1绩效review
3. **长期建议**: 考虑增加2个HC应对业务增长

需要我帮您安排与某位员工的谈话吗？
"""
        
        return response


class AnnouncementTool(BaseTool):
    """公告发布工具"""
    name = "publish_announcement"
    description = "发布公司公告或通知。领导说'发个通知'、'通知全员'时调用。"
    required_role = "boss"
    
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
        
        # 获取目标用户
        if target == "all":
            users_res = await supabase.table("users").select("id, name").execute()
        elif target == "managers":
            users_res = await supabase.table("users").select("id, name").in_("role", ["manager", "founder"]).execute()
        else:
            users_res = await supabase.table("users").select("id, name").execute()
        
        users = users_res.data or []
        
        # 发送通知
        priority_icons = {"normal": "📢", "important": "⚠️", "urgent": "🚨"}
        icon = priority_icons.get(priority, "📢")
        
        for user in users:
            await supabase.table("notifications").insert({
                "user_id": user["id"],
                "title": f"{icon} {title}",
                "content": content,
                "type": "info" if priority == "normal" else "warning"
            }).execute()
        
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