"""工具选择准确性评估器

不实际调用 LLM，而是通过关键词规则模拟 Agent 的工具路由逻辑。
关键词映射与 TOOL_REGISTRY 中注册的工具名精确对应。
"""

from typing import Any

from evals.eval_metrics import EvalDimension, EvalResult

# 工具名 -> 触发关键词映射表
# 名称与 app/tools/__init__.py TOOL_REGISTRY 中注册的实际工具名一致
TOOL_KEYWORD_MAP: dict[str, list[str]] = {
    # 审批类
    "submit_approval_on_behalf": ["提交审批", "申请审批", "发起审批"],
    "approve_request": ["批准", "同意", "通过审批"],
    "reject_request": ["驳回", "拒绝审批"],
    "get_pending_approvals": ["待审批", "待处理", "审批列表"],
    "get_employee_info": ["员工信息", "查员工"],
    "get_employee_approval_history": ["审批历史", "审批记录"],
    # 财务类
    "create_expense_claim": ["报销", "报个账", "费用报销"],
    "query_expense_status": ["报销状态", "报销进度", "到账"],
    "query_budget": ["预算", "预算余额"],
    "query_salary": ["工资", "薪资", "薪水", "扣税", "到手"],
    "recognize_invoice": ["发票", "识别发票", "发票OCR"],
    # OA 办公
    "create_leave_request": ["请假", "年假", "休假", "调休", "病假", "事假"],
    "query_leave_status": ["假期余额", "年假余额", "请假状态", "几天年假", "假期"],
    "book_meeting": ["会议室", "订会议", "预订", "预约会议"],
    "assign_task": ["安排任务", "分配任务", "让.*做", "安排.*完成"],
    "create_work_handover": ["交接", "工作交接"],
    # HR 人力资源
    "query_attendance": ["考勤", "出勤", "打卡", "迟到", "早退"],
    "query_team_attendance": ["团队考勤", "团队出勤", "团队.*迟到"],
    "get_employee_profile": ["员工画像", "员工档案", "人才画像"],
    "create_performance_review": ["绩效评估", "绩效考核"],
    "manage_recruitment": ["招聘", "候选人", "面试"],
    # 运营/分析
    "get_performance_report": ["绩效报告", "绩效数据"],
    "get_company_stats": ["公司统计", "员工总数"],
    "query_knowledge_base": ["知识库", "查文档"],
    "award_badge": ["颁发徽章", "荣誉", "奖励徽章"],
    # 项目
    "get_projects": ["项目列表", "所有项目"],
    "create_project": ["新建项目", "创建项目", "立项"],
    "create_project_event": ["项目事件", "项目进度", "记录.*项目"],
    # 领导专属
    "smart_approve": ["智能审批", "批量审批", "一键审批"],
    "get_daily_briefing": ["今天.*事", "简报", "汇报", "日报"],
    "get_business_dashboard": ["经营", "业绩", "利润", "营收", "收入"],
    "get_team_insight": ["团队洞察", "团队分析", "人员状态"],
    "publish_announcement": ["公告", "通知全员", "发布公告"],
    # 销售/竞品
    "analyze_tender_document": ["标书", "投标", "招标"],
    "get_battlecard": ["竞品", "竞争对手", "打击卡"],
}


class ToolSelectionEvaluator:
    """
    评估 Agent 是否为给定用户消息选择了正确的工具。

    策略: 基于关键词匹配的确定性预测，与预期工具列表做 Jaccard 相似度。
    这样可以在无 LLM API 的情况下运行。
    """

    dimension = EvalDimension.TOOL_SELECTION

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        """评估单个用例的工具选择准确性。"""
        user_message: str = case["user_message"]
        expected_tools: list[str] = case["expected_tools"]

        predicted_tools = self._predict_tools(user_message)

        # 计算 Jaccard 相似度
        if not expected_tools and not predicted_tools:
            # 都为空 = 正确不调用任何工具
            score = 1.0
        elif not expected_tools and predicted_tools:
            # 不应调用工具却预测了工具 = 误报
            score = 0.0
        elif expected_tools and not predicted_tools:
            # 应该调用工具却未预测到 = 漏报
            score = 0.0
        else:
            intersection = set(expected_tools) & set(predicted_tools)
            union = set(expected_tools) | set(predicted_tools)
            score = len(intersection) / len(union) if union else 0.0

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=score >= 0.5,
            score=score,
            details={
                "expected": expected_tools,
                "predicted": predicted_tools,
            },
        )

    def _predict_tools(self, message: str) -> list[str]:
        """基于关键词匹配预测应使用的工具。"""
        import re

        predicted: list[str] = []
        for tool_name, keywords in TOOL_KEYWORD_MAP.items():
            for kw in keywords:
                # 支持正则关键词（如 "让.*做"）
                if re.search(kw, message):
                    if tool_name not in predicted:
                        predicted.append(tool_name)
                    break

        return predicted
