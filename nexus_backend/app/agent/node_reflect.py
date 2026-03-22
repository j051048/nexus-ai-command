"""
Graph Nodes: reflect_node, critic_node, _verify_tool_grounding
"""

import json as _json
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    AgentState,
    CriticResult,
    GroundednessCheck,
    HallucinationCheck,
    QueryComplexity,
    ThinkingStep,
    _get_langfuse_callbacks,
    _get_llm,
    _get_trace_context,
    logger,
    record_hallucination,
    sanitize_output,
    scan_content,
)


def _normalize_number(text: str) -> float | None:
    """将中文数字表达归一化为浮点数。

    支持: 428万 → 4280000, 3.5亿 → 350000000, 4,280,000 → 4280000,
          95.2% → 95.2, 12.5k → 12500, 2.1M → 2100000
    """
    text = text.strip().replace(",", "").replace("，", "")
    _CN_UNITS = {"万": 1e4, "亿": 1e8, "千": 1e3, "百": 1e2}
    _EN_UNITS = {"k": 1e3, "K": 1e3, "M": 1e6, "m": 1e6}

    # 百分比: 95.2% → 95.2
    m = re.match(r"^(\d+(?:\.\d+)?)%$", text)
    if m:
        return float(m.group(1))

    # 中文单位: 428万
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([万亿千百])$", text)
    if m:
        return float(m.group(1)) * _CN_UNITS[m.group(2)]

    # 英文缩写: 12.5k / 2.1M
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([kKmM])$", text)
    if m:
        return float(m.group(1)) * _EN_UNITS[m.group(2)]

    # 纯数字
    m = re.match(r"^(\d+(?:\.\d+)?)$", text)
    if m:
        return float(m.group(1))

    return None


async def _verify_tool_grounding(ai_response: str, tool_results: list) -> str | None:
    """
    P1 Fix: Verify that numerical data in AI response matches tool results.
    Returns a description of grounding issues, or None if all grounded.

    Uses relaxed matching to avoid false positives:
    - Skips small numbers (< 10) which are commonly used in formatting
    - Uses ±10% relative tolerance for number comparison
    - Requires at least 3 ungrounded numbers to trigger (avoids noise from dates, IDs, etc.)
    - Aggressively strips date/time strings before extracting numbers.
    """
    issues = []

    # Strip out common date/time formats to avoid false positives (e.g. 2024年12月16日, 2024-12-16)
    def _strip_dates(text: str) -> str:
        text = re.sub(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?", "", text)
        text = re.sub(r"\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}", "", text)
        text = re.sub(r"\d{1,2}\s*:\s*\d{1,2}(?:\s*:\s*\d{1,2})?", "", text)
        # Also strip ISO timestamps and UUIDs which contain many numbers
        text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "", text)
        text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", text)
        return text

    clean_ai_response = _strip_dates(ai_response)

    # Extract numbers from AI response — support Chinese units like 428万
    _num_pattern = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?(?:[万亿千百kKmM%])?")
    ai_raw_numbers = _num_pattern.findall(clean_ai_response)
    ai_numbers = [(_normalize_number(n), n) for n in ai_raw_numbers if _normalize_number(n) is not None]

    # Get all numbers from tool results (also strip dates to avoid false positives)
    tool_numbers: list[float] = []
    for tool in tool_results:
        # P1 fix: Handle both ToolCallRecord objects and dicts
        result_text = tool.get("result", "") if isinstance(tool, dict) else getattr(tool, "result", "")
        if result_text:
            clean_result = _strip_dates(str(result_text))
            for raw in _num_pattern.findall(clean_result):
                val = _normalize_number(raw)
                if val is not None:
                    tool_numbers.append(val)

    if not tool_numbers:
        return None  # No tool numbers to compare against

    # Check if AI mentions numbers not in tool results (semantic comparison)
    for val, raw in ai_numbers:
        # Skip small numbers — commonly used in formatting, list indices, etc.
        if val < 10:
            continue
        # Use ±10% relative tolerance for comparison
        found = any(abs(val - tn) / max(tn, 1.0) < 0.10 for tn in tool_numbers)
        if not found:
            issues.append(f"数值 {raw} 未见工具返回")

    # Require at least 3 ungrounded numbers to flag (avoids noise from IDs, etc.)
    if len(issues) >= 3:
        return "; ".join(issues[:3])

    return None


