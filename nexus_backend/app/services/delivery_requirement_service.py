"""Deterministic acceptance checks and server-side catalog quote resolution."""

import re
from decimal import Decimal

from app.services.solution_cpq_service import build_package_quote


async def resolve_delivery_quote(db, organization_id, requirements):
    if requirements.budget is None and not requirements.catalog_quantities:
        return None
    if not requirements.catalog_quantities:
        return {
            "errors": ["预算核验需要选择已审核产品及数量"],
            "approval_required": True,
        }
    if any(
        not 1 <= quantity <= 10000
        for quantity in requirements.catalog_quantities.values()
    ):
        raise ValueError("Product quantities must be between 1 and 10000")
    products = (
        await db.table("instrument_product_catalog")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .in_("model_code", list(requirements.catalog_quantities))
        .execute()
    )
    books = (
        await db.table("solution_price_books")
        .select("id,tax_rate")
        .eq("organization_id", organization_id)
        .eq("status", "active")
        .eq("is_default", True)
        .limit(2)
        .execute()
    )
    if len(books.data or []) != 1:
        return {"errors": ["请先确认唯一的默认价格册与税率"], "approval_required": True}
    book = books.data[0]
    if book.get("tax_rate") is None:
        return {"errors": ["默认价格册未设置税率"], "approval_required": True}
    items = (
        await db.table("solution_price_book_items")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("price_book_id", book["id"])
        .execute()
    )
    # No model-supplied prices, discounts or quote totals are accepted here.
    quote = build_package_quote(
        {
            "line_items": [
                {"model_code": model, "quantity": quantity}
                for model, quantity in requirements.catalog_quantities.items()
            ]
        },
        products.data or [],
        price_book_items=items.data or [],
        tax_rate=book["tax_rate"],
    )
    if any(line["unit_price"] <= 0 for line in quote["line_items"]):
        quote["errors"].append("产品价格缺失或无效，不能作为零元报价")
    quote["valid"] = not quote["errors"]
    quote["price_book_id"] = book["id"]
    quote["budget_basis"] = "tax_inclusive_catalog_quote"
    return quote


def evaluate_delivery_requirements(text, spec, evidence_packet):
    requirements = spec.delivery_requirements
    records = (evidence_packet or {}).get("records") or []
    findings = []
    checks = []

    def fail(code, message, *, repairable=False):
        findings.append(
            {
                "severity": "high",
                "code": code,
                "message": message,
                "repairable": repairable,
            }
        )

    for fact in requirements.required_facts:
        supporting = [
            row
            for row in records
            if fact.expected_text in str(row.get("excerpt") or "")
        ]
        cited_ids = {
            f"[EVID:{row.get('document_id')}:{row.get('chunk_id')}]"
            for row in supporting
        }
        paragraphs = re.split(r"\n\s*\n", text)
        covered = any(
            fact.expected_text in paragraph
            and (
                not fact.evidence_required or any(ref in paragraph for ref in cited_ids)
            )
            for paragraph in paragraphs
        )
        checks.append(
            {
                "topic": fact.topic,
                "covered": covered,
                "source_ids": [row.get("document_id") for row in supporting],
            }
        )
        if not covered:
            fail(
                "delivery_requirement_unverified",
                f"关键要求未获正文与证据共同支持：{fact.topic}",
                repairable=bool(supporting) or not fact.evidence_required,
            )
    for phrase in requirements.forbidden_claims:
        if phrase.strip() and phrase in text:
            fail(
                "delivery_forbidden_claim",
                f"包含禁止使用的承诺：{phrase}",
                repairable=True,
            )
    if requirements.budget is not None or requirements.catalog_quantities:
        quote = spec.commercial_quote or {}
        if (
            quote.get("errors")
            or quote.get("total") is None
            or quote.get("approval_required")
        ):
            fail(
                "delivery_quote_unverified", "预算或商务条件尚未通过产品目录与报价核验"
            )
        elif quote.get("currency") != requirements.currency:
            fail("delivery_currency_mismatch", "预算与报价币种不一致")
        elif (
            requirements.budget is not None
            and Decimal(str(quote["total"])) > requirements.budget
        ):
            fail("delivery_budget_exceeded", "所选配置超过客户预算，请调整配置")
    return {"checks": checks, "findings": findings}
