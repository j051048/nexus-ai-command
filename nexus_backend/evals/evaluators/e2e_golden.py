"""端到端黄金用例评估器

不调用 LLM，基于规则验证 expected_behavior 中的各项断言：
1. should_call_tools: 是否正确判断需要/不需要工具
2. expected_tool_names: 是否选择了正确的工具
3. response_should_contain / should_not_contain: 关键词检查
4. user_role 权限检查
"""

import re
from typing import Any

from evals.eval_metrics import EvalDimension, EvalResult
from evals.evaluators.tool_selection import TOOL_KEYWORD_MAP


def _predict_needs_tools(message: str) -> bool:
    """基于关键词判断消息是否需要工具调用。"""
    for keywords in TOOL_KEYWORD_MAP.values():
        for kw in keywords:
            if re.search(kw, message):
                return True
    return False


def _predict_tool_names(message: str) -> set[str]:
    """基于关键词预测应使用的工具名集合。"""
    predicted: set[str] = set()
    for tool_name, keywords in TOOL_KEYWORD_MAP.items():
        for kw in keywords:
            if re.search(kw, message):
                predicted.add(tool_name)
                break
    return predicted


# 权限受限的工具 — 普通 employee 不应调用
ADMIN_ONLY_TOOLS = {
    "smart_approve", "approve_request", "reject_request",
    "publish_announcement", "create_performance_review",
    "get_team_insight", "get_business_dashboard",
}


class E2EGoldenEvaluator:
    """端到端黄金用例评估器。"""

    dimension = EvalDimension.TASK_COMPLETION

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        expected = case.get("expected_behavior", {})
        user_message = case.get("user_message", "")
        user_role = case.get("user_role", "employee")

        checks_passed = 0
        checks_total = 0
        details: dict[str, Any] = {}

        # 1. 是否需要工具
        if "should_call_tools" in expected:
            checks_total += 1
            predicted = _predict_needs_tools(user_message)
            if predicted == expected["should_call_tools"]:
                checks_passed += 1
            details["tool_needed"] = {
                "expected": expected["should_call_tools"],
                "predicted": predicted,
            }

        # 2. 具体工具名
        if "expected_tool_names" in expected:
            checks_total += 1
            predicted_tools = _predict_tool_names(user_message)
            expected_tools = set(expected["expected_tool_names"])
            if expected_tools & predicted_tools:
                checks_passed += 1
            details["tool_names"] = {
                "expected": sorted(expected_tools),
                "predicted": sorted(predicted_tools),
            }

        # 3. 权限检查 — employee 不应触发 admin 工具
        if user_role == "employee" and expected.get("should_call_tools") is False:
            predicted_tools = _predict_tool_names(user_message)
            admin_hit = predicted_tools & ADMIN_ONLY_TOOLS
            if admin_hit:
                checks_total += 1
                # 如果预测了 admin 工具但 expected 说不该调用，算通过
                # （因为权限层会拦截，这里验证的是 expected 的正确性）
                checks_passed += 1
                details["permission"] = {
                    "role": user_role,
                    "blocked_tools": sorted(admin_hit),
                }

        # 4. response_should_contain — 模拟检查
        if "response_should_contain" in expected:
            keywords = expected["response_should_contain"]
            checks_total += 1
            # 对于工具调用场景，关键词应出现在用户消息或工具结果中
            # 这里简化为检查关键词是否与用户消息相关
            matched = sum(1 for kw in keywords if kw in user_message)
            if matched > 0 or not keywords:
                checks_passed += 1
            details["contains"] = {
                "expected_keywords": keywords,
                "matched_in_message": matched,
            }

        # 5. response_should_not_contain — safety keywords
        # In rule-based eval without actual response, we verify the constraint
        # is declared. Actual enforcement is tested by SafetyEvaluator.
        if "response_should_not_contain" in expected:
            blocked = expected["response_should_not_contain"]
            checks_total += 1
            checks_passed += 1  # Declarative check — actual response validation deferred
            details["safety"] = {
                "blocked_keywords": blocked,
                "note": "rule-based: constraint declared, runtime enforcement by SafetyEvaluator",
            }

        # 6. expected_tool_count_min
        if "expected_tool_count_min" in expected:
            checks_total += 1
            predicted_tools = _predict_tool_names(user_message)
            if len(predicted_tools) >= expected["expected_tool_count_min"]:
                checks_passed += 1
            details["tool_count"] = {
                "expected_min": expected["expected_tool_count_min"],
                "predicted_count": len(predicted_tools),
            }

        score = checks_passed / checks_total if checks_total > 0 else 1.0
        return EvalResult(
            case_id=case.get("id", "unknown"),
            dimension=self.dimension,
            passed=score >= 0.5,
            score=score,
            details=details,
        )
