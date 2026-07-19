"""Evidence-grounded solution generation and deterministic quality checks."""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from typing import Any
from xml.sax.saxutils import escape

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.llm_gateway import llm_gateway

WORKSPACE_SCHEMA_VERSION = "solution-workspace.v1"
STAGES = ["brief", "requirements", "configuration", "draft", "review", "delivery"]


def build_initial_workspace(brief: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "active_stage": "brief",
        "brief": brief,
        "requirements": [],
        "packages": [],
        "sections": [],
        "review_gates": [
            {"id": "budget", "label": "预算范围已核对", "passed": False},
            {"id": "evidence", "label": "关键参数有企业资料依据", "passed": False},
            {"id": "claims", "label": "外部承诺已由负责人确认", "passed": False},
        ],
        "artifacts": [],
        "generation": {},
        "extension_data": {"output_connectors": [], "template_id": None},
    }


def apply_template_structure(
    workspace: dict[str, Any], template_structure: dict[str, Any]
) -> dict[str, Any]:
    """Reuse approved structure without carrying customer-specific approvals."""
    requirements = [
        {**item, "status": "open"}
        for item in template_structure.get("requirements") or []
        if isinstance(item, dict)
    ]
    sections = [
        {**item, "status": "draft"}
        for item in template_structure.get("sections") or []
        if isinstance(item, dict)
    ]
    review_gates = [
        {**item, "passed": False}
        for item in template_structure.get("review_gates") or []
        if isinstance(item, dict)
    ]
    templated = {
        **workspace,
        "requirements": requirements,
        "packages": [
            item
            for item in template_structure.get("packages") or []
            if isinstance(item, dict)
        ],
        "sections": sections,
        "review_gates": review_gates or workspace["review_gates"],
    }
    templated["quality"] = validate_workspace(templated)
    return templated


def _parse_json_object(content: str) -> dict[str, Any] | None:
    cleaned = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _fallback_draft(
    brief: dict[str, Any], products: list[dict[str, Any]]
) -> dict[str, Any]:
    budget_min = brief.get("budget_min")
    budget_max = brief.get("budget_max")
    budget_text = "预算待确认"
    if budget_min is not None or budget_max is not None:
        budget_text = f"预算范围：{budget_min or 0:,.0f} - {budget_max or 0:,.0f} 元"
    product_names = [
        item.get("model_code") or item.get("product_name") for item in products[:6]
    ]
    product_names = [name for name in product_names if name]
    requirements = [
        {
            "id": "req-1",
            "title": brief.get("application_scenario") or "明确应用目标与样品类型",
            "priority": "must",
            "status": "open",
            "evidence_ref": None,
        },
        {
            "id": "req-2",
            "title": budget_text,
            "priority": "must",
            "status": "open",
            "evidence_ref": None,
        },
        {
            "id": "req-3",
            "title": "确认安装环境、交付周期与验收标准",
            "priority": "should",
            "status": "open",
            "evidence_ref": None,
        },
    ]
    packages = []
    for key, name, positioning in [
        ("essential", "基础方案", "满足核心检测与合规要求"),
        ("recommended", "推荐方案", "兼顾性能、扩展性与全生命周期成本"),
        ("advanced", "进阶方案", "面向高通量、自动化与未来扩展"),
    ]:
        packages.append(
            {
                "id": key,
                "name": name,
                "positioning": positioning,
                "product_models": product_names[:2],
                "components": ["主机配置待选型", "安装培训", "基础应用支持"],
                "rationale": "需结合企业知识库中的产品参数进一步核验。",
                "tradeoffs": ["具体参数与价格待人工确认"],
            }
        )
    sections = [
        {
            "id": "summary",
            "title": "方案摘要",
            "content": f"面向{brief.get('customer_name') or '目标客户'}的{brief.get('application_scenario') or '科学仪器应用'}需求，提供分层配置建议。",
            "evidence_refs": [],
            "status": "draft",
        },
        {
            "id": "needs",
            "title": "需求理解",
            "content": "当前信息不足的项目已标记为待核验，建议在正式外发前完成技术澄清。",
            "evidence_refs": [],
            "status": "draft",
        },
        {
            "id": "delivery",
            "title": "交付与服务",
            "content": "交付周期、安装条件、培训范围与验收口径均需由业务负责人确认。",
            "evidence_refs": [],
            "status": "draft",
        },
    ]
    return {"requirements": requirements, "packages": packages, "sections": sections}


def validate_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
    requirements = workspace.get("requirements") or []
    packages = workspace.get("packages") or []
    sections = workspace.get("sections") or []
    review_gates = workspace.get("review_gates") or []
    evidence_count = sum(len(item.get("evidence_refs") or []) for item in sections)
    open_claims = sum(
        1
        for item in requirements
        if item.get("priority") == "must"
        and (
            item.get("status") != "verified"
            or not str(item.get("evidence_ref") or "").strip()
        )
    )
    checks = {
        "has_brief": bool((workspace.get("brief") or {}).get("title")),
        "has_requirements": bool(requirements),
        "has_three_packages": len(packages) >= 3,
        "has_draft": bool(sections),
        "sections_approved": bool(sections)
        and all(item.get("status") == "approved" for item in sections),
        "has_evidence": evidence_count > 0,
        "must_requirements_verified": open_claims == 0,
        "review_gates_passed": bool(review_gates)
        and all(bool(item.get("passed")) for item in review_gates),
    }
    return {
        "checks": checks,
        "ready_for_external_use": all(checks.values()),
        "evidence_count": evidence_count,
        "open_claims": open_claims,
        "completion": round(sum(checks.values()) / len(checks) * 100),
    }


