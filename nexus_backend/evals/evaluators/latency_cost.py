"""延迟/成本评估器

模拟估算查询的延迟和成本，验证是否在可接受范围内。
不需要实际调用 LLM，基于规则模拟。
"""

from typing import Any

from evals.eval_metrics import EvalDimension, EvalResult

# 模拟参数
_LLM_BASE_MS = {
    "simple": 800,
    "moderate": 2000,
    "complex": 4000,
    "critical": 8000,
}
_TOOL_AVG_MS = 800  # 平均每个工具执行耗时

# 模拟 token 估算
_ESTIMATED_TOKENS = {
    "simple": (200, 100),  # (input, output)
    "moderate": (500, 300),
    "complex": (1000, 600),
    "critical": (2000, 1200),
}
_COST_PER_1M = (2.50, 10.00)  # GPT-4o pricing (input, output)


class LatencyCostEvaluator:
    """
    延迟/成本评估器

    基于复杂度和工具数量模拟延迟和成本，
    对比阈值判断是否在可接受范围内。
    """

    dimension = EvalDimension.LATENCY_COST

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        ctx = case.get("context", {})
        complexity = ctx.get("complexity", "moderate")
        tool_count = ctx.get("tool_count", 0)

        # 模拟延迟
        base_ms = _LLM_BASE_MS.get(complexity, 2000)
        simulated_latency = base_ms + tool_count * _TOOL_AVG_MS

        # 模拟成本
        in_tok, out_tok = _ESTIMATED_TOKENS.get(complexity, (500, 300))
        simulated_cost = (
            in_tok * _COST_PER_1M[0] + out_tok * _COST_PER_1M[1]
        ) / 1_000_000

        max_latency = case.get("max_latency_ms", 10000)
        max_cost = case.get("max_cost_usd", 0.10)

        latency_ok = simulated_latency <= max_latency
        cost_ok = simulated_cost <= max_cost

        score = (0.5 if latency_ok else 0.0) + (0.5 if cost_ok else 0.0)

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=score >= 0.5,
            score=score,
            details={
                "simulated_latency_ms": simulated_latency,
                "max_latency_ms": max_latency,
                "latency_ok": latency_ok,
                "simulated_cost_usd": round(simulated_cost, 6),
                "max_cost_usd": max_cost,
                "cost_ok": cost_ok,
            },
        )
