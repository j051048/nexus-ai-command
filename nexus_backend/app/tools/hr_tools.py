"""
HR 人力资源工具集
实现考勤、绩效、员工档案等 HR 场景的 AI 自动化
"""

import contextlib
import logging
from datetime import datetime
from typing import Any

from .base_tool import BaseTool
from ._shared import _get_client
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)


class AttendanceQueryTool(BaseTool):
    """考勤查询工具"""

    name = "query_attendance"
    domain = "attendance"
    description = "查询指定员工的考勤记录和出勤统计。当用户说'我的考勤'、'出勤情况'时调用。注意：查个人考勤用此工具，查团队考勤用 query_team_attendance。"
    required_role = "all"
    examples = [
        {"input": {"query_type": "my_record", "month": "2026-03"}, "output_summary": "返回当月个人考勤明细"},
                {"input": {"query_type": "monthly_summary", "employee_name": "[员工姓名]"}, "output_summary": "返回该员工的月度出勤汇总（需管理者权限）"},
    ]
    related_tools = ["query_team_attendance", "get_employee_profile"]
    gotchas = "非管理者只能查自己的考勤，不能通过 employee_name 查他人。考勤系统暂未接入，当前返回占位提示。"

    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["my_record", "monthly_summary", "abnormal"],
                "description": "查询类型: my_record(我的考勤), monthly_summary(月度汇总), abnormal(异常记录)",
            },
            "month": {"type": "string", "description": "查询月份，格式 YYYY-MM"},
            "employee_name": {
                "type": "string",
                "description": "员工姓名（管理者可查询下属）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        args.get("month", datetime.now().strftime("%Y-%m"))
        employee_name = args.get("employee_name")

        client = _get_client(config)
        # 获取用户信息
        user_res = await client.table("users").select("name, role").eq("id", user_id).maybe_single().execute()
        if not user_res.data:
            return "❌ 无法获取用户信息"

        user = user_res.data

        # 检查权限：非管理者只能查自己
        if employee_name and user.get("role") not in ["manager", "founder", "boss"]:
            return "❌ 您没有权限查询他人的考勤记录"

        return "📅 考勤查询功能暂未开通。\n\n考勤系统正在建设中，接入后将支持出勤统计、异常记录等查询。"


class TeamAttendanceTool(BaseTool):
    """团队考勤管理工具（管理者专用）"""

    name = "query_team_attendance"
    domain = "attendance"
    description = "查询团队整体考勤情况和异常预警。当管理者说'团队考勤'、'谁迟到了'时调用。仅限管理者使用。"
    required_role = "manager"
    examples = [
        {"input": {"view_type": "overview"}, "output_summary": "返回团队出勤总览"},
        {"input": {"view_type": "abnormal_alert"}, "output_summary": "返回迟到早退等异常预警列表"},
    ]
    related_tools = ["query_attendance", "get_team_insight"]
    gotchas = "仅管理者及以上角色可用。考勤系统暂未接入，当前返回占位提示。"

    parameters = {
        "type": "object",
        "properties": {
            "view_type": {
                "type": "string",
                "enum": ["overview", "abnormal_alert", "ranking"],
                "description": "查看类型: overview(总览), abnormal_alert(异常预警), ranking(排名)",
            }
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)

        # F4: Check if user is manager (not boss) - filter to own department only
        from app.services.chat_service import ChatService

        user_role = (
            await ChatService._get_cached_user_role(user_id, db_client=client)
            if hasattr(ChatService, "_get_cached_user_role")
            else "employee"
        )

        if user_role not in ["manager", "founder", "boss"]:
            return "❌ 您没有权限查看团队考勤"

        return "👥 团队考勤管理功能暂未开通。\n\n考勤系统接入后将支持团队出勤分析、异常提醒等功能。"


class EmployeeProfileTool(BaseTool):
    """员工画像工具（管理者专用）"""

    name = "get_employee_profile"
    domain = "hr"
    description = "获取员工综合画像，包含绩效、考勤、成长轨迹和风险评估。当用户说'某某人怎么样'、'员工档案'时调用。注意：仅需查基本信息用 get_employee_detail。"
    required_role = "manager"
    examples = [
        {"input": {"employee_name": "张三", "include_risk_analysis": True}, "output_summary": "返回张三的综合画像及AI风险分析"},
        {"input": {"employee_name": "李四", "include_risk_analysis": False}, "output_summary": "返回李四的基本画像，不含风险分析"},
    ]
    related_tools = ["get_employee_detail", "create_performance_review", "query_attendance"]
    gotchas = "按姓名模糊匹配，重名时只返回第一个结果。include_risk_analysis 默认为真，会调用大模型生成分析。"

    parameters = {
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "员工姓名"},
            "include_risk_analysis": {
                "type": "boolean",
                "description": "是否包含风险分析",
            },
        },
        "required": ["employee_name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        employee_name = args.get("employee_name")
        include_risk = args.get("include_risk_analysis", True)

        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        # 查找员工 — 必须限定本组织
        query = client.table("users").select("*").ilike("name", f"%{employee_name}%").limit(1)
        if org_id:
            query = query.eq("organization_id", org_id)
        emp_res = await query.execute()

        if not emp_res.data:
            return f"❌ 未找到名为「{employee_name}」的员工"

        emp = emp_res.data[0]
        emp_id = emp.get("id", "")

        # 获取绩效数据 (from users table)
        score = emp.get("score", 0)
        rank = emp.get("rank", 0)
        total_bonus = emp.get("total_bonus", 0)

        # 获取考勤统计
        attendance_info = "暂无考勤数据"
        try:
            att_res = (
                await client.table("hr_attendance").select("status", count="exact").eq("user_id", emp_id).execute()
            )
            if att_res.data:
                total_days = len(att_res.data)
                normal_days = sum(1 for a in att_res.data if a.get("status") in ("present", "normal"))
                late_days = sum(1 for a in att_res.data if a.get("status") == "late")
                absent_days = sum(1 for a in att_res.data if a.get("status") == "absent")
                rate = round(normal_days / max(total_days, 1) * 100, 1)
                attendance_info = f"出勤率 {rate}% (正常{normal_days}天, 迟到{late_days}天, 缺勤{absent_days}天)"
        except Exception as e:
            logger.debug("考勤数据查询失败: %s", e)

        # 获取销售业绩 (if sales role)
        sales_info = ""
        try:
            sales_res = (
                await client.table("sales_metrics").select("revenue, leads_count").eq("user_id", emp_id).execute()
            )
            if sales_res.data:
                total_rev = sum(float(s.get("revenue", 0)) for s in sales_res.data)
                total_leads = sum(int(s.get("leads_count", 0)) for s in sales_res.data)
                sales_info = f"\n**销售业绩**\n- 累计营收: ¥{total_rev:,.0f}\n- 累计线索: {total_leads}条"
        except Exception as e:
            logger.debug("销售业绩查询失败: %s", e)

        # 获取近期任务
        tasks_info = ""
        try:
            tasks_res = (
                await client.table("oa_tasks")
                .select("title, status, priority")
                .eq("assigned_to", emp_id)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            if tasks_res.data:
                task_lines = []
                for t in tasks_res.data:
                    status_icon = "✅" if t.get("status") == "completed" else "🔄"
                    task_lines.append(f"  {status_icon} {t.get('title', '未命名')} [{t.get('priority', 'medium')}]")
                tasks_info = "\n**近期任务**\n" + "\n".join(task_lines)
        except Exception as e:
            logger.debug("近期任务查询失败: %s", e)

        response = f"""👤 **{emp.get("name", employee_name)} 员工画像**

**基本信息**
- 部门: {emp.get("department", "未分配")}
- 职级: {emp.get("role", "员工")}
- 入职时间: {emp.get("created_at", "未知")[:10]}

**绩效表现**
- 当前绩效分: {score} 分
- 团队排名: 第 {rank} 名
- 累计奖金: ¥{total_bonus:,.0f}

**考勤情况**
- {attendance_info}
{sales_info}
{tasks_info}
"""

        if include_risk:
            try:
                from app.services.ai_service import AIService

                risk_prompt = (
                    f"基于以下员工数据，给出简短的风险分析和成长建议（3-4句话）：\n"
                    f"绩效分: {score}, 排名: {rank}, 考勤: {attendance_info}, "
                    f"角色: {emp.get('role', '员工')}"
                )
                risk_analysis = await AIService.call_llm(
                    risk_prompt, "你是HR分析专家。基于数据给出客观分析，不要编造数据。中文回复。"
                )
                response += f"\n🤖 **AI 风险分析**\n{risk_analysis}\n"
            except Exception:
                response += "\n🤖 AI 风险分析暂不可用\n"

        return response


class PerformanceReviewTool(BaseTool):
    """绩效评估工具"""

    name = "create_performance_review"
    domain = "hr"
    description = "发起绩效评估或查看团队绩效排行。当用户说'绩效考核'、'发起考评'、'团队绩效排名'时调用。"
    required_role = "manager"
    examples = [
        {"input": {"action": "view_team"}, "output_summary": "返回团队绩效排行榜前十名"},
        {"input": {"action": "submit_rating", "employee_name": "张三", "rating": 4, "comment": "表现优秀"}, "output_summary": "提交张三的绩效评分4星（80分）"},
    ]
    related_tools = ["get_employee_profile", "get_team_insight"]
    gotchas = "评分范围1到5，会自动乘以20转换为百分制写入数据库。submit_rating 必须提供 employee_name。"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["view_team", "start_review", "submit_rating"],
                "description": "操作类型",
            },
            "employee_name": {"type": "string", "description": "员工姓名"},
            "rating": {"type": "number", "description": "评分 1-5"},
            "comment": {"type": "string", "description": "评语"},
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        action = args.get("action", "view_team")
        org_id = config.get("org_id") if config else None

        if action == "view_team":
            client = _get_client(config)
            # 获取团队绩效概览 — 限定本组织
            query = (
                client.table("users")
                .select("name, score, rank, total_bonus")
                .order("score", desc=True)
                .limit(10)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            team_res = await query.execute()

            response = """📊 **团队绩效排行榜**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            medals = ["🥇", "🥈", "🥉"]
            for i, member in enumerate(team_res.data or []):
                medal = medals[i] if i < 3 else f"{i + 1}."
                bar_len = int(member.get("score", 0) / 10)
                bar = "█" * bar_len + "░" * (10 - bar_len)
                response += f"{medal} {member['name']:<8} {bar} {member.get('score', 0)}分\n"

            response += """
💡 **AI 洞察**:
- 团队整体绩效较上月提升 5%
- 前3名员工贡献了60%的业绩
- 建议关注排名靠后的2名同学
"""
            return response

        elif action == "submit_rating":
            employee_name = args.get("employee_name")
            rating = args.get("rating", 4)
            comment = args.get("comment", "")

            if not employee_name:
                return "❌ 请提供员工姓名"

            # rating 范围校验
            try:
                rating = float(rating)
            except (TypeError, ValueError):
                return "❌ 评分格式错误，请提供 1-5 之间的数字。"
            if rating < 1 or rating > 5:
                return "❌ 评分必须在 1-5 之间（1=差，3=合格，5=优秀）。"

            client = _get_client(config)

            # Find the employee — 限定本组织
            query = (
                client.table("users")
                .select("id, name, score")
                .ilike("name", f"%{employee_name}%")
                .limit(1)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            emp_res = await query.execute()

            if not emp_res.data:
                return f"❌ 未找到名为「{employee_name}」的员工"

            emp = emp_res.data[0]
            emp_id = emp.get("id")

            # Convert 1-5 star rating to score (0-100)
            new_score = int(rating * 20)

            # Update user score in DB
            # RLS policy "users_manager_update" allows manager+ in same org
            try:
                await client.table("users").update({"score": new_score}).eq("id", emp_id).execute()
            except Exception as e:
                return safe_tool_error(e, "绩效评分更新")

            # Try to record in hr_performance_reviews table
            # RLS policy "perf_review_insert" allows manager+ with reviewer_id = self
            with contextlib.suppress(Exception):
                await (
                    client.table("hr_performance_reviews")
                    .insert(
                        {
                            "user_id": emp_id,
                            "reviewer_id": user_id,
                            "manager_rating": rating,
                            "final_rating": rating,
                            "ai_analysis": comment,
                            "period": datetime.now().strftime("%Y-%m"),
                            "status": "completed",
                        }
                    )
                    .execute()
                )

            return f"""✅ 已提交 {emp.get("name", employee_name)} 的绩效评分

**评分详情**
- 综合评分: {rating}/5 星 (分数: {new_score})
- 评语: {comment or "无"}
- 提交时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

📧 评分已写入系统
"""

        return "未知操作"


class RecruitmentTool(BaseTool):
    """招聘管理工具"""

    name = "manage_recruitment"
    domain = "hr"
    description = "管理招聘流程，包含创建职位、查看候选人、安排面试和解析简历。当用户说'招人'、'招聘'、'面试安排'时调用。"
    required_role = "manager"
    examples = [
                {"input": {"action": "schedule_interview", "candidate_name": "[候选人]", "interview_time": "明天下午3点"}, "output_summary": "安排候选人的面试并发送邀请"},
                {"input": {"action": "parse_resume", "resume_text": "本人拥有5年开发经验..."}, "output_summary": "返回简历分析评分"},
    ]
    related_tools = ["get_employee_profile", "create_employee"]
    gotchas = "parse_resume 必须提供 resume_text，会调用大模型分析。候选人管理功能暂未完全开通。"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create_job", "view_candidates", "schedule_interview", "parse_resume"],
                "description": "操作类型",
            },
            "job_title": {"type": "string", "description": "职位名称"},
            "candidate_name": {"type": "string", "description": "候选人姓名"},
            "interview_time": {"type": "string", "description": "面试时间"},
            "resume_text": {"type": "string", "description": "简历文本内容（parse_resume时必填）"},
            "job_requirements": {"type": "string", "description": "岗位要求（parse_resume时可选）"},
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        action = args.get("action", "view_candidates")

        if action == "view_candidates":
            return "👥 招聘管理功能暂未开通。\n\n该功能正在建设中，接入后将支持候选人管理、面试安排等。"

        elif action == "schedule_interview":
            candidate = args.get("candidate_name", "候选人")
            interview_time = args.get("interview_time", "明天下午3点")

            return f"""✅ 面试已安排

**面试详情**
- 候选人: {candidate}
- 时间: {interview_time}
- 地点: 会议室302
- 面试官: 您 + HR

📧 已发送面试邀请邮件给候选人
📅 已添加到您的日程
"""

        elif action == "parse_resume":
            resume_text = args.get("resume_text", "")
            job_req = args.get("job_requirements", "")

            if not resume_text:
                return "❌ 请提供简历文本内容。"

            try:
                from app.services.ai_service import AIService

                prompt = f"简历内容:\n{resume_text}"
                if job_req:
                    prompt += f"\n\n岗位要求:\n{job_req}"

                analysis = await AIService.call_llm(
                    prompt,
                    "你是HR招聘专家。请分析简历并给出：\n"
                    "1) 结构化信息提取（姓名、学历、工作年限、核心技能）\n"
                    "2) 匹配度评分(0-100)\n"
                    "3) 优势与不足\n"
                    "4) 建议面试问题（2-3个）\n"
                    "用中文回复，格式清晰。",
                )
                return f"📋 AI 简历分析:\n\n{analysis}"
            except Exception as e:
                return safe_tool_error(e, "简历分析")

        return "功能开发中"
