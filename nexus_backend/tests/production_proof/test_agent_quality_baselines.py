from __future__ import annotations


def _baseline_intent(text: str) -> str:
    lowered = text.lower()
    if any(
        token in lowered
        for token in ("approval", "approve", "reject", "reimbursement")
    ):
        return "approval_decision"
    if any(token in lowered for token in ("tender", "rfp", "score criteria")):
        return "tender_support"
    if any(
        token in lowered
        for token in ("battlecard", "thermo", "agilent", "shimadzu", "compare")
    ):
        return "battlecard"
    if any(token in lowered for token in ("contract", "renewal", "expire")):
        return "renewal_or_contract"
    if any(token in lowered for token in ("crm", "customer", "lead", "follow-up", "visit")):
        return "crm_followup"
    return "general_assistant"


def test_classifier_accuracy_baseline_has_ci_threshold(intent_baseline):
    correct = sum(
        1
        for item in intent_baseline
        if _baseline_intent(item["text"]) == item["expected_intent"]
    )
    accuracy = correct / len(intent_baseline)
    assert accuracy >= 0.90


def test_llm_replay_cassette_has_tool_and_answer_expectations(llm_replay_cassette):
    assert llm_replay_cassette["cassette_version"]
    for case in llm_replay_cassette["cases"]:
        assert case["expected_tool_calls"]
        assert case["recorded_response"]["tool_calls"]
        assert case["recorded_response"]["answer_contains"]


def test_agent_eval_dataset_is_large_and_balanced(agent_eval_cases_200):
    assert len(agent_eval_cases_200) >= 200
    intents = {case["expected_intent"] for case in agent_eval_cases_200}
    critical_cases = [
        case for case in agent_eval_cases_200 if case["criticality"] == "critical"
    ]
    assert {
        "crm_followup",
        "approval_decision",
        "tender_support",
        "battlecard",
        "renewal_or_contract",
        "knowledge_search",
        "vmd_campaign",
    }.issubset(intents)
    assert len(critical_cases) >= 40
    for case in agent_eval_cases_200:
        assert case["id"]
        assert case["text"]
        assert case["expected_intent"]
        assert "respects_tenant_context" in case["assertions"]


def test_agent_eval_dataset_runs_against_operating_system_router(agent_eval_cases_200):
    from app.services.agent_eval_baseline_service import agent_eval_baseline_service

    router_supported = {
        "approval_decision",
        "battlecard",
        "crm_followup",
        "renewal_or_contract",
        "tender_support",
        "general_assistant",
    }
    cases = [
        case
        for case in agent_eval_cases_200
        if case["expected_intent"] in router_supported
    ][:120]
    result = agent_eval_baseline_service.run_router_baseline(cases)
    assert result["case_count"] >= 70
    assert result["accuracy"] >= 0.70
