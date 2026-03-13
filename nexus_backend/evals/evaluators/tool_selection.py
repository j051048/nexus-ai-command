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
    "approve_request": ["批准", "同意", "通过审批", "批准这个"],
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
    "send_notification": ["通知.*人", "通知小", "提醒.*人", "发消息给"],
    # HR 人力资源
    "query_attendance": ["考勤", "出勤", "打卡", "迟到", "早退"],
    "query_team_attendance": ["团队考勤", "团队出勤", "团队.*迟到"],
    "get_employee_profile": ["员工画像", "员工档案", "人才画像", "表现怎么样", "能力如何"],
    "create_performance_review": ["绩效评估", "绩效考核", "发起考评"],
    "manage_recruitment": ["招聘", "候选人", "面试"],
    # 运营/分析
    "get_performance_report": ["绩效报告", "绩效数据", "业绩.*怎么样"],
    "get_company_stats": ["公司统计", "员工总数", "公司.*多少人"],
    "query_knowledge_base": ["知识库", "查文档", "公司.*制度", "技术参数", "产品.*参数"],
    "award_badge": ["颁发徽章", "荣誉", "奖励徽章"],
    # 项目
    "get_projects": ["项目列表", "所有项目"],
    "create_project": ["新建项目", "创建项目", "立项"],
    "create_project_event": ["项目事件", "项目进度", "记录.*项目"],
    # 领导专属
    "smart_approve": ["智能审批", "批量审批", "一键审批", "以下的.*都批", "全部通过"],
    "get_daily_briefing": ["今天.*事", "简报", "汇报", "日报"],
    "get_business_dashboard": ["经营", "业绩", "利润", "营收", "收入"],
    "get_team_insight": ["团队洞察", "团队分析", "人员状态"],
    "publish_announcement": ["公告", "通知全员", "发布公告", "全员.*通知"],
    # CRM 客户
    "get_customers": ["客户.*有哪些", "客户列表"],
    "get_customer_detail": ["客户.*详细", "客户.*信息"],
    "add_follow_up": ["跟进记录", "记一下.*拜访", "记录跟进"],
    "get_follow_ups": ["跟进情况", "跟进记录.*查"],
    "update_customer_stage": ["更新.*阶段", "推进.*阶段", "更新进度"],
    "get_sales_pipeline": ["销售漏斗", "销售管线"],
    # 资产/库存
    "list_inventory": ["库存", "还有多少"],
    "inventory_in": ["入库", "到货.*入库"],
    "inventory_out": ["出库"],
    "transfer_asset": ["资产转移", "转给"],
    "list_assets": ["资产列表", "资产.*有哪些"],
    "asset_statistics": ["资产统计"],
    # 工单
    "create_work_order": ["报修", "维修", "创建工单"],
    "list_work_orders": ["工单列表", "所有工单"],
    "work_order_statistics": ["工单.*统计", "工单.*情况"],
    # 合同
    "get_expiring_contracts": ["到期.*合同", "合同.*到期"],
    "analyze_contract": ["合同.*风险", "条款.*风险", "审合同"],
    "get_contracts": ["合同列表", "所有合同"],
    # 销售/竞品
    "analyze_tender_document": ["标书", "投标", "招标文件"],
    "get_battlecard": ["竞品", "竞争对手", "打击卡"],
    "search_bidding_projects": ["搜.*招标", "招投标.*搜"],
    # 定时任务
    "create_scheduled_task": ["定时", "提醒我", "每天.*提醒", "每周.*提醒", "每月.*提醒", "定期"],
    "list_scheduled_tasks": ["定时任务", "有哪些.*提醒", "提醒列表", "查看.*定时"],
    "delete_scheduled_task": ["取消.*提醒", "删除.*定时", "取消.*定时", "不用.*提醒"],
    # 联网搜索
    "web_search": ["搜索", "搜一下", "最新.*新闻", "行业.*政策"],
    # 追问
    "ask_user": ["帮我办个事", "那个.*怎么样了", "帮我查一下$"],
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
