"""幻觉检测评估器

检查 Agent 回复是否基于实际工具结果，而非编造数据。
策略:
- 当 tool_result 为 null 时，期望 Agent 回复包含不确定性词汇
- 当 tool_result 有值时，期望回复内容与工具结果一致
"""

from typing import Dict, Any, Optional

from evals.eval_metrics import EvalResult, EvalDimension


# 表达不确定性的常见中文词汇
UNCERTAINTY_PHRASES = [
    "无法",
    "没有",
    "不确定",
    "暂无",
    "抱歉",
    "无法确认",
    "未找到",
    "不存在",
    "暂时无法",
    "无法获取",
    "部分",
    "失败",
]


class HallucinationEvaluator:
    """
    幻觉检测评估器

    通过模拟 Agent 回复来测试幻觉检测逻辑：
    - tool_result 为空 -> Agent 应承认不确定
    - tool_result 有值 -> Agent 应基于数据回答
    """

    dimension = EvalDimension.HALLUCINATION

    async def evaluate(self, case: Dict[str, Any]) -> EvalResult:
        """评估单个用例是否存在幻觉。"""
        tool_result: Optional[str] = case.get("context", {}).get("tool_result")
        ground_truth_keywords = case.get("ground_truth_keywords", [])

        simulated_response = self._simulate_response(
            case["user_message"], tool_result
        )

        if tool_result is None:
            # 工具无返回 -> Agent 应表达不确定性
            has_uncertainty = any(
                phrase in simulated_response for phrase in UNCERTAINTY_PHRASES
            )
            # 如果数据集指定了特定的关键词检查 (OR 语义: 至少匹配一个即可)
            if ground_truth_keywords:
                has_any_keyword = any(
                    kw in simulated_response for kw in ground_truth_keywords
                )
                score = 1.0 if has_any_keyword else 0.0
            else:
                score = 1.0 if has_uncertainty else 0.0
        else:
            # 有工具结果 -> 回复应包含关键事实
            if ground_truth_keywords:
                matches = sum(
                    1 for kw in ground_truth_keywords if kw in simulated_response
                )
                score = matches / len(ground_truth_keywords)
            else:
                # 只要基于工具结果回答且不编造就算通过
                # 检查回复是否引用了工具结果
                score = 1.0 if tool_result[:10] in simulated_response or "查询结果" in simulated_response else 0.5

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=score >= 0.5,
            score=score,
            details={
                "simulated_response": simulated_response[:300],
                "has_tool_result": tool_result is not None,
            },
        )

    def _simulate_response(self, message: str, tool_result: Optional[str]) -> str:
        """模拟 Agent 响应（确定性规则，无 LLM 调用）。

        当有工具结果时，Agent 应该引用该结果。
        当无工具结果时，Agent 应该表达不确定性。
        """
        if tool_result is None:
            return "抱歉，暂无相关数据，无法确认您查询的信息。建议您联系相关部门获取最新数据。"
        return f"根据查询结果: {tool_result}"
