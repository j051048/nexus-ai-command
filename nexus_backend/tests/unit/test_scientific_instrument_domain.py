from app.services.scientific_instrument_domain import (
    INSTRUMENT_DOMAIN_VERSION,
    build_instrument_context,
    instrument_domain_catalog,
    normalize_instrument_line,
)


def test_domain_catalog_exposes_exactly_five_supported_instrument_lines():
    catalog = instrument_domain_catalog()
    lines = catalog["instrument_lines"]

    assert catalog["domain_version"] == INSTRUMENT_DOMAIN_VERSION
    assert [line["code"] for line in lines] == [
        "spectroscopy",
        "chromatography",
        "mass_spectrometry",
        "energy_spectroscopy",
        "electronic_instrumentation",
    ]
    assert all(line["evidence_requirements"] for line in lines)
    assert all(line["tender_focus"] for line in lines)


def test_domain_context_translates_chinese_alias_and_preserves_business_context():
    context = build_instrument_context(
        "质谱",
        application_field="环境痕量检测",
        product_models=["ICP-MS 9000"],
    )

    assert normalize_instrument_line("质谱") == "mass_spectrometry"
    assert context["classification_status"] == "classified"
    assert context["instrument_line_name"] == "质谱"
    assert context["application_field"] == "环境痕量检测"
    assert context["product_models"] == ["ICP-MS 9000"]
    assert "灵敏度与质量精度" in context["evidence_requirements"]


def test_unknown_line_is_explicitly_unclassified():
    context = build_instrument_context("microscopy")

    assert context["classification_status"] == "unclassified"
    assert context["instrument_line_code"] is None
