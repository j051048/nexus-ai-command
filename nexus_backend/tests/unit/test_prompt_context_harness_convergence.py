from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.context_compiler import ContextCompilePolicy, context_compiler
from app.services.context_ablation_service import context_ablation_service
from app.services.full_graph_replay_service import full_graph_replay_service
from app.services.prompt_artifact_service import (
    PromptArtifact,
    PromptReleaseState,
    StrictPromptRenderer,
    prompt_release_gate,
)
from app.services.prompt_linter import prompt_linter
from app.services.scientific_instrument_eval_service import (
    scientific_instrument_eval_service,
)


def test_prompt_artifact_is_strict_and_content_addressed():
    artifact = PromptArtifact(
        prompt_key="calibration",
        agent_code="instrument_agent",
        version="v1",
        content="Time: {current_time}; instrument: {instrument_id}",
        variables=("current_time", "instrument_id"),
    )
    rendered = artifact.render({"current_time": "2026-07-13", "instrument_id": "LC-42"})
    assert "LC-42" in rendered
    assert len(artifact.content_hash) == 64
    with pytest.raises(ValueError, match="missing"):
        artifact.render({"current_time": "2026-07-13"})


def test_prompt_linter_rejects_undeclared_variables():
    issues = prompt_linter.lint_text(
        "Use {instrument_id} at {current_time}",
        declared_variables={"current_time"},
    )
    assert any(issue.code == "undeclared_variable" for issue in issues)
    with pytest.raises(ValueError, match="undeclared"):
        StrictPromptRenderer.render(
            "{instrument_id}", values={"instrument_id": "LC-42"}, declared_variables=()
        )


def test_prompt_release_gate_requires_ordered_passing_evidence():
    with pytest.raises(ValueError, match="offline_eval"):
        prompt_release_gate.validate_transition(
            PromptReleaseState.LINTED,
            PromptReleaseState.OFFLINE_EVAL,
            {"lint": {"passed": True}},
        )
    prompt_release_gate.validate_transition(
        PromptReleaseState.LINTED,
        PromptReleaseState.OFFLINE_EVAL,
        {"lint": {"passed": True}, "offline_eval": {"passed": True}},
    )


def test_global_context_compiler_reserves_policy_and_drops_low_utility_blocks():
    messages = [
        SystemMessage(content="[Security policy]\nNever bypass confirmation."),
        SystemMessage(content="[参考示例]\n" + "example " * 500),
        SystemMessage(
            content="[Evidence]\nsource_id: calibration-cert-42\nCertified drift: 0.2%"
        ),
        HumanMessage(content="Check calibration drift"),
    ]
    compiled, report = context_compiler.compile(
        messages,
        policy=ContextCompilePolicy(
            max_input_tokens=300,
            reserved_output_tokens=50,
            reserved_history_tokens=50,
            minimum_context_tokens=100,
        ),
    )
    contents = [str(message.content) for message in compiled]
    assert any("Security policy" in content for content in contents)
    assert any("Evidence" in content for content in contents)
    assert not any("参考示例" in content for content in contents)
    assert report.evidence_ids == ["calibration-cert-42"]
    assert report.dropped_blocks[0]["reason"] == "global_budget"


@pytest.mark.asyncio
async def test_context_ablation_executes_counterfactual_quality_runs():
    ledger = {
        "entries": [
            {"provider": "business_rules", "included": True, "tokens_estimated": 40},
            {"provider": "chat_history", "included": True, "tokens_estimated": 20},
        ]
    }

    async def evaluator(excluded: set[str]):
        penalty = 0.2 if "business_rules" in excluded else 0.0
        return {"quality_score": 0.95 - penalty, "tokens": 60 - 20 * len(excluded)}

    result = await context_ablation_service.evaluate_counterfactuals(ledger, evaluator)
    business = next(
        item
        for item in result["counterfactuals"]
        if item["provider"] == "business_rules"
    )
    assert business["quality_delta"] == -0.2
    assert business["removal_safe"] is False


@pytest.mark.asyncio
async def test_full_graph_replay_uses_executor_and_checks_side_effects_hitl_and_evidence():
    async def executor(state: dict, thread_id: str) -> dict:
        return {
            **state,
            "thinking_steps": [
                {"phase": "router"},
                {
                    "phase": "executing",
                    "tool_name": "write_calibration",
                    "tool_args": {"instrument_id": "LC-42", "coefficient": 1.2},
                    "status": "blocked",
                },
            ],
            "requires_confirmation": True,
            "final_response": "Waiting for QA confirmation.",
            "evidence_contract": {"evidence_ids": ["certificate-42"]},
            "side_effects": [],
        }

    result = await full_graph_replay_service.run_case(
        {
            "id": "calibration-hitl",
            "message": "Write calibration coefficient",
            "expectations": {
                "expected_nodes": ["router", "executing", "respond"],
                "expected_tools": ["write_calibration"],
                "expected_tool_args": {"write_calibration": {"instrument_id": "LC-42"}},
                "requires_hitl": True,
                "required_evidence_ids": ["certificate-42"],
                "forbidden_side_effects": ["instrument_write"],
                "max_errors": 0,
            },
        },
        executor=executor,
    )
    assert result["passed"] is True


def test_scientific_instrument_eval_dataset_meets_release_threshold():
    root = Path(__file__).resolve().parents[2]
    cases = json.loads(
        (root / "evals/datasets/scientific_instrument_agent_cases.json").read_text(
            encoding="utf-8"
        )
    )
    result = scientific_instrument_eval_service.evaluate(cases)
    assert result["case_count"] >= 12
    assert result["accuracy"] >= 0.95
