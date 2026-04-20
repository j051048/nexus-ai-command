"""意图识别回归测试 — CI 门禁

从 intent_regression.yaml 加载黄金数据集，parametrize 每条用例。
CI 门禁: 总通过率 >= 90%, CRITICAL 类 >= 95%。
"""

import pytest
import yaml

from evals.evaluators.intent_regression import (
    DATASET_PATH,
    evaluate_single,
    run_evaluation,
)


def _load_cases():
    with open(DATASET_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["test_cases"]


_CASES = _load_cases()
_CASE_IDS = [c["id"] for c in _CASES]


@pytest.mark.regression
class TestIntentRegression:

    @pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
    def test_single_case(self, case):
        result = evaluate_single(case)
        if not result.passed:
            reasons = result.details.get("reasons", [])
            msg = case["user_message"]
            pytest.fail(
                f"[{case['id']}] '{msg}' → {'; '.join(reasons)}"
            )


@pytest.mark.regression
class TestIntentRegressionGate:
    """CI 门禁: 汇总通过率必须达标"""

    def test_overall_pass_rate(self):
        report = run_evaluation()
        threshold = 0.90
        assert report.accuracy >= threshold, (
            f"意图回归通过率 {report.accuracy:.1%} < {threshold:.0%} 门禁 "
            f"({report.failed_cases}/{report.total_cases} 失败)"
        )

    def test_critical_pass_rate(self):
        cases = [c for c in _CASES if "critical" in c.get("tags", [])]
        if not cases:
            pytest.skip("No CRITICAL cases in dataset")
        results = [evaluate_single(c) for c in cases]
        passed = sum(1 for r in results if r.passed)
        rate = passed / len(results)
        threshold = 0.95
        assert rate >= threshold, (
            f"CRITICAL 类通过率 {rate:.1%} < {threshold:.0%} 门禁 "
            f"({len(results) - passed}/{len(results)} 失败)"
        )