async def generate_solution(
    *,
    brief: dict[str, Any],
    current_workspace: dict[str, Any],
    products: list[dict[str, Any]],
    knowledge_context: str,
    template: dict[str, Any] | None,
    user_id: str,
    organization_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_context = knowledge_context[:12000]
    product_context = json.dumps(products[:12], ensure_ascii=False, default=str)[:8000]
    template_context = json.dumps(template or {}, ensure_ascii=False, default=str)[
        :5000
    ]
    system_prompt = """你是科学仪器企业的资深售前方案架构师，覆盖光谱、色谱、质谱、能谱及电子测试仪器。
只允许依据输入的客户事实、产品目录和企业知识资料写作。不得虚构参数、资质、交付周期、价格或客户案例；证据不足时明确写“待核验”。
输出严格 JSON 对象，字段仅包含 requirements、packages、sections。packages 必须提供基础、推荐、进阶三档；sections 中每段必须有 evidence_refs 数组。
外发、报价和承诺均由人工确认，本次只生成可编辑草稿。"""
    prompt = {
        "brief": brief,
        "existing_workspace": current_workspace,
        "product_catalog": product_context,
        "enterprise_knowledge": source_context,
        "approved_template": template_context,
        "output_schema": {
            "requirements": [
                {
                    "id": "req-1",
                    "title": "",
                    "priority": "must|should|optional",
                    "status": "open",
                    "evidence_ref": "资料名或null",
                }
            ],
            "packages": [
                {
                    "id": "essential|recommended|advanced",
                    "name": "",
                    "positioning": "",
                    "product_models": [],
                    "components": [],
                    "rationale": "",
                    "tradeoffs": [],
                }
            ],
            "sections": [
                {
                    "id": "",
                    "title": "",
                    "content": "",
                    "evidence_refs": [],
                    "status": "draft",
                }
            ],
        },
    }
    response = await llm_gateway.chat(
        scene_code="solution_design",
        agent_code="scientific_solution_architect",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=system_prompt,
        messages=[
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False, default=str),
            }
        ],
        temperature=0.2,
        max_tokens=3200,
    )
    generated = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    degraded = generated is None
    generated = generated or _fallback_draft(brief, products)
    workspace = {
        **current_workspace,
        **generated,
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "active_stage": "review",
        "generation": {
            "generated_at": datetime.now(UTC).isoformat(),
            "model": response.model_code,
            "usage": response.usage,
            "degraded": degraded,
            "knowledge_context_available": bool(knowledge_context),
        },
    }
    workspace["quality"] = validate_workspace(workspace)
    return workspace, workspace["generation"]


def workspace_markdown(project: dict[str, Any]) -> str:
    workspace = project.get("workspace") or {}
    lines = [f"# {project.get('title') or '客户解决方案'}", ""]
    brief = workspace.get("brief") or {}
    lines.extend(
        [
            f"客户：{brief.get('customer_name') or '待确认'}",
            f"行业/地区：{brief.get('industry') or '待确认'} / {brief.get('region') or '待确认'}",
            "",
        ]
    )
    for section in workspace.get("sections") or []:
        lines.extend(
            [
                f"## {section.get('title') or '未命名章节'}",
                section.get("content") or "",
                "",
            ]
        )
        refs = section.get("evidence_refs") or []
        if refs:
            lines.extend([f"证据：{', '.join(map(str, refs))}", ""])
    lines.extend(["## 配置建议", ""])
    for package in workspace.get("packages") or []:
        lines.extend(
            [f"### {package.get('name')}", package.get("positioning") or "", ""]
        )
        for component in package.get("components") or []:
            lines.append(f"- {component}")
        lines.append("")
    lines.append("> 本文档为 AI 辅助草稿，参数、价格、交期与外部承诺须经人工审核。")
    return "\n".join(lines)


def export_docx(project: dict[str, Any]) -> bytes:
    markdown = workspace_markdown(project)
    document = Document()
    for line in markdown.splitlines():
        if line.startswith("### "):
            document.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            document.add_heading(line[2:], level=1)
        elif line.startswith("- "):
            document.add_paragraph(line[2:], style="List Bullet")
        elif line.startswith("> "):
            document.add_paragraph(line[2:])
        else:
            document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def export_pdf(project: dict[str, Any]) -> bytes:
    buffer = io.BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "STSong-Light"
    story = []
    for line in workspace_markdown(project).splitlines():
        if not line:
            story.append(Spacer(1, 3 * mm))
            continue
        if line.startswith("# "):
            story.append(Paragraph(escape(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
        elif line.startswith("### "):
            story.append(Paragraph(escape(line[4:]), styles["Heading3"]))
        else:
            story.append(Paragraph(escape(line.lstrip("- >")), styles["BodyText"]))
    SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm
    ).build(story)
    return buffer.getvalue()
