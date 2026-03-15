"""
Phase 4 战略分析工具集
4.1 多维度数据智能归因解读
4.2 复杂战略指令推演大脑（What-if 沙盘模拟）
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.services.ai_service import AIService

from .base_tool import BaseTool
from ._shared import _get_client

logger = logging.getLogger(__name__)


class DataAttributionTool(BaseTool):
    """4.1 多维度数据智能归因解读工具"""

    name = "analyze_data_attribution"
    description = (
        "对Dashboard数据变化进行智能归因分析，解释为什么指标上涨或下跌。"
        "当用户说'为什么销售额下降了'、'分析一下业绩变化原因'、'解读数据'时调用。"
    )
    required_role = "manager"

    parameters = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["revenue", "leads", "conversion", "cost", "headcount", "all"],
                "default": "all",
                "description": "要归因分析的指标类型。revenue=营收, leads=线索, conversion=转化率, cost=成本, headcount=人力, all=全部",
            },
            "period": {
                "type": "string",
                "enum": ["week", "month", "quarter"],
                "default": "month",
                "description": "对比周期（与上一同期对比）。week=本周vs上周, month=本月vs上月, quarter=本季vs上季",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        metric = args.get("metric", "all")  # noqa: F841 — reserved for per-metric filtering
        period = args.get("period", "month")
        client = _get_client(config)

        now = datetime.now()
        data_context = []

        # 计算当前周期和上一周期的日期范围
        if period == "week":
            current_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
            prev_start = (now - timedelta(days=now.weekday() + 7)).strftime("%Y-%m-%d")
            period_name = "本周"
        elif period == "quarter":
            q = (now.month - 1) // 3
            current_start = f"{now.year}-{q * 3 + 1:02d}-01"
            prev_start = f"{now.year - 1}-10-01" if q == 0 else f"{now.year}-{(q - 1) * 3 + 1:02d}-01"
            period_name = "本季度"
        else:
            current_start = now.strftime("%Y-%m-01")
            prev_month = now.month - 1 if now.month > 1 else 12
            prev_year = now.year if now.month > 1 else now.year - 1
            prev_start = f"{prev_year}-{prev_month:02d}-01"
            period_name = "本月"

        # 收集各维度数据
        try:
            # 销售指标
            current_metrics = await client.table("sales_metrics").select("*").gte("date", current_start).execute()
            prev_metrics = (
                await client.table("sales_metrics")
                .select("*")
                .gte("date", prev_start)
                .lt("date", current_start)
                .execute()
            )

            cur_data = current_metrics.data or []
            prev_data = prev_metrics.data or []

            cur_revenue = sum(float(m.get("revenue", 0)) for m in cur_data)
            prev_revenue = sum(float(m.get("revenue", 0)) for m in prev_data)
            cur_leads = sum(int(m.get("leads_count", 0)) for m in cur_data)
            prev_leads = sum(int(m.get("leads_count", 0)) for m in prev_data)

            data_context.append(
                f"营收: {period_name} ¥{cur_revenue:,.0f} vs 上期 ¥{prev_revenue:,.0f} "
                f"(变化: {((cur_revenue - prev_revenue) / max(prev_revenue, 1)) * 100:+.1f}%)"
            )
            data_context.append(f"线索: {period_name} {cur_leads} vs 上期 {prev_leads}")
        except Exception as e:
            data_context.append(f"销售指标查询: {str(e)}")

        # 商机阶段分布
        try:
            leads_res = await client.table("sales_leads").select("status", count="exact").execute()
            if leads_res.data:
                status_counts = {}
                for lead in leads_res.data:
                    s = lead.get("status", "unknown")
                    status_counts[s] = status_counts.get(s, 0) + 1
                data_context.append(f"商机分布: {status_counts}")
        except Exception as e:
            logger.debug("商机数据查询失败: %s", e)

        # HR 数据
        try:
            users_res = await client.table("users").select("id, role", count="exact").execute()
            headcount = users_res.count or 0
            data_context.append(f"当前人数: {headcount}")

            # 考勤异常
            week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            att_res = (
                await client.table("hr_attendance")
                .select("status", count="exact")
                .gte("date", week_ago)
                .in_("status", ["late", "absent"])
                .execute()
            )
            anomaly_count = att_res.count or 0
            data_context.append(f"近7天考勤异常: {anomaly_count}次")
        except Exception as e:
            logger.debug("HR数据查询失败: %s", e)

        # 合同数据
        try:
            contracts_res = await client.table("contracts").select("status, amount").execute()
            if contracts_res.data:
                active = [c for c in contracts_res.data if c.get("status") == "active"]
                total_amount = sum(float(c.get("amount", 0)) for c in active)
                data_context.append(f"活跃合同: {len(active)}份, 总金额 ¥{total_amount:,.0f}")
        except Exception as e:
            logger.debug("合同数据查询失败: %s", e)

        # 请求审批数据
        try:
            approvals_res = (
                await client.table("approval_requests")
                .select("status, amount")
                .gte("created_at", current_start)
                .execute()
            )
            if approvals_res.data:
                pending = len([a for a in approvals_res.data if a.get("status") == "pending"])
                total_spend = sum(
                    float(a.get("amount", 0)) for a in approvals_res.data if a.get("status") == "approved"
                )
                data_context.append(f"审批: 待处理{pending}笔, 本期已批准支出 ¥{total_spend:,.0f}")
        except Exception as e:
            logger.debug("审批数据查询失败: %s", e)

        if not data_context:
            return "📊 暂无足够数据进行归因分析。请确保相关业务数据已录入系统。"

        prompt = (
            f"请对以下{period_name}经营数据进行多维度归因分析:\n\n"
            + "\n".join(data_context)
            + "\n\n请从以下维度分析数据变化的原因:\n"
            "1. 销售维度: 商机转化率、客户获取渠道效果\n"
            "2. 人力维度: 团队产能、考勤影响\n"
            "3. 财务维度: 成本变化、审批支出趋势\n"
            "4. 风险预警: 需要关注的异常指标\n"
            "5. 建议行动: 基于归因分析的具体改进建议"
        )

        system = (
            "你是企业经营数据分析专家。基于内部数据进行深度归因分析，"
            "不仅说明'是什么'，更要解释'为什么'和'怎么办'。"
            "用数据说话，给出可操作的具体建议。中文回复，格式清晰。"
        )

        try:
            analysis = await AIService.call_llm(prompt, system)
            return f"📊 {period_name}数据智能归因分析:\n\n{analysis}"
        except Exception as e:
            return f"📊 归因分析失败: {str(e)}"


class StrategySimulationTool(BaseTool):
    """4.2 复杂战略指令推演大脑（What-if 沙盘模拟）"""

    name = "strategy_simulation"
    description = (
        "执行战略沙盘推演，回答'如果...会怎样'的假设性问题。"
        "例如：'进军华南市场需要多少预算'、'裁掉产品线X对现金流的影响'、"
        "'如果提价10%对客户流失的影响'。当用户提出战略假设时调用。"
    )
    required_role = "boss"

    parameters = {
        "type": "object",
        "properties": {
            "scenario": {
                "type": "string",
                "minLength": 5,
                "maxLength": 500,
                "description": "要推演的战略假设场景描述，例如：进军华南市场需要多少预算、如果提价10%对客户流失的影响、裁掉产品线X对现金流的影响、招聘10名销售对季度营收的提升",
            },
            "focus": {
                "type": "string",
                "enum": ["finance", "hr", "sales", "market", "comprehensive"],
                "default": "comprehensive",
                "description": "推演重点维度。finance=财务, hr=人力, sales=销售, market=市场, comprehensive=综合全面分析",
            },
        },
        "required": ["scenario"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        scenario = args.get("scenario", "").strip()
        focus = args.get("focus", "comprehensive")
        client = _get_client(config)

        if not scenario or len(scenario) < 5:
            return "❌ 请描述您要推演的战略假设场景（至少5个字），例如：'如果提价10%对客户流失的影响'。"

        if len(scenario) > 500:
            return "❌ 场景描述过长，请精简到500字以内。"

        # 收集企业当前基线数据作为推演基础
        baseline_data = []

        # 并行执行所有基线数据查询（消除串行等待）
        import asyncio

        async def _fetch_metrics():
            try:
                res = (
                    await client.table("sales_metrics")
                    .select("revenue, leads_count, win_rate")
                    .order("date", desc=True)
                    .limit(30)
                    .execute()
                )
                if res.data:
                    recent = res.data
                    total_revenue = sum(float(m.get("revenue", 0)) for m in recent)
                    avg_leads = sum(int(m.get("leads_count", 0)) for m in recent) / max(len(recent), 1)
                    avg_conv = sum(float(m.get("win_rate", 0)) for m in recent) / max(len(recent), 1)
                    return f"近期营收合计: ¥{total_revenue:,.0f}, 日均线索: {avg_leads:.1f}, 平均转化率: {avg_conv:.1%}"
            except Exception as e:
                logger.debug("销售指标基线查询失败: %s", e)
            return None

        async def _fetch_headcount():
            try:
                res = await client.table("users").select("id, role", count="exact").execute()
                headcount = res.count or 0
                roles = {}
                for u in res.data or []:
                    r = u.get("role", "employee")
                    roles[r] = roles.get(r, 0) + 1
                return f"团队规模: {headcount}人, 结构: {roles}"
            except Exception as e:
                logger.debug("团队规模查询失败: %s", e)
                return None

        async def _fetch_salary():
            try:
                res = (
                    await client.table("hr_salary_records")
                    .select("base_salary, gross_salary")
                    .order("created_at", desc=True)
                    .limit(50)
                    .execute()
                )
                if res.data:
                    avg_salary = sum(float(s.get("gross_salary", 0)) for s in res.data) / max(len(res.data), 1)
                    return f"人均月薪: ¥{avg_salary:,.0f}"
            except Exception as e:
                logger.debug("薪资数据查询失败: %s", e)
                return None

        async def _fetch_contracts():
            try:
                res = await client.table("contracts").select("amount, status").limit(200).execute()
                if res.data:
                    active = [c for c in res.data if c.get("status") == "active"]
                    total = sum(float(c.get("amount", 0)) for c in active)
                    return f"活跃合同: {len(active)}份, 合同总额: ¥{total:,.0f}"
            except Exception as e:
                logger.debug("合同基线查询失败: %s", e)
                return None

        async def _fetch_leads():
            try:
                res = await client.table("sales_leads").select("status, estimated_value").limit(500).execute()
                if res.data:
                    pipeline = {}
                    for lead in res.data:
                        s = lead.get("status", "unknown")
                        pipeline[s] = pipeline.get(s, 0) + float(lead.get("estimated_value", 0))
                    return f"销售漏斗: {pipeline}"
            except Exception as e:
                logger.debug("销售漏斗查询失败: %s", e)
                return None

        async def _fetch_budget():
            try:
                res = (
                    await client.table("finance_budgets").select("name, total_amount, used_amount").limit(100).execute()
                )
                if res.data:
                    total_budget = sum(float(b.get("total_amount", 0)) for b in res.data)
                    total_used = sum(float(b.get("used_amount", 0)) for b in res.data)
                    return f"预算总额: ¥{total_budget:,.0f}, 已用: ¥{total_used:,.0f}"
            except Exception as e:
                logger.debug("预算数据查询失败: %s", e)
                return None

        results = await asyncio.gather(
            _fetch_metrics(),
            _fetch_headcount(),
            _fetch_salary(),
            _fetch_contracts(),
            _fetch_leads(),
            _fetch_budget(),
        )
        baseline_data = [r for r in results if r]

        focus_names = {
            "finance": "财务",
            "hr": "人力资源",
            "sales": "销售",
            "market": "市场",
            "comprehensive": "综合",
        }

        baseline_text = "\n".join(baseline_data) if baseline_data else "暂无详细基线数据"

        prompt = (
            f"## 战略沙盘推演请求\n\n"
            f"**假设场景**: {scenario}\n"
            f"**分析维度**: {focus_names.get(focus, '综合')}\n\n"
            f"## 企业当前基线数据\n{baseline_text}\n\n"
            f"## 请按以下框架进行推演分析:\n"
            f"1. **场景解读**: 明确假设的核心变量和边界条件\n"
            f"2. **财务影响**: 预估对营收、成本、现金流的量化影响\n"
            f"3. **人力影响**: 对人员编制、薪资成本、组织架构的影响\n"
            f"4. **销售影响**: 对销售漏斗、客户关系、市场份额的影响\n"
            f"5. **风险评估**: 识别关键风险因素及其发生概率\n"
            f"6. **实施路线图**: 如果执行该战略，建议的分阶段计划\n"
            f"7. **决策建议**: 综合建议（执行/观望/放弃）及理由"
        )

        system = (
            "你是企业战略模拟专家。基于企业真实经营数据进行严谨的假设推演分析。"
            "所有数据引用要基于提供的基线数据，不要编造数据。"
            "如果某方面数据不足，请明确标注为'基于行业平均估算'。"
            "给出的建议要具体、可操作，包含量化指标和时间节点。"
            "用中文回复，结构化呈现。"
        )

        try:
            simulation = await AIService.call_llm(prompt, system)
            return f"🎯 战略沙盘推演 — {scenario[:30]}...\n\n{simulation}"
        except Exception as e:
            return f"🎯 推演分析失败: {str(e)}"
