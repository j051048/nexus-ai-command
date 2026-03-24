"""
Shared Blackboard — structured data sharing hub for multi-agent orchestration.

Replaces the old `completed_context: dict[str, str]` local variable with a
thread-safe, structured result store that preserves tool call data and avoids
key collisions between sub-tasks with the same agent_code.
"""

import asyncio
from dataclasses import dataclass, field


@dataclass
class TaskResult:
    """Complete result record for a single sub-task."""

    task_idx: int
    sub_task_id: str
    agent_code: str
    title: str
    status: str  # completed | degraded | failed
    text: str  # Text result from LLM
    tool_calls: list[dict] = field(default_factory=list)
    # Each dict: {tool_name: str, args_summary: str, result_summary: str}


class SharedBlackboard:
    """Thread-safe sub-task result sharing center for orchestrate_node.

    Keyed by task_idx (integer) to avoid agent_code collisions.
    Uses asyncio.Lock for safe concurrent writes from parallel sub-tasks.
    """

    def __init__(self) -> None:
        self._results: dict[int, TaskResult] = {}
        self._lock = asyncio.Lock()

    async def write(self, result: TaskResult) -> None:
        """Write a sub-task result (called from parallel coroutines)."""
        async with self._lock:
            self._results[result.task_idx] = result

    def read(self, task_idx: int) -> TaskResult | None:
        """Read a specific sub-task result.

        Safe to call without lock because reads only happen in subsequent
        layers after the writing layer has fully completed.
        """
        return self._results.get(task_idx)

    def get_dependency_context(self, dependencies: list[int], max_chars: int = 3000) -> str:
        """Build dependency context text for a sub-task, including tool call summaries.

        Status-aware: marks failed/degraded dependencies so downstream agents
        can adjust their behaviour accordingly.

        Args:
            dependencies: List of task indices this sub-task depends on.
            max_chars: Maximum total characters for the context text.
        """
        if not dependencies:
            return ""

        parts: list[str] = []
        anomaly_count = 0
        chars_per_dep = max_chars // max(len(dependencies), 1)

        for dep_idx in dependencies:
            result = self._results.get(dep_idx)
            if not result:
                continue

            # Status-aware prefix
            if result.status == "failed":
                section = f"[前置任务{dep_idx + 1}: {result.title}] ⚠️ [失败]\n"
                section += f"失败原因: {result.text[:chars_per_dep]}"
                anomaly_count += 1
            elif result.status == "degraded":
                section = f"[前置任务{dep_idx + 1}: {result.title}] ⚠️ [降级]\n"
                section += result.text[:chars_per_dep]
                anomaly_count += 1
            else:
                section = f"[前置任务{dep_idx + 1}: {result.title}]\n"
                section += result.text[:chars_per_dep]

            if result.tool_calls:
                tool_names = ", ".join(tc["tool_name"] for tc in result.tool_calls[:5])
                section += f"\n(使用工具: {tool_names})"

            parts.append(section)

        context = "\n\n".join(parts)

        # Prepend overall warning if any anomalies exist
        if anomaly_count > 0:
            warning = f"⚠️ 注意: 前置任务中有 {anomaly_count} 个失败/降级，请据此调整执行策略。\n\n"
            context = warning + context

        return context

    def get_anomaly_summary(self) -> str:
        """Return a summary of all non-completed results for layer-level health checks."""
        anomalies: list[str] = []
        for result in self.get_all_results():
            if result.status != "completed":
                anomalies.append(
                    f"- 任务{result.task_idx + 1} ({result.agent_code}): "
                    f"[{result.status}] {result.title} — {result.text[:100]}"
                )
        return "\n".join(anomalies) if anomalies else ""

    def get_all_results(self) -> list[TaskResult]:
        """Return all results sorted by task_idx."""
        return [self._results[k] for k in sorted(self._results)]

    def get_tool_data_summary(self) -> str:
        """Aggregate tool call data across all sub-tasks for the integration prompt."""
        summaries: list[str] = []
        for result in self.get_all_results():
            for tc in result.tool_calls:
                summaries.append(f"- {result.title}/{tc['tool_name']}: {tc.get('result_summary', '')[:200]}")
        return "\n".join(summaries[:20])
