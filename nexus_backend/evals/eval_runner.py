"""评估运行器 - 加载数据集、执行评估器、收集指标

使用方式:
    runner = EvalRunner()
    dataset = runner.load_dataset("tool_selection")
    results = await runner.run_evaluation(dataset, evaluator)
    report = runner.generate_report(results, EvalDimension.TOOL_SELECTION)
"""

import logging
import time
from pathlib import Path
from typing import List, Dict, Any

import yaml

from evals.eval_metrics import EvalResult, EvalReport, EvalDimension

logger = logging.getLogger(__name__)


class EvalRunner:
    """
    评估运行器

    职责:
    1. 从 YAML 文件加载评估数据集
    2. 逐个运行测试用例并收集 EvalResult
    3. 汇总生成 EvalReport
    """

    def __init__(self, datasets_dir: str = None) -> None:
        if datasets_dir is None:
            self.datasets_dir = Path(__file__).parent / "datasets"
        else:
            self.datasets_dir = Path(datasets_dir)

    def load_dataset(self, name: str) -> List[Dict[str, Any]]:
        """加载 YAML 数据集文件并返回 test_cases 列表。"""
        path = self.datasets_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        cases = data.get("test_cases", [])
        if not cases:
            raise ValueError(f"Dataset '{name}' contains no test_cases")
        return cases

    async def run_single_case(self, case: Dict[str, Any], evaluator: Any) -> EvalResult:
        """运行单个测试用例，处理异常并记录耗时。"""
        start = time.perf_counter()
        try:
            result = await evaluator.evaluate(case)
            result.duration_ms = (time.perf_counter() - start) * 1000
            return result
        except Exception as e:
            logger.exception(f"Evaluation failed for case {case.get('id', 'unknown')}")
            return EvalResult(
                case_id=case.get("id", "unknown"),
                dimension=evaluator.dimension,
                passed=False,
                score=0.0,
                error=str(e),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    async def run_evaluation(
        self, dataset: List[Dict[str, Any]], evaluator: Any
    ) -> List[EvalResult]:
        """运行整个数据集的评估，返回所有结果。"""
        results: List[EvalResult] = []
        for case in dataset:
            result = await self.run_single_case(case, evaluator)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            logger.info(
                f"  [{result.case_id}] {status} score={result.score:.2f}"
                f"{' error=' + result.error if result.error else ''}"
            )
        return results

    def generate_report(
        self, results: List[EvalResult], dimension: EvalDimension
    ) -> EvalReport:
        """根据评估结果列表生成汇总报告。"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        scores = [r.score for r in results]

        return EvalReport(
            dimension=dimension,
            total_cases=total,
            passed_cases=passed,
            failed_cases=total - passed,
            accuracy=passed / total if total > 0 else 0.0,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            results=results,
        )
