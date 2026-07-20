from app.services.solution_commercial_service import (
    enrich_workspace_commercials,
    extract_requirement_candidates,
    solution_value_metrics,
)


def _workspace(models):
    return {
        "packages": [
            {
                "id": "recommended",
                "name": "推荐方案",
                "product_models": models,
            }
        ],
        "extension_data": {},
    }


def test_verified_catalog_products_are_priced_without_llm_calls():
    result = enrich_workspace_commercials(
        _workspace(["LC-100", "AS-20"]),
        [
            {
                "model_code": "LC-100",
                "validation_status": "verified",
                "lifecycle_status": "active",
                "list_price": 800_000,
                "standard_cost": 500_000,
                "lead_time_days": 60,
                "warranty_months": 24,
                "currency": "CNY",
            },
            {
                "model_code": "AS-20",
                "validation_status": "verified",
                "lifecycle_status": "active",
                "list_price": 200_000,
                "standard_cost": 100_000,
                "lead_time_days": 30,
                "warranty_months": 12,
                "currency": "CNY",
            },
        ],
    )

    commercial = result["packages"][0]["commercial"]
    assert commercial["list_price"] == 1_000_000
    assert commercial["standard_cost"] == 600_000
    assert commercial["gross_margin_percent"] == 40
    assert commercial["lead_time_days"] == 60
    assert result["extension_data"]["commercial_validation"]["valid"] is True


def test_unknown_or_unverified_models_block_external_commercial_validation():
    result = enrich_workspace_commercials(
        _workspace(["UNKNOWN", "MS-DRAFT"]),
        [
            {
                "model_code": "MS-DRAFT",
                "validation_status": "draft",
                "lifecycle_status": "active",
            }
        ],
    )

    validation = result["extension_data"]["commercial_validation"]
    assert validation["valid"] is False
    assert any("UNKNOWN" in item for item in validation["errors"])
    assert any("MS-DRAFT" in item for item in validation["errors"])


def test_requirement_fallback_keeps_document_trace():
    rows = extract_requirement_candidates(
        [
            {
                "id": "document-1",
                "name": "招标参数.pdf",
                "extracted_data": {
                    "full_text_context": "必须支持自动进样并提供现场验收报告。\n建议提供三年维保方案。"
                },
            }
        ]
    )

    assert rows[0]["priority"] == "must"
    assert rows[0]["source_document_id"] == "document-1"
    assert rows[0]["source_name"] == "招标参数.pdf"


def test_value_metrics_cover_win_rate_adoption_and_cost():
    metrics = solution_value_metrics(
        [
            {
                "status": "won",
                "current_version": 1,
                "workspace": {
                    "quality": {"completion": 90},
                    "generation": {"usage": {"total_tokens": 1000, "cost_usd": 0.01}},
                },
            },
            {
                "status": "lost",
                "current_version": 1,
                "workspace": {"quality": {"completion": 70}},
            },
        ],
        [{"change_type": "accepted"}, {"change_type": "edited"}],
        [{"status": "prepared"}],
    )

    assert metrics["win_rate"] == 50
    assert metrics["acceptance_rate"] == 50
    assert metrics["average_readiness"] == 80
    assert metrics["total_tokens"] == 1000