async def reflect_node(state: AgentState) -> dict:
    """
    P1 Security Enhancement: Self-reflection with advanced hallucination detection.

    Detection layers:
    1. Empty response check
    2. Keyword-based hallucination detection
    3. Tool result grounding verification
    4. LLM-based fact checking
    5. Numerical data validation
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    completed_tools = state.get("completed_tool_calls", [])
    reflection_count = state.get("reflection_count", 0)

    # ── Item 33: Adaptive Reflection Budget ──
    _REFLECTION_BUDGET = {
        QueryComplexity.SIMPLE: 0,
        QueryComplexity.MODERATE: 1,
        QueryComplexity.COMPLEX: 2,
        QueryComplexity.CRITICAL: 3,
    }
    max_reflections = _REFLECTION_BUDGET.get(complexity, 2)
    # 涉及不可逆操作时 +1（上限 4）
    if any(getattr(tc, "is_irreversible", False) for tc in completed_tools):
        max_reflections = min(max_reflections + 1, 4)
    if reflection_count >= max_reflections:
        logger.info(
            f"[ReflectNode] Reflection budget exhausted "
            f"({reflection_count}/{max_reflections}), skipping to respond"
        )
        # Extract last AI content for final_response
        last_content = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                from app.agent.think_tags import extract_clean_content
                last_content = extract_clean_content(msg)
                break
        return {
            "reflection": f"反思预算耗尽 ({reflection_count}/{max_reflections})，直接输出",
            "is_hallucination": False,
            "needs_replanning": False,
            "confidence_score": 0.7,
            "final_response": last_content,
            "current_phase": AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content=f"反思预算已用完 ({reflection_count}/{max_reflections})，跳过反思直接输出",
                )
            ],
        }

    # Resolve model via pre-resolved configs (Step 2: centralized resolution)
    resolved = None
    if config.resolved_configs:
        resolved = config.resolved_configs.get(complexity.model_tier)
    if not resolved:
        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = config.org_id or "default"
            scene_code = state.get("scene_code", "")
            agent_code = state.get("agent_code", "")
            resolved = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier=complexity.model_tier)
        except Exception:
            logger.debug("LLM gateway model config unavailable in reflect_node, using default")

    # Extract the last AI message
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            # Use extract_clean_content to strip reasoning from reasoning models
            from app.agent.stream import extract_clean_content
            last_ai_content = extract_clean_content(msg)
            break

    thinking_step = ThinkingStep(
        phase=AgentPhase.REFLECTING.value,
        content="正在评估回复完整度与事实准确性...",
    )

    # ── Layer 1: Empty response check ──
    if (not last_ai_content.strip() or len(last_ai_content.strip()) < 5) and completed_tools:
        should_replan = iteration < config.max_iterations
        return {
            "reflection": "回复内容为空，需要整合工具结果重新回答。",
            "needs_replanning": should_replan,
            "iteration": iteration + 1 if should_replan else iteration,
            "current_phase": AgentPhase.PLANNING if should_replan else AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content="检测到未正常生成回复，触发重试路径",
                )
            ],
        }

    # ── Layer 2: Keyword-based hallucination detection ──
    is_hallucination = False
    hallucination_reason = ""
    
    intent = state.get("intent_summary", "")
    is_creative_writing = any(kw in intent for kw in ("写作", "创作", "软文", "文章", "报告", "方案", "推广"))

    if not is_creative_writing and complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL) and not completed_tools:
        hallucination_keywords = ["查询到", "系统显示", "数据显示", "结果是", "找到", "检索到", "发现"]
        if any(kw in last_ai_content for kw in hallucination_keywords):
            # Additional check: does it contain specific numbers/data?
            number_pattern = r"\d+(?:\.\d+)?(?:万|千|百|元|个|%|位)?"
            if re.search(number_pattern, last_ai_content):
                is_hallucination = True
                hallucination_reason = "复杂查询未调用工具却产出了具体数据"

    # ── Layer 3: Tool result grounding verification ──
    # P1 Fix: Verify that numerical data in response matches tool results
    if not is_creative_writing and completed_tools and last_ai_content:
        grounding_issues = await _verify_tool_grounding(last_ai_content, completed_tools)
        if grounding_issues:
            is_hallucination = True
            hallucination_reason = f"回复数据与工具返回不一致: {grounding_issues}"

    # ── Layer 4: RAG-based groundedness check ──
    # IMPORTANT: Skip this check when tools were involved (even if some failed).
    # If the query triggered tool calls, it's a tool-oriented query — RAG context
    # is NOT the right source of truth for validating the response.
    grounded_warning = None
    rag_context = state.get("rag_context", "")

    # Safely get tool status, handling both dict and dataclass
    def _is_success(t):
        if isinstance(t, dict):
            return t.get("status") == "success"
        return getattr(t, "status", None) == "success"

    has_successful_tools = any(_is_success(t) for t in completed_tools)
    has_any_tool_attempts = len(completed_tools) > 0

    # Broader pattern matching for failed/empty RAG results
    _rag_empty_patterns = ("搜索失败", "缺少", "未找到", "没有找到", "无相关", "暂无", "不存在")
    rag_search_failed = (
        not rag_context or any(p in rag_context for p in _rag_empty_patterns) or len(rag_context.strip()) < 20
    )

    # Skip Layer 4 when: tools were attempted (query is tool-oriented), OR RAG returned nothing useful
    if rag_context and last_ai_content and not is_hallucination and not has_any_tool_attempts and not rag_search_failed:
        prompt = f"""[事实核查任务]
