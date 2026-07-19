from app.services.solution_workspace_service import (
    WORKSPACE_SCHEMA_VERSION,
    apply_template_structure,
    build_initial_workspace,
    export_pdf,
    validate_workspace,
    workspace_markdown,
)


def _ready_workspace():
    workspace = build_initial_workspace(
        {
            "title": "制药客户液相色谱解决方案",
            "customer_name": "华东制药实验室",
            "application_scenario": "原料药杂质检测",
        }
    )
    workspace["requirements"] = [
        {
            "id": "req-1",
            "title": "检出限满足方法要求",
            "priority": "must",
            "status": "verified",
            "evidence_ref": "产品手册第 12 页",
        }
    ]
    workspace["packages"] = [
        {"id": "essential", "name": "基础方案"},
        {"id": "recommended", "name": "推荐方案"},
        {"id": "advanced", "name": "进阶方案"},
    ]
    workspace["sections"] = [
        {
            "id": "summary",
            "title": "方案摘要",
            "content": "采用 <LC-100> 配置并由售前复核。",
            "evidence_refs": ["产品手册第 12 页"],
            "status": "approved",
        }
    ]
    workspace["review_gates"] = [
        {**gate, "passed": True} for gate in workspace["review_gates"]
    ]
    return workspace


def test_initial_workspace_is_versioned_and_requires_human_review():
    workspace = build_initial_workspace({"title": "客户方案"})

    assert workspace["schema_version"] == WORKSPACE_SCHEMA_VERSION
    assert workspace["active_stage"] == "brief"
    assert len(workspace["review_gates"]) == 3
    assert not any(gate["passed"] for gate in workspace["review_gates"])


def test_template_reuses_structure_without_reusing_customer_approvals():
    workspace = build_initial_workspace(
        {"title": "新客户方案", "customer_name": "新客户"}
    )
    templated = apply_template_structure(
        workspace,
        {
            "requirements": [
                {
                    "id": "req-1",
                    "title": "历史要求",
                    "priority": "must",
                    "status": "verified",
                }
            ],
            "packages": [{"id": "recommended", "name": "推荐方案"}],
            "sections": [{"id": "summary", "title": "摘要", "status": "approved"}],
            "review_gates": [{"id": "claims", "label": "承诺已确认", "passed": True}],
        },
    )

    assert templated["brief"]["customer_name"] == "新客户"
    assert templated["requirements"][0]["status"] == "open"
    assert templated["sections"][0]["status"] == "draft"
    assert templated["review_gates"][0]["passed"] is False


def test_external_delivery_requires_evidence_approved_sections_and_gates():
    workspace = _ready_workspace()
    assert validate_workspace(workspace)["ready_for_external_use"] is True

    workspace["requirements"][0]["evidence_ref"] = None
    assert validate_workspace(workspace)["ready_for_external_use"] is False

    workspace = _ready_workspace()
    workspace["sections"][0]["status"] = "review"
    assert validate_workspace(workspace)["checks"]["sections_approved"] is False

    workspace = _ready_workspace()
    workspace["review_gates"][0]["passed"] = False
    assert validate_workspace(workspace)["checks"]["review_gates_passed"] is False


def test_exports_keep_evidence_notice_and_escape_pdf_markup():
    project = {"title": "液相色谱 <升级> 方案", "workspace": _ready_workspace()}

    markdown = workspace_markdown(project)
    pdf = export_pdf(project)

    assert "产品手册第 12 页" in markdown
    assert "人工审核" in markdown
    assert pdf.startswith(b"%PDF")
