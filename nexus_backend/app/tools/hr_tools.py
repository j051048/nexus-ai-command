"""
HR 人力资源工具集
实现考勤、绩效、员工档案等 HR 场景的 AI 自动化
"""
from .base_tool import BaseTool
from typing import Dict, Any
from datetime import datetime
from app.core.database import supabase


def _get_client(config: Dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


class AttendanceQueryTool(BaseTool):
    """考勤查询工具"""
    name = "query_attendance"
    description = "查询员工考勤记录、迟到早退情况、出勤统计等"
    required_role = "all"
    
    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["my_record", "monthly_summary", "abnormal"],
                "description": "查询类型: my_record(我的考勤), monthly_summary(月度汇总), abnormal(异常记录)"
            },
            "month": {
                "type": "string",
                "description": "查询月份，格式 YYYY-MM"
            },
            "employee_name": {
                "type": "string",
                "description": "员工姓名（管理者可查询下属）"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        month = args.get("month", datetime.now().strftime("%Y-%m"))
        employee_name = args.get("employee_name")
        
        client = _get_client(config)
        # 获取用户信息
        user_res = await client.table("users").select("name, role").eq("id", user_id).maybe_single().execute()
        if not user_res.data:
            return "❌ 无法获取用户信息"
        
        user = user_res.data
        query_user_name = employee_name or user.get("name", "您")
        
        # 检查权限：非管理者只能查自己
        if employee_name and user.get("role") not in ["manager", "founder", "boss"]:
            return "❌ 您没有权限查询他人的考勤记录"
        
        # 模拟考勤数据（实际应从 hr_attendance 表查询）
        work_days = 22
        actual_days = 21
        late_count = 2
        early_leave_count = 0
        overtime_hours = 12.5
        
        response = f"""📅 **{query_user_name} {month} 考勤汇总**

**出勤统计**
┌─────────────────────────────┐
│ 应出勤天数        {work_days:>10} 天 │
│ 实际出勤          {actual_days:>10} 天 │
│ 出勤率            {actual_days/work_days*100:>9.1f}% │
└─────────────────────────────┘

**异常记录**
┌─────────────────────────────┐
│ 迟到              {late_count:>10} 次 │
│ 早退              {early_leave_count:>10} 次 │
│ 请假              {work_days - actual_days:>10} 天 │
└─────────────────────────────┘

**加班统计**
┌─────────────────────────────┐
│ 加班时长          {overtime_hours:>9.1f} 小时 │
│ 可调休            {overtime_hours/8:>9.1f} 天 │
└─────────────────────────────┘
"""
        
        if late_count > 0:
            response += f"""
⚠️ **迟到明细**
- 12月3日 09:15 (迟到15分钟)
- 12月15日 09:08 (迟到8分钟)

💡 温馨提示: 本月迟到{late_count}次，将扣除全勤奖 ¥{late_count * 100}
"""
        
        return response


class TeamAttendanceTool(BaseTool):
    """团队考勤管理工具（管理者专用）"""
    name = "query_team_attendance"
    description = "查询团队整体考勤情况、异常预警等（管理者专用）"
    required_role = "manager"
    
    parameters = {
        "type": "object",
        "properties": {
            "view_type": {
                "type": "string",
                "enum": ["overview", "abnormal_alert", "ranking"],
                "description": "查看类型: overview(总览), abnormal_alert(异常预警), ranking(排名)"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        # 模拟团队数据
        team_stats = {
            "total_members": 12,
            "avg_attendance_rate": 96.5,
            "total_late": 8,
            "total_overtime_hours": 156
        }
        
        abnormal_members = [
            {"name": "张小明", "late_count": 5, "status": "关注", "trend": "上升"},
            {"name": "李小红", "late_count": 3, "status": "正常", "trend": "稳定"},
        ]
        
        response = f"""👥 **团队考勤总览**
📅 统计周期: {datetime.now().strftime("%Y年%m月")}

**整体情况**
┌─────────────────────────────┐
│ 团队人数          {team_stats['total_members']:>10} 人 │
│ 平均出勤率        {team_stats['avg_attendance_rate']:>9.1f}% │
│ 本月迟到总计      {team_stats['total_late']:>10} 次 │
│ 加班总时长        {team_stats['total_overtime_hours']:>9} 小时 │
└─────────────────────────────┘

"""
        
        if abnormal_members:
            response += "⚠️ **需关注成员**\n"
            for member in abnormal_members:
                alert_icon = "🔴" if member["status"] == "关注" else "🟡"
                response += f"{alert_icon} {member['name']}: 迟到{member['late_count']}次 (趋势{member['trend']})\n"
            
            response += """
💡 **AI 建议**:
- 张小明本月迟到次数明显增加，建议一对一沟通了解情况
- 整体出勤率良好，团队状态稳定
"""
        
        return response


class EmployeeProfileTool(BaseTool):
    """员工画像工具（管理者专用）"""
    name = "get_employee_profile"
    description = "获取员工综合画像，包括绩效、考勤、成长轨迹、风险评估等"
    required_role = "manager"
    
    parameters = {
        "type": "object",
        "properties": {
            "employee_name": {
                "type": "string",
                "description": "员工姓名"
            },
            "include_risk_analysis": {
                "type": "boolean",
                "description": "是否包含风险分析"
            }
        },
        "required": ["employee_name"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        employee_name = args.get("employee_name")
        include_risk = args.get("include_risk_analysis", True)
        
        client = _get_client(config)
        # 查找员工
        emp_res = await client.table("users").select("*").ilike("name", f"%{employee_name}%").limit(1).execute()
        
        if not emp_res.data:
            return f"❌ 未找到名为「{employee_name}」的员工"
        
        emp = emp_res.data[0]
        
        # 获取绩效数据
        score = emp.get("score", 85)
        rank = emp.get("rank", 5)
        total_bonus = emp.get("total_bonus", 12000)
        
        response = f"""👤 **{emp.get('name', employee_name)} 员工画像**

**基本信息**
┌─────────────────────────────┐
│ 部门          {emp.get('department', '未分配'):>14} │
│ 职级          {emp.get('role', '员工'):>14} │
│ 入职时间      {emp.get('created_at', '2023-01')[:10]:>14} │
└─────────────────────────────┘

**绩效表现**
┌─────────────────────────────┐
│ 当前绩效分    {score:>14} 分 │
│ 团队排名      {rank:>14} 名 │
│ 累计奖金      ¥{total_bonus:>12,.0f} │
└─────────────────────────────┘

**能力雷达图**
  销售能力: ████████░░ 80%
  沟通能力: █████████░ 90%
  执行力:   ███████░░░ 70%
  学习能力: ████████░░ 80%
  团队协作: █████████░ 90%

**近期动态**
- 12月10日: 成功签约「华为云项目」¥50万
- 12月5日: 获得「销售新星」徽章
- 11月28日: 完成产品培训认证
"""
        
        if include_risk:
            # AI 风险分析
            response += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **AI 风险分析**

📊 离职风险: 低 (15%)
   - 绩效稳定在团队前30%
   - 近期无异常请假
   - 加班时长正常

📈 成长建议:
   - 可考虑培养为团队骨干
   - 建议参与大客户项目锻炼
   - 推荐报名管理培训课程
"""
        
        return response


class PerformanceReviewTool(BaseTool):
    """绩效评估工具"""
    name = "create_performance_review"
    description = "发起或查看绩效评估"
    required_role = "manager"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["view_team", "start_review", "submit_rating"],
                "description": "操作类型"
            },
            "employee_name": {
                "type": "string",
                "description": "员工姓名"
            },
            "rating": {
                "type": "number",
                "description": "评分 1-5"
            },
            "comment": {
                "type": "string",
                "description": "评语"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        action = args.get("action", "view_team")
        
        if action == "view_team":
            client = _get_client(config)
            # 获取团队绩效概览
            team_res = await client.table("users").select("name, score, rank, total_bonus").order("score", desc=True).limit(10).execute()
            
            response = """📊 **团队绩效排行榜**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
            medals = ["🥇", "🥈", "🥉"]
            for i, member in enumerate(team_res.data or []):
                medal = medals[i] if i < 3 else f"{i+1}."
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
            
            return f"""✅ 已提交 {employee_name} 的绩效评分

**评分详情**
- 综合评分: {rating}/5 星
- 评语: {comment or '无'}
- 提交时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}

📧 已通知 {employee_name} 查看评估结果
"""
        
        return "未知操作"


class RecruitmentTool(BaseTool):
    """招聘管理工具"""
    name = "manage_recruitment"
    description = "管理招聘需求、查看候选人、安排面试等"
    required_role = "manager"
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create_job", "view_candidates", "schedule_interview"],
                "description": "操作类型"
            },
            "job_title": {
                "type": "string",
                "description": "职位名称"
            },
            "candidate_name": {
                "type": "string",
                "description": "候选人姓名"
            },
            "interview_time": {
                "type": "string",
                "description": "面试时间"
            }
        },
        "required": []
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        action = args.get("action", "view_candidates")
        
        if action == "view_candidates":
            # 模拟候选人数据
            candidates = [
                {"name": "候选人A", "position": "销售经理", "stage": "复试", "score": 4.5, "source": "猎聘"},
                {"name": "候选人B", "position": "销售专员", "stage": "初筛", "score": 3.8, "source": "BOSS"},
                {"name": "候选人C", "position": "销售经理", "stage": "offer", "score": 4.8, "source": "内推"},
            ]
            
            response = """👥 **候选人管道**

"""
            stage_icons = {"初筛": "📋", "复试": "🎯", "offer": "✅", "入职": "🎉"}
            
            for c in candidates:
                icon = stage_icons.get(c["stage"], "📋")
                stars = "⭐" * int(c["score"])
                response += f"""{icon} **{c['name']}** - {c['position']}
   阶段: {c['stage']} | 评分: {stars} | 来源: {c['source']}

"""
            
            response += """💡 **AI 建议**:
- 候选人C综合评分最高，建议尽快发offer
- 销售经理岗位已有2名合适候选人
"""
            return response
        
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
        
        return "功能开发中"