请比较【参考知识】与【AI回复】，判断回复是否完全基于背景知识，是否存在编造或矛盾。
请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"is_grounded": true, "reason": "", "score": 0.8}}

参考知识:
{rag_context[:2000]}

AI回复:
{last_ai_content[:1000]}
"""
        try:
            import re as _re

            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            raw_resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_text = raw_resp.content.strip()
            json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
            if json_match:
                parsed = _json.loads(json_match.group())
                eval_result = GroundednessCheck(**parsed)
                if not eval_result.is_grounded:
                    is_hallucination = True
                    grounded_warning = eval_result.reason or "事实偏差"
                    logger.warning(f"[Reflect] Ungrounded response: {grounded_warning}")
        except Exception as e:
            logger.debug(f"[ReflectNode] Groundedness check failed: {e}")
    elif has_any_tool_attempts:
        logger.info(
            f"[Reflect] Layer 4 skipped: query used tools "
            f"(success={has_successful_tools}, total={len(completed_tools)}), "
            f"RAG groundedness check not applicable"
        )
    elif rag_search_failed:
        logger.info("[Reflect] Layer 4 skipped: RAG context empty or search failed")

    # ── Layer 5: LLM-based reflection ──
    # Skip LLM reflection if tools were involved — tool results are ground truth.
    if not is_creative_writing and config.reflect_use_llm and last_ai_content and not is_hallucination and not has_any_tool_attempts:
        messages_text = "\n".join([f"{m.type}: {m.content[:200]}" for m in messages[-3:]])
        prompt = f"""请评估 AI 的最新回复是否包含编造的信息（幻觉）。

检查要点:
1. 是否声称有数据但实际未调用工具?
2. 是否引用了不存在的文档或来源?
3. 数值是否合理且有依据?

请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"is_hallucination": false, "reason": "", "confidence": 0.8}}

上下文摘要:
{messages_text}

