import sys
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = ROOT / "nexus_backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.context_engine import ContextEngine, ContextProvider
from app.agent.context_ledger import ContextLedger
from app.agent.prompt_snapshot import build_prompt_snapshot
from app.services.agent_replay_harness import agent_replay_harness
from app.services.agent_cost_attribution import build_cost_attribution
from app.services.context_ablation_service import context_ablation_service
from app.services.eval_case_promotion_service import (
    EvalCasePromotionService,
    redact_eval_text,
)
from app.services.prompt_linter import prompt_linter
from evals.evaluators.agent_replay import AgentReplayEvaluator


class _Provider(ContextProvider):
    name = "fixture"
    priority = 10

    def __init__(self, text: str, max_tokens: int = 100):
        self.text = text
        self._max_tokens = max_tokens

    def max_tokens(self) -> int:
        return self._max_tokens

    async def get_context(self, user_id: str, org_id: str | None, query: str, **kwargs):
        return self.text


def test_prompt_snapshot_flags_duplicate_and_mojibake():
    messages = [
        SystemMessage(content="[policy]\nkeep data safe"),
        SystemMessage(content="[policy]\nkeep data safe"),
        HumanMessage(content="mojibake marker: 鈥"),
    ]
    snapshot = build_prompt_snapshot(messages, prompt_version="test", max_total_tokens=10_000)
    assert snapshot.fingerprint
    assert any("duplicates" in warning for warning in snapshot.warnings)
    assert any("mojibake" in warning for warning in snapshot.warnings)


@pytest.mark.asyncio
async def test_context_engine_records_ledger_without_mutating_global_budget():
    engine = ContextEngine(total_budget=120)
    engine.register(_Provider("hello world " * 20, max_tokens=30))
    ledger = ContextLedger(request_id="req-1")

    context = await engine.build_context(
        user_id="u1",
        org_id="o1",
        query="hello",
        context_window=1000,
        context_ledger=ledger,
    )

    assert "fixture" in context
    assert ledger.total_budget == engine.adjust_budget_for_model(1000)
    assert engine._total_budget == 120
    assert ledger.entries
    assert ledger.entries[0].included is True
    assert ledger.entries[0].truncated_reason == "provider_budget"


def test_frontend_prompt_file_is_not_backend_mirror():
    content = (ROOT / "src/services/agentPrompts.ts").read_text(encoding="utf-8")
    assert "mirror_backend_prompts" not in content
    assert "BACKEND_PROMPT_MANIFEST_ENDPOINT" in content
    assert "enhanced direct fallback" not in content.lower()
    assert "只能基于本条消息和下方业务数据快照做分析" in content


def test_runtime_prompt_registry_is_utf8_clean():
    from app.core.prompts_registry import SYSTEM_PROMPTS, get_prompt_manifest

    manifest = get_prompt_manifest()
    assert manifest["frontend_policy"]["direct_mode"] == "minimal_read_only_fallback"
    assert manifest["system_prompts"]
    lint = prompt_linter.lint_registry()
    assert lint["error_count"] == 0
    assert all("鈥" not in text for text in SYSTEM_PROMPTS.values())


def test_agent_replay_harness_asserts_trace_contract():
    trace = {
        "total_tokens": 100,
        "total_duration_ms": 500,
        "final_response": "已找到客户 A",
        "steps": [
            {"node_type": "router"},
            {"node_type": "plan"},
            {"node_type": "execute", "tool_calls": [{"name": "get_customer"}]},
            {"node_type": "respond"},
        ],
    }
    result = agent_replay_harness.evaluate_trace(
        trace,
        {
            "expected_nodes": ["router", "plan", "execute", "respond"],
            "expected_tools": ["get_customer"],
            "final_contains": ["客户 A"],
            "max_tokens": 500,
        },
    )
    assert result.passed
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_agent_replay_evaluator_uses_real_harness():
    evaluator = AgentReplayEvaluator()
    result = await evaluator.evaluate(
        {
            "id": "case-1",
            "cassette": {
                "final_response": "早，有什么事？",
                "steps": [{"node_type": "router"}, {"node_type": "respond"}],
            },
            "expectations": {
                "expected_nodes": ["router", "respond"],
                "forbidden_tools": ["delete_customer"],
                "final_contains": ["早"],
            },
        }
    )
    assert result.passed
    assert result.details["passed"] is True


def test_failure_log_promotion_redacts_and_builds_pending_case():
    service = EvalCasePromotionService()
    assert "[PHONE]" in redact_eval_text("联系 13800138000")
    case = service.build_case_from_failure(
        {
            "organization_id": "org-1",
            "user_message": "帮我查 13800138000 的审批",
            "error_type": "wrong_tool",
            "error_detail": "picked wrong tool",
            "pattern_key": "wrong_tool:unknown",
        }
    )
    row = case.to_row()
    assert row["status"] == "pending_label"
    assert row["dimension"] == "tool_selection"
    assert "[PHONE]" in row["input_json"]["query"]


def test_cost_attribution_and_context_ablation():
    snapshot = {
        "total_tokens_estimated": 100,
        "blocks": [
            {"block_name": "system", "role": "system", "tokens_estimated": 60},
            {"block_name": "user", "role": "human", "tokens_estimated": 40},
        ],
    }
    ledger = {
        "used_tokens": 50,
        "entries": [
            {"provider": "business_rules", "included": True, "tokens_estimated": 30},
            {"provider": "chat_history", "included": True, "tokens_estimated": 20},
        ],
    }
    attribution = build_cost_attribution(
        prompt_snapshot=snapshot,
        context_ledger=ledger,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.03,
    )
    assert attribution["prompt_blocks"][0]["input_cost_usd_est"] > 0
    ablation = context_ablation_service.analyze_ledger(ledger)
    assert ablation["ablations"][0]["provider"] == "business_rules"
