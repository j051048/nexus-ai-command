"""评估指标和报告数据结构

定义评估维度、单个测试结果、汇总报告等核心数据类。
所有评估器产出的结果都统一为 EvalResult -> EvalReport 结构。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EvalDimension(Enum):
    """评估维度枚举"""

    TOOL_SELECTION = "tool_selection"
    HALLUCINATION = "hallucination"
    TASK_COMPLETION = "task_completion"
    SAFETY = "safety"


@dataclass
class EvalResult:
    """单个测试用例的评估结果"""

    case_id: str
    dimension: EvalDimension
    passed: bool
    score: float  # 0.0 to 1.0
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class EvalReport:
    """一个维度的评估报告"""

    dimension: EvalDimension
    total_cases: int
    passed_cases: int
    failed_cases: int
    accuracy: float  # passed / total
    avg_score: float
    results: list[EvalResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """将报告序列化为字典，方便 JSON 输出或日志记录。"""
        return {
            "dimension": self.dimension.value,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "accuracy": round(self.accuracy, 4),
            "avg_score": round(self.avg_score, 4),
            "timestamp": self.timestamp,
            "details": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "score": r.score,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


class MetricsReporter:
    """汇总多维度评估报告，支持阈值校验。"""

    def __init__(self) -> None:
        self.reports: dict[EvalDimension, EvalReport] = {}

    def add_report(self, report: EvalReport) -> None:
        self.reports[report.dimension] = report

    def summary(self) -> dict[str, Any]:
        """返回各维度的汇总摘要。"""
        return {
            dim.value: {
                "accuracy": report.accuracy,
                "total": report.total_cases,
                "passed": report.passed_cases,
            }
            for dim, report in self.reports.items()
        }

    def all_passed(self, thresholds: dict[EvalDimension, float]) -> bool:
        """检查所有维度是否都达到了指定的准确率阈值。"""
        for dim, threshold in thresholds.items():
            report = self.reports.get(dim)
            if not report or report.accuracy < threshold:
                return False
        return True