AI 回复:
{last_ai_content}
"""
        try:
            import re as _re

            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            raw_resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_text = raw_resp.content.strip()
            json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
            if json_match:
                parsed = _json.loads(json_match.group())
                eval_result = HallucinationCheck(**parsed)
                if eval_result.is_hallucination:
                    is_hallucination = True
                    hallucination_reason = eval_result.reason or "存在事实偏差"
        except Exception as e:
            logger.debug(f"[ReflectNode] LLM eval failed: {e}")

    if grounded_warning:
        hallucination_reason = grounded_warning

    # ── Content Safety ──
    is_safe, violations = scan_content(last_ai_content)
    if not is_safe:
        last_ai_content = sanitize_output(last_ai_content)

    # Calculate confidence
    confidence = 0.85
    if is_hallucination:
        confidence = 0.3
    if completed_tools:
        # P1 Fix: Don't override hallucination-reduced confidence
        confidence = min(confidence, 0.95) if is_hallucination else 0.95
    if state.get("needs_replanning"):
        confidence = min(confidence, 0.6)

    needs_replanning = is_hallucination and iteration < config.max_iterations

    # P1 Fix: Record hallucination metrics
    if is_hallucination:
        record_hallucination("reflect_node")

    if needs_replanning:
        # Provide escalating feedback: deeper iterations get more specific UI hints
        if iteration >= 3:
            thinking_content = f"🔄 深度验证第{iteration}轮: {hallucination_reason}，即将结束验证..."
        elif iteration >= 2:
            thinking_content = f"🔄 深度验证中 (第{iteration}轮): {hallucination_reason}，正在修正..."
        else:
            thinking_content = f"⚠️ 检测到潜在事实错误: {hallucination_reason}，正在修正..."

        # P0-3: Build structured correction guidance for plan_node
        guidance_parts = [f"## 反思修正指令 (第{iteration + 1}轮)"]
        guidance_parts.append(f"**问题类型**: {hallucination_reason}")

        if "未调用工具却产出了具体数据" in hallucination_reason:
            guidance_parts.append("**修正策略**: 必须调用相关工具获取真实数据，禁止凭空编造数值")
            guidance_parts.append("**建议**: 根据用户查询意图选择数据查询类工具")
        elif "工具返回不一致" in hallucination_reason:
            guidance_parts.append("**修正策略**: 严格引用工具返回的原始数据，不做未经授权的数值修改")
        elif "事实偏差" in hallucination_reason or "Ungrounded" in str(hallucination_reason):
            guidance_parts.append("**修正策略**: 回复必须完全基于检索到的参考知识，移除无依据的陈述")
        else:
            guidance_parts.append("**修正策略**: 重新审视回复，确保所有信息有据可查")

        if completed_tools:
            tool_summary = []
            for t in completed_tools[-3:]:
                t_name = t.tool_name if hasattr(t, "tool_name") else t.get("tool_name", "")
                t_result = (t.result if hasattr(t, "result") else t.get("result", ""))[:200]
                tool_summary.append(f"  - {t_name}: {t_result}")
            guidance_parts.append("**可用工具结果**:\n" + "\n".join(tool_summary))

        reflection_guidance = "\n".join(guidance_parts)

        # ── Log hallucination failure ──
        try:
            from app.services.failure_log_service import failure_log_service

            user_message = ""
            for msg in reversed(messages):
                if hasattr(msg, "type") and msg.type == "human":
                    user_message = msg.content
                    break
            await failure_log_service.log_failure(
                org_id=getattr(config, "org_id", None),
                user_id=getattr(config, "user_id", None),
                conversation_id=getattr(config, "conversation_id", None),
                user_message=user_message or last_ai_content[:200],
                intent_summary=state.get("intent_summary"),
                complexity=complexity.value if complexity else None,
                error_type="hallucination",
                error_detail=hallucination_reason[:2000],
                severity="high",
            )
        except Exception as e:
            logger.debug(f"[ReflectNode] Failed to log hallucination: {e}")

        from app.core.ai_metrics import record_hallucination
        record_hallucination("reflect_grounding_check")

        return {
            "messages": [HumanMessage(content=f"[自我指引] {reflection_guidance}")],
            "reflection": f"触发幻觉修正: {hallucination_reason}",
            "reflection_guidance": reflection_guidance,
            "is_hallucination": True,
            "needs_replanning": True,
            "confidence_score": confidence,
            "current_phase": AgentPhase.PLANNING,
            "iteration": iteration + 1,
            "reflection_count": reflection_count + 1,
            "thinking_steps": [
            ],
        }

    return {
        "reflection": "通过质量校验",
        "is_hallucination": is_hallucination,
        "needs_replanning": False,
        "confidence_score": confidence,
        "final_response": last_ai_content,
        "current_phase": AgentPhase.RESPONDING,
        "reflection_count": reflection_count + 1,
        "thinking_steps": [thinking_step],
    }


async def critic_node(state: AgentState) -> dict:
    """
    P1-5: Independent quality evaluation before final response.

    Only activates for COMPLEX/CRITICAL queries. Uses mini_model with a strict
    evaluation prompt to assess completeness, relevance, and accuracy.
    If the critic fails the response, it sets reflection_guidance and
    needs_replanning=True to send it back to plan_node for one correction pass.
    """
    config: AgentConfig = state["config"]
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Skip critic for simple/moderate queries — not worth the extra LLM call
    if complexity in (QueryComplexity.SIMPLE, QueryComplexity.MODERATE):
        return {
            "critic_passed": True,
            "critic_feedback": "",
            "current_phase": AgentPhase.RESPONDING,
        }

    final_response = state.get("final_response", "")
    if not final_response:
        from app.agent.stream import extract_clean_content
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = extract_clean_content(msg)
                break

    if not final_response:
        return {
            "critic_passed": True,
            "critic_feedback": "无回复内容，跳过评审",
            "current_phase": AgentPhase.RESPONDING,
        }

    # Gather context for critic evaluation
    intent_summary = state.get("intent_summary", "")
    tool_results_summary = []
    for tc in state.get("completed_tool_calls", []):
        result_preview = (getattr(tc, "result", "") or "")[:200]
        tool_results_summary.append(f"- {tc.tool_name}: {result_preview}")
    tool_context = "\n".join(tool_results_summary[:5]) if tool_results_summary else "无工具调用"

    # Inject historical failure lessons into critic prompt (few-shot from failure_log)
    history_lessons = ""
    try:
        from app.services.failure_log_service import failure_log_service
        _org_id = getattr(config, "org_id", None)
        if _org_id:
            failures = await failure_log_service.get_top_failures(_org_id, days=7, limit=5)
            if failures:
                # Filter out saturated signals — systemic issues that
                # repeating in the prompt won't help fix
                actionable = [f for f in failures if not f.get("saturated")]
                if actionable:
                    lesson_lines = ["## 历史教训（近期常见错误，请重点检查）"]
                    for f in actionable[:3]:
                        err_type = f.get("error_type", "unknown")
                        pattern = f.get("pattern_key", "")
                        count = f.get("count", 1)
                        err_detail = (f.get("error_detail") or "")[:100]
                        lesson_lines.append(f"- [{err_type}] {err_detail} (模式: {pattern}, 出现{count}次)")
                    history_lessons = "\n".join(lesson_lines) + "\n\n"
    except Exception:
        pass  # 非关键路径

    critic_prompt = f"""你是一个严格的质量评审员。请评估以下AI回复的质量。

