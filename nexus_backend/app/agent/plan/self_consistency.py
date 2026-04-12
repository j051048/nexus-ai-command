"""CRITICAL-level multi-sample self-consistency voting."""

import asyncio
from collections import Counter

from langchain_openai import ChatOpenAI

from app.agent.node_helpers import logger


def _tool_signature(msg) -> str:
    """Build a signature from tool names + arg key sets for parameter-aware voting.

    Example: "search_leads(keywords,region)|update_lead(lead_id,stage)"
    Only arg *keys* are compared (not values) to avoid over-fragmentation.
    """
    calls = getattr(msg, "tool_calls", None) or []
    parts: list[str] = []
    for tc in calls:
        if isinstance(tc, dict):
            name = tc.get("name", "")
            args = tc.get("args", {})
        else:
            name = getattr(tc, "name", "")
            args = getattr(tc, "args", {})
        arg_keys = ",".join(sorted(args.keys())) if isinstance(args, dict) else ""
        parts.append(f"{name}({arg_keys})")
    parts.sort()
    return "|".join(parts) if parts else "__no_tools__"


async def plan_with_self_consistency(
    lc_msgs: list,
    config: "AgentConfig",  # noqa: F821
    model: str | None,
    tool_schemas: list | None,
    resolved_config: dict | None = None,
    n: int = 3,
):
    """CRITICAL 查询多次采样 + 工具组合投票，选最一致的方案。

    使用 temperature=0.7 多次调用，提取每次的 tool_calls 列表，
    用 Counter 投票选工具组合一致性最高的方案。

    Returns: (best_sample, candidate_plans) where candidate_plans is a list
    of scored alternatives for Tree-of-Thought backtracking.
    """

    async def _single_sample(i: int):
        """Single sampling call for parallel execution."""
        sample_llm = ChatOpenAI(
            model=(resolved_config or {}).get("model") or model or config.model,
            api_key=(resolved_config or {}).get("api_key") or config.api_key,
            base_url=(resolved_config or {}).get("base_url") or config.base_url,
            temperature=0.7,
            streaming=False,
            timeout=30.0,
        )
        if tool_schemas:
            sample_llm = sample_llm.bind_tools(tool_schemas, parallel_tool_calls=True)
        return await asyncio.wait_for(sample_llm.ainvoke(lc_msgs), timeout=30)

    # Parallel sampling via asyncio.gather
    results = await asyncio.gather(
        *[_single_sample(i) for i in range(n)],
        return_exceptions=True,
    )
    samples = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error(f"[SelfConsistency] Sample {i+1}/{n} failed: {r}")
        else:
            samples.append(r)

    if not samples:
        return None, []  # 全部失败，退回单次调用

    # 按工具组合签名投票
    sigs = [_tool_signature(s) for s in samples]
    counter = Counter(sigs)
    best_sig, best_count = counter.most_common(1)[0]

    # Build scored candidate list for ToT backtracking (top-2, excluding winner)
    candidate_plans = []
    for sig, count in counter.most_common():
        if sig == best_sig:
            continue  # Winner goes directly as return value
        # Find first sample with this signature
        for s, s_sig in zip(samples, sigs, strict=False):
            if s_sig == sig:
                candidate_plans.append(
                    {
                        "sig": sig,
                        "score": count / n,
                        "tool_calls": [
                            {
                                "name": (
                                    tc.get("name", "")
                                    if isinstance(tc, dict)
                                    else getattr(tc, "name", "")
                                ),
                                "args": (
                                    tc.get("args", {})
                                    if isinstance(tc, dict)
                                    else getattr(tc, "args", {})
                                ),
                            }
                            for tc in (getattr(s, "tool_calls", None) or [])
                        ],
                        "content": s.content or "",
                    }
                )
                break
    # Keep at most 1 alternative (top-2 total: winner + 1 backup)
    candidate_plans = candidate_plans[:1]

    # 选该签名的第一个样本
    for s, sig in zip(samples, sigs, strict=False):
        if sig == best_sig:
            # Aggregate token usage from all samples for accurate tracking
            total_sc_input = sum(
                (getattr(r, "response_metadata", {}) or {})
                .get("token_usage", {})
                .get("prompt_tokens", 0)
                for r in samples
            )
            total_sc_output = sum(
                (getattr(r, "response_metadata", {}) or {})
                .get("token_usage", {})
                .get("completion_tokens", 0)
                for r in samples
            )
            s._sc_total_input_tokens = total_sc_input
            s._sc_total_output_tokens = total_sc_output
            logger.info(
                f"[SelfConsistency] Selected: {best_sig} (votes: {best_count}/{n}), "
                f"alternatives: {len(candidate_plans)}"
            )
            return s, candidate_plans

    return samples[0], []
