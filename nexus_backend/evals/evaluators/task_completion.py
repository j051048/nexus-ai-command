"""任务完成度评估器

评估多步骤复杂任务的完成情况:
- 步骤覆盖率: 预期步骤中有多少被执行
- 成功标准: 最终结果是否满足业务条件
"""

from typing import Any

from evals.eval_metrics import EvalDimension, EvalResult

# 步骤关键词 -> 工具/动作映射
STEP_KEYWORD_MAP: dict[str, list[str]] = {
    # 工具步骤
    "get_business_dashboard": ["经营", "业绩", "营收", "利润"],
    "query_leave_status": ["假期", "年假", "余额"],
    "create_leave_request": ["请假", "休假"],
    "create_expense_claim": ["报销", "费用"],
    "query_expense_status": ["报销状态", "到账"],
    "query_team_attendance": ["团队", "考勤", "出勤"],
    "assign_task": ["安排", "任务", "通知", "分配"],
    "get_pending_approvals": ["待审批", "审批列表"],
    "approve_request": ["批准", "通过"],
    "get_employee_info": ["员工信息", "了解"],
    "get_employee_profile": ["员工画像", "全面了解", "画像"],
    "query_attendance": ["考勤", "出勤"],
    "book_meeting": ["会议", "预订", "会议室"],
    "get_daily_briefing": ["简报", "汇报", "今天.*事"],
    "smart_approve": ["智能审批", "批量", "一键"],
    "get_projects": ["项目", "项目列表"],
    "create_project_event": ["事件", "进度", "记录"],
    "manage_recruitment": ["招聘", "候选人"],
    # 抽象步骤
    "analyze_result": ["分析", "找出", "对比"],
    "generate_recommendation": ["建议", "改进", "优化"],
    "identify_issues": ["异常", "问题", "发现"],
    "schedule_interview": ["面试", "安排面试"],
}

# 成功标准检查映射
CRITERIA_KEYWORD_MAP: dict[str, list[str]] = {
    "mentions_data": ["数据", "经营", "业绩", "指标"],
    "provides_recommendation": ["建议", "改进", "优化", "提升"],
    "mentions_top_performer": ["最好", "第一", "最优", "表现"],
    "checks_balance": ["余额", "剩余", "还有"],
    "submits_request": ["申请", "提交", "请假"],
    "creates_claim": ["报销", "费用", "创建"],
    "checks_status": ["状态", "到账", "进度"],
    "reviews_attendance": ["考勤", "出勤", "团队"],
    "handles_exception": ["异常", "跟进", "处理"],
    "lists_approvals": ["待审批", "列表", "审批"],
    "executes_approval": ["批准", "通过", "处理"],
    "provides_profile": ["信息", "画像", "档案"],
    "includes_performance": ["绩效", "考勤", "表现"],
    "books_room": ["会议室", "预订", "预约"],
    "notifies_team": ["通知", "安排", "准备"],
    "provides_briefing": ["简报", "今天", "事项"],
    "processes_approvals": ["审批", "处理", "批准"],
    "finds_project": ["项目", "找到"],
    "creates_event": ["事件", "记录", "进度"],
    "lists_candidates": ["候选人", "岗位", "招聘"],
    "arranges_interview": ["面试", "安排"],
}


class TaskCompletionEvaluator:
    """
    评估多步任务是否完成。

    分两个维度打分:
    1. 步骤覆盖率: 根据用户消息关键词判断哪些步骤可以被触发
    2. 成功标准满足度: 检查用户消息是否覆盖了成功标准对应的语义
    """

    dimension = EvalDimension.TASK_COMPLETION

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        """评估多步任务的完成度。"""
        user_message: str = case["user_message"]
        expected_steps: list[str] = case.get("expected_steps", [])
        success_criteria: list[str] = case.get("success_criteria", [])

        # 模拟执行: 检查哪些步骤可以被识别
        executed_steps = self._simulate_execution(user_message, expected_steps)
        step_score = len(executed_steps) / len(expected_steps) if expected_steps else 1.0

        # 检查成功标准
        criteria_met = self._check_criteria(user_message, success_criteria)
        criteria_score = criteria_met / len(success_criteria) if success_criteria else 1.0

        # 综合得分 (步骤权重 60%, 标准权重 40%)
        score = step_score * 0.6 + criteria_score * 0.4

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=score >= 0.6,
            score=score,
            details={
                "expected_steps": expected_steps,
                "executed_steps": executed_steps,
                "step_score": round(step_score, 3),
                "criteria_met": criteria_met,
                "criteria_total": len(success_criteria),
                "criteria_score": round(criteria_score, 3),
            },
        )

    def _simulate_execution(self, message: str, expected_steps: list[str]) -> list[str]:
        """模拟步骤执行: 基于用户消息关键词判断哪些步骤会被触发。"""
        import re

        executed: list[str] = []
        for step in expected_steps:
            keywords = STEP_KEYWORD_MAP.get(step, [])
            if keywords:
                for kw in keywords:
                    if re.search(kw, message):
                        executed.append(step)
                        break
            else:
                # 对于未映射的步骤，尝试步骤名本身作为关键词
                step_readable = step.replace("_", "")
                if step_readable in message:
                    executed.append(step)
        return executed

    def _check_criteria(self, message: str, criteria: list[str]) -> int:
        """检查用户消息中有多少成功标准被覆盖。"""
        import re

        met_count = 0
        for criterion in criteria:
            keywords = CRITERIA_KEYWORD_MAP.get(criterion, [])
            if keywords:
                for kw in keywords:
                    if re.search(kw, message):
                        met_count += 1
                        break
        return met_count
