"""
Graph Node: parallel_context_and_plan — runs RAG retrieval and planning concurrently.

Optimization for COMPLEX/CRITICAL queries when LANGGRAPH_ENABLE_RAG_INJECT is True.
Instead of sequential RAG → Plan, both run in parallel via asyncio.gather(),
saving ~40% latency on the critical path.
"""

import asyncio
import logging

from langchain_core.runnables import RunnableConfig

from app.agent.node_plan import plan_node
from app.agent.state import AgentPhase, AgentState, ThinkingStep

logger = logging.getLogger(__name__)


async def _retrieve_rag_context(state: AgentState) -> dict:
    """
    Perform RAG retrieval for the current query.
    Returns a dict with rag_context and rag_sources to merge into state.
    """
    config = state.get("config")
    if not config or not config.enable_rag_inject:
        return {"rag_context": "", "rag_sources": []}

    # Extract last user message
    last_user_msg = ""
    for msg in reversed(state.get("messages", [])):
        content = ""
        if hasattr(msg, "content"):
            content = msg.content
        elif isinstance(msg, dict):
            content = msg.get("content", "")
        msg_type = getattr(msg, "type", None) or (
            msg.get("role") if isinstance(msg, dict) else None
        )
        if msg_type in ("human", "user"):
            last_user_msg = content
            break

    if not last_user_msg:
        return {"rag_context": "", "rag_sources": []}

    try:
        from app.agent.artifact_contract import infer_artifact_spec
        from app.agent.scientific_writing_skills import enrich_artifact_spec
        from app.services.agent_evidence_service import retrieve_agent_evidence

        spec = enrich_artifact_spec(
            state.get("artifact_spec") or infer_artifact_spec(last_user_msg)
        )
        packet = await retrieve_agent_evidence(
            query=last_user_msg,
            config=config,
            artifact_spec=spec,
        )
        if packet.prompt_context:
            logger.info(
                "[ParallelContext] evidence records=%d coverage=%.2f",
                len(packet.records),
                packet.coverage,
            )
        return {
            "rag_context": packet.prompt_context,
            "rag_sources": [record.title for record in packet.records],
            "evidence_packet": packet.model_dump(mode="json"),
        }
    except Exception as e:
        logger.warning(f"[ParallelContext] RAG retrieval failed: {e}")

    return {"rag_context": "", "rag_sources": []}


async def parallel_context_and_plan(
    state: AgentState, config: RunnableConfig | None = None
) -> dict:
    """
    Run RAG context retrieval in parallel with LLM planning.

    Strategy:
    1. If state already has rag_context (from prepare_initial_state), skip retrieval
    2. Otherwise, run retrieval concurrently with plan_node
    3. Merge the RAG context into the plan result before returning

    This saves latency by overlapping the RAG vector search (~200-500ms)
    with the LLM planning call (~1-3s).
    """
    existing_rag = state.get("rag_context", "")
    iteration = state.get("iteration", 0)

    # Only do parallel retrieval on first iteration and when no RAG context exists
    if existing_rag or iteration > 0:
        # Already have context or re-planning — just run plan_node directly
        return await plan_node(state, config)

    agent_config = state.get("config")
    if not agent_config or not agent_config.enable_rag_inject:
        # RAG not enabled — just run plan_node directly
        return await plan_node(state, config)

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content="正在并行执行 RAG 检索与 LLM 规划...",
    )

    try:
        from app.agent.artifact_contract import is_strict_artifact

        # External deliverables must plan from the retrieved evidence, so their
        # first pass is intentionally sequential. Ordinary chat keeps the
        # latency-optimized parallel path.
        if is_strict_artifact(state.get("artifact_spec")):
            rag_result = await _retrieve_rag_context(state)
            planning_state = {**state, **rag_result}
            plan_result = await plan_node(planning_state, config)
            return {
                **rag_result,
                **plan_result,
                "thinking_steps": [thinking_step]
                + plan_result.get("thinking_steps", []),
            }

        # Run both in parallel
        rag_task = asyncio.create_task(_retrieve_rag_context(state))
        plan_task = asyncio.create_task(plan_node(state, config))

        rag_result, plan_result = await asyncio.gather(
            rag_task, plan_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(plan_result, Exception):
            logger.error(f"[ParallelContext] Plan failed: {plan_result}")
            raise plan_result

        if isinstance(rag_result, Exception):
            logger.warning(f"[ParallelContext] RAG failed (non-fatal): {rag_result}")
            rag_result = {"rag_context": "", "rag_sources": []}

        # Merge RAG context into plan result if retrieval found something
        rag_context = rag_result.get("rag_context", "")
        if rag_context and not plan_result.get("rag_context"):
            plan_result["rag_context"] = rag_context
            logger.info(
                f"[ParallelContext] Injected {len(rag_context)} chars of RAG context "
                f"from parallel retrieval"
            )
        if rag_result.get("evidence_packet"):
            plan_result["evidence_packet"] = rag_result["evidence_packet"]
            plan_result["rag_sources"] = rag_result.get("rag_sources", [])

        # Add parallel execution thinking step
        existing_steps = plan_result.get("thinking_steps", [])
        plan_result["thinking_steps"] = [thinking_step] + existing_steps

        return plan_result

    except Exception as e:
        logger.error(
            f"[ParallelContext] Parallel execution failed, falling back to sequential: {e}"
        )
        # Fallback: run plan_node sequentially
        return await plan_node(state, config)