## 用户意图
{intent_summary or "未知"}

## 工具调用结果摘要
{tool_context}

## AI回复
{final_response[:2000]}

{history_lessons}## 评估标准
1. completeness (0-1): 回答是否完整覆盖了用户的所有问题点？
2. relevance (0-1): 回答是否紧扣用户意图，没有跑题？
3. accuracy (0-1): 回答中的数据/事实是否与工具返回结果一致？
4. passed (true/false): 三项均≥0.6 且无明显错误时为 true
5. improvement_suggestion: 如果 passed=false，给出简明改进建议（一句话）

请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"completeness": 0.8, "relevance": 0.9, "accuracy": 0.7, "passed": true, "improvement_suggestion": ""}}"""

    try:
        # Resolve model via pre-resolved configs (Step 2: centralized resolution)
        resolved_critic = None
        if config.resolved_configs:
            resolved_critic = config.resolved_configs.get("economy")
        if not resolved_critic:
            try:
                from app.services.llm_helpers import resolve_model_config

                org_id = config.org_id or "default"
                scene_code = state.get("scene_code", "")
                agent_code = state.get("agent_code", "")
                resolved_critic = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier="economy")
            except Exception:
                logger.debug("LLM gateway unavailable in critic_node, using default mini_model")

        if resolved_critic:
            # Validate api_key — Gateway may return empty key for misconfigured models
            critic_api_key = resolved_critic.get("api_key") or config.api_key
            critic_base_url = resolved_critic.get("base_url") or config.base_url
            critic_llm = ChatOpenAI(
                model=resolved_critic.get("model", config.mini_model),
                api_key=critic_api_key,
                base_url=critic_base_url,
                temperature=0.1,
                max_tokens=300,
                callbacks=_get_langfuse_callbacks(**_get_trace_context(config), tags=["reflect"]),
            )
        else:
            critic_llm = ChatOpenAI(
                model=config.mini_model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=0.1,
                max_tokens=300,
                callbacks=_get_langfuse_callbacks(**_get_trace_context(config), tags=["reflect"]),
            )
        # Avoid with_structured_output — many proxied/non-OpenAI APIs reject
        # additionalProperties in the JSON schema.  Parse JSON manually instead.
        import re as _re

        raw_response = await critic_llm.ainvoke([SystemMessage(content=critic_prompt)])
        raw_text = raw_response.content.strip()
        # Extract JSON from possible markdown fences
        json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in critic response: {raw_text[:200]}")
        parsed = _json.loads(json_match.group())
        result = CriticResult(**parsed)
    except Exception as e:
        # Critic failure should never block the response — silently pass
        logger.warning(f"[CriticNode] Evaluation failed, silently passing: {e}")
        return {
            "critic_passed": True,
            "critic_feedback": f"评审异常，自动通过: {e}",
            "current_phase": AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.CRITIQUING.value,
                    content="质量评审异常，自动通过",
                )
            ],
        }

    # Persist critic score (non-blocking)
    try:
        await _persist_critic_score(
            state=state,
            result=result,
            model_code=(resolved_critic or {}).get("model", config.mini_model),
        )
    except Exception as e:
        logger.warning(f"[CriticNode] Failed to persist quality score: {e}")

    critic_feedback = (
        f"完整性: {result.completeness:.0%}, 相关性: {result.relevance:.0%}, 准确性: {result.accuracy:.0%}"
    )
    if result.improvement_suggestion:
        critic_feedback += f" | 建议: {result.improvement_suggestion}"

    if result.passed:
        logger.info(f"[CriticNode] ✅ Passed: {critic_feedback}")
        return {
            "critic_passed": True,
            "critic_feedback": critic_feedback,
            "confidence_score": min(result.completeness, result.relevance, result.accuracy),
            "current_phase": AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.CRITIQUING.value,
                    content=f"质量评审通过: {critic_feedback}",
                )
            ],
        }

    # Failed: send back for one correction pass
    logger.info(f"[CriticNode] ❌ Failed: {critic_feedback}")
    iteration = state.get("iteration", 0)
    guidance = (
        f"## Critic 评审未通过\n"
        f"**评分**: 完整性={result.completeness:.0%} 相关性={result.relevance:.0%} 准确性={result.accuracy:.0%}\n"
        f"**改进要求**: {result.improvement_suggestion}\n"
        f"请根据以上反馈修正回复。"
    )
    return {
        "critic_passed": False,
        "critic_feedback": critic_feedback,
        "reflection_guidance": guidance,
        "needs_replanning": True,
        "iteration": iteration + 1,
        "current_phase": AgentPhase.PLANNING,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.CRITIQUING.value,
                content=f"质量评审未通过，需要修正: {result.improvement_suggestion}",
            )
        ],
    }


async def _persist_critic_score(
    state: AgentState,
    result: CriticResult,
    model_code: str = "",
) -> None:
    """Persist critic evaluation scores to agent_quality_scores table."""
    from app.core.database import supabase
    from app.core.trace_context import get_trace_id

    if not supabase:
        return

    config: AgentConfig = state["config"]
    org_id = config.org_id

    row = {
        "tenant_id": org_id if org_id and org_id != "default" else None,
        "user_id": config.user_id or None,
        "session_id": config.session_id or None,
        "trace_id": get_trace_id() or None,
        "scene_code": state.get("scene_code", ""),
        "agent_code": state.get("agent_code", ""),
        "complexity": state.get("complexity", QueryComplexity.MODERATE).value,
        "intent_summary": (state.get("intent_summary", "") or "")[:500],
        "completeness": result.completeness,
        "relevance": result.relevance,
        "accuracy": result.accuracy,
        "passed": result.passed,
        "improvement_suggestion": result.improvement_suggestion or "",
        "model_code": model_code,
        "iteration": state.get("iteration", 0),
        "response_length": len(state.get("final_response", "")),
        "tool_call_count": len(state.get("completed_tool_calls", [])),
    }

    await supabase.table("agent_quality_scores").insert(row).execute()
    logger.info(
        f"[CriticNode] Quality score persisted: "
        f"passed={result.passed} score={min(result.completeness, result.relevance, result.accuracy):.2f}"
    )
