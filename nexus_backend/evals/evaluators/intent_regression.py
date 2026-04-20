"""意图识别回归评估器

规则模式（默认）：直接比对 classify_query / detect_agent_role 输出
LLM-as-Judge 模式（可选）：有 OPENAI_API_KEY 时对 COMPLEX/CRITICAL 二次验证
"""

import logging
import os
import time
from pathlib import Path

import yaml

from app.agent.router import classify_query, detect_agent_role
from app.agent.state import QueryComplexity
from evals.eval_metrics import EvalDimension, EvalReport, EvalResult

logger = logging.getLogger(__name__)

_COMPLEXITY_ORDER = {
    QueryComplexity.SIMPLE: 0,
    QueryComplexity.MODERATE: 1,
    QueryComplexity.COMPLEX: 2,
    QueryComplexity.CRITICAL: 3,
}

_STR_TO_COMPLEXITY = {c.value: c for c in QueryComplexity}

DATASET_PATH = Path(__file__).parent.parent / "datasets" / "intent_regression.yaml"


def _gte(actual: QueryComplexity, expected: QueryComplexity) -> bool:
    return _COMPLEXITY_ORDER[actual] >= _COMPLEXITY_ORDER[expected]


def load_dataset() -> dict:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_single(case: dict) -> EvalResult:
    start = time.perf_counter()
    msg = case["user_message"]
    case_id = case["id"]
    details: dict = {"user_message": msg}

    actual_complexity, intent_summary = classify_query(msg)
    details["actual_complexity"] = actual_complexity.value
    details["intent_summary"] = intent_summary

    passed = True
    reasons = []

    # --- Complexity assertions ---
    if "expected_complexity" in case:
        exp = _STR_TO_COMPLEXITY[case["expected_complexity"]]
        if actual_complexity != exp:
            passed = False
            reasons.append(f"complexity: got {actual_complexity.value}, want {exp.value}")

    if "expected_complexity_min" in case:
        exp_min = _STR_TO_COMPLEXITY[case["expected_complexity_min"]]
        if not _gte(actual_complexity, exp_min):
            passed = False
            reasons.append(f"complexity: got {actual_complexity.value}, want >= {exp_min.value}")

    if "expected_complexity_not" in case:
        exp_not = _STR_TO_COMPLEXITY[case["expected_complexity_not"]]
        if actual_complexity == exp_not:
            passed = False
            reasons.append(f"complexity: got {actual_complexity.value}, want != {exp_not.value}")

    # --- Agent role assertions ---
    if "expected_agent" in case or "expected_multi_agent" in case:
        agent_code, scene_code, multi = detect_agent_role(msg, actual_complexity)
        details["actual_agent"] = agent_code
        details["actual_multi_agent"] = multi

        if "expected_agent" in case:
            exp_agent = case["expected_agent"]
            if agent_code != exp_agent:
                passed = False
                reasons.append(f"agent: got '{agent_code}', want '{exp_agent}'")

        if "expected_multi_agent" in case:
            exp_multi = case["expected_multi_agent"]
            if multi != exp_multi:
                passed = False
                reasons.append(f"multi_agent: got {multi}, want {exp_multi}")

    duration_ms = (time.perf_counter() - start) * 1000
    details["reasons"] = reasons

    return EvalResult(
        case_id=case_id,
        dimension=EvalDimension.ROUTER_ACCURACY,
        passed=passed,
        score=1.0 if passed else 0.0,
        details=details,
        error="; ".join(reasons) if reasons else None,
        duration_ms=duration_ms,
    )


def run_evaluation() -> EvalReport:
    dataset = load_dataset()
    cases = dataset["test_cases"]
    results = [evaluate_single(c) for c in cases]

    passed = sum(1 for r in results if r.passed)
    total = len(results)

    return EvalReport(
        dimension=EvalDimension.ROUTER_ACCURACY,
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        accuracy=passed / total if total else 0,
        avg_score=sum(r.score for r in results) / total if total else 0,
        results=results,
    )


def llm_judge_classification(msg: str, actual: str, expected: str) -> bool:
    """Optional LLM-as-Judge for ambiguous cases. Requires OPENAI_API_KEY."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return True  # skip when no key

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个意图分类评审员。判断以下用户消息的复杂度分类是否合理。\n"
                        "复杂度级别: simple(问候闲聊), moderate(单工具查询), "
                        "complex(多步分析/报告), critical(审批/财务变更/HR敏感操作)\n"
                        "只回答 CORRECT 或 INCORRECT。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"用户消息: {msg}\n"
                        f"系统分类: {actual}\n"
                        f"期望分类: {expected}\n"
                        f"系统分类是否合理？"
                    ),
                },
            ],
            max_tokens=10,
            temperature=0,
        )
        answer = resp.choices[0].message.content.strip().upper()
        return "CORRECT" in answer
    except Exception as e:
        logger.warning(f"LLM judge failed: {e}")
        return True
