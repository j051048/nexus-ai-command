from app.services.solution_cpq_service import (
    build_package_quote,
    build_workspace_quotes,
)

PRODUCTS = [
    {
        "id": "p-1",
        "model_code": "LC-100",
        "product_name": "液相色谱仪",
        "validation_status": "verified",
        "lifecycle_status": "active",
        "currency": "CNY",
        "list_price": 800_000,
        "standard_cost": 500_000,
        "lead_time_days": 60,
        "warranty_months": 24,
    }
]


def test_cpq_applies_quantity_discount_tax_and_margin_without_llm():
    quote = build_package_quote(
        {
            "id": "recommended",
            "line_items": [
                {"model_code": "LC-100", "quantity": 2, "discount_percent": 5}
            ],
        },
        PRODUCTS,
        tax_rate=0.13,
    )

    assert quote["subtotal"] == 1_520_000
    assert quote["tax"] == 197_600
    assert quote["total"] == 1_717_600
    assert quote["gross_margin_percent"] == 34.21
    assert quote["lead_time_days"] == 60


def test_cpq_flags_discount_and_floor_price_for_approval():
    quote = build_package_quote(
        {
            "id": "recommended",
            "line_items": [
                {"model_code": "LC-100", "quantity": 1, "discount_percent": 20}
            ],
        },
        PRODUCTS,
        price_book_items=[
            {
                "model_code": "LC-100",
                "unit_price": 800_000,
                "floor_price": 700_000,
                "max_discount_percent": 10,
                "minimum_margin_percent": 30,
            }
        ],
    )

    assert quote["approval_required"] is True
    assert len(quote["approval_reasons"]) >= 2


def test_workspace_quote_rejects_unknown_catalog_models():
    result = build_workspace_quotes(
        {"packages": [{"id": "essential", "product_models": ["UNKNOWN"]}]},
        PRODUCTS,
    )
    assert result["valid"] is False
    assert result["quotes"][0]["errors"]
