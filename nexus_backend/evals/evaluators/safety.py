"""安全性评估器

使用 ContentModerator 的 check_input() 方法检测:
- 误杀 (False Positive): 正常业务输入被拦截
- 漏杀 (False Negative): 恶意输入未被拦截

在测试中通过 mock content_moderator 来避免 LLM 调用。
"""

from typing import Dict, Any

from evals.eval_metrics import EvalResult, EvalDimension


class SafetyEvaluator:
    """
    安全性评估器

    调用 content_moderation.ContentModerator.check_input() 进行内容审核，
    然后对比 should_pass 预期来判断是否正确。
    """

    dimension = EvalDimension.SAFETY

    async def evaluate(self, case: Dict[str, Any]) -> EvalResult:
        """评估内容审核的准确性。"""
        from app.services.content_moderation import content_moderator

        should_pass: bool = case.get("should_pass", True)

        # check_input 返回 (is_safe, warning_message)
        is_safe, warning_msg = content_moderator.check_input(case["user_message"])
        actually_passed = is_safe

        # 判定: 预期与实际是否一致
        correct = should_pass == actually_passed

        # 分类错误类型
        if correct:
            error_type = "correct"
        elif should_pass and not actually_passed:
            error_type = "false_positive"  # 误杀
        else:
            error_type = "false_negative"  # 漏杀

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=correct,
            score=1.0 if correct else 0.0,
            details={
                "should_pass": should_pass,
                "actually_passed": actually_passed,
                "error_type": error_type,
                "warning": warning_msg,
            },
        )
