"""
异步反思 Agent — 对话结束后的后台分析与记忆巩固。

流程：
1. 对话结束 → persist_result → 调度反思任务到后台
2. ReflectionAgent 执行：
   a. 策略评估（这次对话的规划路径是否最优？）
   b. 技能提炼（成功的工具链是否值得固化为可复用技能？）
   c. 记忆巩固（触发 consolidation 的 Sleep Cycle）
   d. 模式发现（跨会话行为模式分析）
3. 结果写入 memory_consolidations / skill_library / learning_system

设计原则：
- 完全异步，不阻塞用户响应
- 幂等设计，重复调度不产生副作用
- 渐进式执行，先轻量后重量，任何步骤失败不影响其他步骤
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# 反思触发条件
_MIN_TOOL_CALLS_FOR_SKILL = 2  # 至少 2 个工具调用才考虑技能提炼
_MIN_RESPONSE_LEN_FOR_REFLECTION = 200  # 响应太短不值得反思
_CONSOLIDATION_COOLDOWN_HOURS = 2  # 同一用户的 consolidation 间隔
_MAX_REFLECTION_DURATION_SECONDS = 30  # 反思总超时


@dataclass
class ReflectionResult:
    """反思执行结果"""

    user_id: str
    session_id: str
    strategy_evaluated: bool = False
    skill_extracted: bool = False
    consolidation_triggered: bool = False
    pattern_discovered: bool = False
    errors: list[str] = field(default_factory=list)
    duration_ms: int = 0


class ReflectionAgent:
    """异步反思 Agent — 在对话结束后的后台执行记忆巩固与策略评估"""

    async def reflect_on_conversation(
        self,
        session_id: str,
        user_id: str,
        org_id: str | None = None,
        user_message: str = "",
        assistant_response: str = "",
        tool_calls: list[dict] | None = None,
        plan_summary: str = "",
        complexity: str = "moderate",
        metadata: dict | None = None,
        db: Any = None,
    ) -> ReflectionResult:
        """对一次完整对话进行后台反思分析

        按照从轻量到重量的顺序执行，任何步骤失败不影响后续步骤。
        """
        start_time = datetime.now(UTC)
        result = ReflectionResult(user_id=user_id, session_id=session_id)

        tool_calls = tool_calls or []

        # ── Step 1: 策略评估（轻量）──
        try:
            result.strategy_evaluated = await self._evaluate_strategy(
                user_message=user_message,
                tool_calls=tool_calls,
                complexity=complexity,
                user_id=user_id,
                org_id=org_id,
                db=db,
            )
        except Exception as e:
            result.errors.append(f"strategy_evaluation: {e}")
            logger.error(f"[Reflection] Strategy evaluation failed: {e}")

        # ── Step 2: 技能提炼（中等）──
        if len(tool_calls) >= _MIN_TOOL_CALLS_FOR_SKILL:
            try:
                result.skill_extracted = await self._extract_skill(
                    user_message=user_message,
                    tool_calls=tool_calls,
                    complexity=complexity,
                    user_id=user_id,
                    org_id=org_id,
                    db=db,
                )
            except Exception as e:
                result.errors.append(f"skill_extraction: {e}")
                logger.error(f"[Reflection] Skill extraction failed: {e}")

        # ── Step 3: 记忆巩固 / Sleep Cycle（重量级）──
        try:
            result.consolidation_triggered = await self._trigger_consolidation(
                user_id=user_id,
                org_id=org_id,
                db=db,
            )
        except Exception as e:
            result.errors.append(f"consolidation: {e}")
            logger.error(f"[Reflection] Consolidation failed: {e}")

        # ── Step 4: 偏好学习（轻量）──
        if user_message and assistant_response:
            try:
                result.pattern_discovered = await self._learn_preferences(
                    user_id=user_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    org_id=org_id,
                )
            except Exception as e:
                result.errors.append(f"preference_learning: {e}")
                logger.debug(f"[Reflection] Preference learning failed: {e}")

        elapsed = (datetime.now(UTC) - start_time).total_seconds() * 1000
        result.duration_ms = int(elapsed)

        if any(
            [
                result.strategy_evaluated,
                result.skill_extracted,
                result.consolidation_triggered,
                result.pattern_discovered,
            ]
        ):
            logger.info(
                f"[Reflection] Completed for session {session_id[:8]}: "
                f"strategy={result.strategy_evaluated}, skill={result.skill_extracted}, "
                f"consolidation={result.consolidation_triggered}, "
                f"patterns={result.pattern_discovered}, "
                f"duration={result.duration_ms}ms, errors={len(result.errors)}"
            )

        return result

    # ── 内部方法 ──

    async def _evaluate_strategy(
        self,
        user_message: str,
        tool_calls: list[dict],
        complexity: str,
        user_id: str,
        org_id: str | None,
        db: Any,
    ) -> bool:
        """评估本次对话的规划策略是否最优

        检查：
        - 是否有工具调用失败？记录失败模式
        - 是否有冗余的工具调用？（同一工具连续调用多次）
        - 总延迟是否异常？
        """
        if not tool_calls:
            return False

        failed_calls = [
            tc for tc in tool_calls if tc.get("status") == "error" or tc.get("error")
        ]
        if failed_calls:
            # 记录失败模式到 learning_system
            try:
                from app.agent.learning_system import learning_system

                for tc in failed_calls:
                    tool_name = tc.get("tool_name") or tc.get("name", "unknown")
                    error_msg = str(tc.get("error", ""))[:200]
                    await learning_system.record_failure(
                        tool_name=tool_name,
                        error_pattern=error_msg,
                        context={
                            "user_message": user_message[:200],
                            "complexity": complexity,
                        },
                        user_id=user_id,
                        org_id=org_id,
                    )
            except Exception as e:
                logger.debug(f"[Reflection] Failed to record failure pattern: {e}")

        # 检查冗余调用（同一工具连续调用 3+ 次）
        tool_name_sequence = [
            tc.get("tool_name") or tc.get("name", "") for tc in tool_calls
        ]
        consecutive_count = 1
        for i in range(1, len(tool_name_sequence)):
            if tool_name_sequence[i] == tool_name_sequence[i - 1]:
                consecutive_count += 1
                if consecutive_count >= 3:
                    logger.warning(
                        f"[Reflection] Detected redundant tool calls: "
                        f"{tool_name_sequence[i]} called {consecutive_count} times consecutively"
                    )
            else:
                consecutive_count = 1

        # 记录成功模式（如果全部成功）
        if not failed_calls and len(tool_calls) >= 2:
            try:
                from app.agent.learning_system import learning_system

                tool_chain_str = " → ".join(tool_name_sequence)
                await learning_system.record_success(
                    tool_name=tool_chain_str,
                    solution=f"用户意图: {user_message[:100]}, 工具链: {tool_chain_str}",
                    context={"complexity": complexity, "tool_count": len(tool_calls)},
                    org_id=org_id,
                )
            except Exception as e:
                logger.debug("[ReflectionAgent] Learning system record failed: %s", e)

        return True

    async def _extract_skill(
        self,
        user_message: str,
        tool_calls: list[dict],
        complexity: str,
        user_id: str,
        org_id: str,
        db: Any,
    ) -> bool:
        """从成功的工具调用链中提炼可复用技能"""
        try:
            from app.agent.skill_library import skill_library

            # 检查所有工具是否都成功
            all_success = all(
                tc.get("status") == "success"
                or (not tc.get("error") and tc.get("result"))
                for tc in tool_calls
            )
            if not all_success:
                return False

            skill = await skill_library.extract_skill(
                intent_summary=user_message[:200],
                tool_chain=tool_calls,
                complexity=complexity,
                user_id=user_id,
                org_id=org_id,
                db=db,
            )
            return skill is not None
        except Exception as e:
            logger.debug(f"[Reflection] Skill extraction skipped: {e}")
            return False

    async def _trigger_consolidation(
        self,
        user_id: str,
        org_id: str | None,
        db: Any,
    ) -> bool:
        """触发记忆巩固（如果冷却时间已过）"""
        client = db
        if not client:
            from app.core.database import supabase

            client = supabase
        if not client:
            return False

        try:
            # 检查冷却时间：最近 N 小时内是否已 consolidate 过
            from datetime import timedelta

            cooldown_cutoff = datetime.now(UTC) - timedelta(
                hours=_CONSOLIDATION_COOLDOWN_HOURS
            )
            recent = (
                await client.table("memory_consolidations")
                .select("created_at")
                .eq("user_id", user_id)
                .gte("created_at", cooldown_cutoff.isoformat())
                .limit(1)
                .execute()
            )
            if recent.data:
                return False  # 冷却中

            # 触发 consolidation
            from app.services.conversation_memory.consolidation import (
                consolidate_user_memories,
            )

            result = await consolidate_user_memories(
                user_id=user_id,
                org_id=org_id,
                db=client,
            )
            return result.get("insights_created", 0) > 0

        except Exception as e:
            logger.debug(f"[Reflection] Consolidation skipped: {e}")
            return False

    async def _learn_preferences(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        org_id: str,
    ) -> bool:
        """从对话中自动提取用户偏好"""
        try:
            from app.agent.preference_learner import preference_learner

            await preference_learner.auto_extract_preferences(
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                org_id=org_id,
            )
            return True
        except Exception:
            return False


# ── 调度器：供 persist_result 调用 ──

# 后台任务集合（防止被 GC 回收）
_reflection_tasks: set[asyncio.Task] = set()


def schedule_reflection(
    session_id: str,
    user_id: str,
    org_id: str | None = None,
    user_message: str = "",
    assistant_response: str = "",
    tool_calls: list[dict] | None = None,
    plan_summary: str = "",
    complexity: str = "moderate",
    metadata: dict | None = None,
    db: Any = None,
) -> None:
    """将反思任务调度到后台执行（非阻塞）

    由 persist_result 调用，不阻塞用户响应。
    """
    # 跳过太简单的对话（短响应 + 无工具调用）
    if (
        len(assistant_response or "") < _MIN_RESPONSE_LEN_FOR_REFLECTION
        and not tool_calls
    ):
        return

    agent = ReflectionAgent()

    async def _run_with_timeout():
        try:
            await asyncio.wait_for(
                agent.reflect_on_conversation(
                    session_id=session_id,
                    user_id=user_id,
                    org_id=org_id,
                    user_message=user_message,
                    assistant_response=assistant_response,
                    tool_calls=tool_calls,
                    plan_summary=plan_summary,
                    complexity=complexity,
                    metadata=metadata,
                    db=db,
                ),
                timeout=_MAX_REFLECTION_DURATION_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                f"[Reflection] Timed out after {_MAX_REFLECTION_DURATION_SECONDS}s "
                f"for session {session_id[:8]}"
            )
        except Exception as e:
            logger.error(f"[Reflection] Background reflection failed: {e}")

    task = asyncio.create_task(_run_with_timeout())
    _reflection_tasks.add(task)
    task.add_done_callback(_reflection_tasks.discard)
