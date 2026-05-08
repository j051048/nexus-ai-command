"""Deterministic multi-model routing policy and A/B guardrails."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingDecision:
    model_code: str
    changed: bool
    reason: str
    bucket: int


def _stable_bucket(*parts: str) -> int:
    raw = "::".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return int(digest[:8], 16) % 100


def choose_model_variant(
    *,
    primary_model: str,
    scene_code: str,
    agent_code: str,
    org_id: str,
    user_id: str,
    estimated_tokens: int,
    has_tools: bool,
) -> RoutingDecision:
    """Optionally route low-risk calls to an A/B economy model.

    Disabled by default. Set LLM_ENABLE_AB_ROUTING=true and
    LLM_AB_ECONOMY_MODEL=<configured model_code> to activate.
    """
    bucket = _stable_bucket(org_id, user_id, scene_code, agent_code)
    if os.getenv("LLM_ENABLE_AB_ROUTING", "false").lower() != "true":
        return RoutingDecision(primary_model, False, "ab_routing_disabled", bucket)

    economy_model = os.getenv("LLM_AB_ECONOMY_MODEL", "").strip()
    percent = int(os.getenv("LLM_AB_ECONOMY_PERCENT", "0") or "0")
    percent = max(0, min(100, percent))

    if not economy_model or economy_model == primary_model:
        return RoutingDecision(primary_model, False, "no_economy_variant", bucket)
    if bucket >= percent:
        return RoutingDecision(primary_model, False, "outside_ab_bucket", bucket)
    if has_tools or estimated_tokens > int(os.getenv("LLM_AB_MAX_TOKENS", "6000")):
        return RoutingDecision(primary_model, False, "risk_or_context_too_high", bucket)

    return RoutingDecision(economy_model, True, "ab_economy_variant", bucket)
