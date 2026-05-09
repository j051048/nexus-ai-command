"""Token and cost attribution for Agent prompt/context blocks."""

from __future__ import annotations

from typing import Any


def build_cost_attribution(
    *,
    prompt_snapshot: dict[str, Any] | None,
    context_ledger: dict[str, Any] | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> dict[str, Any]:
    """Allocate input token/cost share across prompt blocks and context providers.

    This is attribution, not billing truth. Billing truth remains provider usage;
    attribution explains where the budget went.
    """
    prompt_snapshot = prompt_snapshot or {}
    context_ledger = context_ledger or {}
    total_tokens = max(input_tokens + output_tokens, 1)
    input_cost = cost_usd * (input_tokens / total_tokens)
    output_cost = cost_usd * (output_tokens / total_tokens)

    blocks = []
    prompt_tokens = max(int(prompt_snapshot.get("total_tokens_estimated") or 0), 1)
    for block in prompt_snapshot.get("blocks") or []:
        tokens = int(block.get("tokens_estimated") or 0)
        share = tokens / prompt_tokens
        blocks.append(
            {
                "block_name": block.get("block_name"),
                "role": block.get("role"),
                "tokens": tokens,
                "input_cost_usd_est": round(input_cost * share, 8),
                "mojibake_risk": bool(block.get("mojibake_risk")),
            }
        )

    providers = []
    context_tokens = max(int(context_ledger.get("used_tokens") or 0), 1)
    for entry in context_ledger.get("entries") or []:
        if not entry.get("included"):
            continue
        tokens = int(entry.get("tokens_estimated") or 0)
        share = tokens / context_tokens
        providers.append(
            {
                "provider": entry.get("provider"),
                "tokens": tokens,
                "input_cost_usd_est": round(input_cost * share, 8),
                "truncated_reason": entry.get("truncated_reason"),
                "pii_level": entry.get("pii_level"),
            }
        )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": round(cost_usd, 8),
        "input_cost_usd_est": round(input_cost, 8),
        "output_cost_usd_est": round(output_cost, 8),
        "prompt_blocks": blocks,
        "context_providers": providers,
    }
