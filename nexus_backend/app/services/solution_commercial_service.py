"""Deterministic commercial checks for scientific-instrument solutions."""

from __future__ import annotations

import re
from typing import Any


def _money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _product_lookup(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for product in products:
        for key in (product.get("model_code"), product.get("product_name")):
            if key:
                lookup[str(key).strip().casefold()] = product
    return lookup


def _compatibility_warnings(
    selected_models: set[str], product: dict[str, Any]
) -> list[str]:
    warnings: list[str] = []
    rules = product.get("compatibility_rules") or []
    if not isinstance(rules, list):
        return warnings
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        required = {
            str(item).strip().casefold() for item in rule.get("requires", []) if item
        }
        conflicts = {
            str(item).strip().casefold()
            for item in rule.get("conflicts_with", [])
            if item
        }
        missing = required - selected_models
        collisions = conflicts & selected_models
        model = product.get("model_code") or product.get("product_name") or "unknown"
        if missing:
            warnings.append(f"{model} requires: {', '.join(sorted(missing))}")
        if collisions:
            warnings.append(f"{model} conflicts with: {', '.join(sorted(collisions))}")
    return warnings


def enrich_workspace_commercials(
    workspace: dict[str, Any], products: list[dict[str, Any]]
) -> dict[str, Any]:
    """Attach package totals and deterministic catalog validation to a workspace."""
    lookup = _product_lookup(products)
    enriched_packages: list[dict[str, Any]] = []
    workspace_errors: list[str] = []
    workspace_warnings: list[str] = []

    for package in workspace.get("packages") or []:
        models = [str(value).strip() for value in package.get("product_models") or []]
        normalized_models = {value.casefold() for value in models if value}
        selected = [lookup[value] for value in normalized_models if value in lookup]
        unknown = [value for value in models if value.casefold() not in lookup]
        prices = [_money(item.get("list_price")) for item in selected]
        costs = [_money(item.get("standard_cost")) for item in selected]
        price_known = all(value is not None for value in prices) and bool(selected)
        cost_known = all(value is not None for value in costs) and bool(selected)
        total_price = (
            round(sum(value or 0 for value in prices), 2) if price_known else None
        )
        total_cost = (
            round(sum(value or 0 for value in costs), 2) if cost_known else None
        )
        gross_margin = None
        if total_price and total_cost is not None:
            gross_margin = round((total_price - total_cost) / total_price * 100, 2)

        package_errors: list[str] = []
        package_warnings: list[str] = []
        if unknown:
            package_errors.append(f"Unknown catalog models: {', '.join(unknown)}")
        for product in selected:
            model = (
                product.get("model_code") or product.get("product_name") or "unknown"
            )
            if product.get("validation_status") != "verified":
                package_errors.append(f"{model} is not catalog-verified")
            if product.get("lifecycle_status") == "eol":
                package_errors.append(f"{model} lifecycle is eol")
            elif product.get("lifecycle_status") == "limited":
                package_warnings.append(
                    f"{model} lifecycle is {product.get('lifecycle_status')}"
                )
            package_errors.extend(_compatibility_warnings(normalized_models, product))
        if selected and not price_known:
            package_warnings.append("Catalog pricing is incomplete")
        if selected and not cost_known:
            package_warnings.append("Standard cost is incomplete")

        lead_times = [
            int(item["lead_time_days"])
            for item in selected
            if item.get("lead_time_days") is not None
        ]
        warranty_values = [
            int(item["warranty_months"])
            for item in selected
            if item.get("warranty_months") is not None
        ]
        currency = next(
            (str(item.get("currency")) for item in selected if item.get("currency")),
            "CNY",
        )
        commercial = {
            "currency": currency,
            "list_price": total_price,
            "standard_cost": total_cost,
            "gross_margin_percent": gross_margin,
            "lead_time_days": max(lead_times) if lead_times else None,
            "warranty_months": min(warranty_values) if warranty_values else None,
            "catalog_models": len(selected),
            "validation_errors": package_errors,
            "validation_warnings": package_warnings,
        }
        enriched_packages.append({**package, "commercial": commercial})
        workspace_errors.extend(package_errors)
        workspace_warnings.extend(package_warnings)

    extension = dict(workspace.get("extension_data") or {})
    extension["commercial_validation"] = {
        "valid": not workspace_errors,
        "errors": sorted(set(workspace_errors)),
        "warnings": sorted(set(workspace_warnings)),
    }
    return {
        **workspace,
        "packages": enriched_packages,
        "extension_data": extension,
    }


def extract_requirement_candidates(
    documents: list[dict[str, Any]], *, limit: int = 80
) -> list[dict[str, Any]]:
    """Produce traceable fallback requirements without an LLM dependency."""
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        extracted = document.get("extracted_data") or {}
        if isinstance(extracted, str):
            text = extracted
        elif isinstance(extracted, dict):
            text = str(
                extracted.get("full_text_context")
                or extracted.get("summary")
                or extracted.get("content")
                or ""
            )
        else:
            text = ""
        candidates = re.split(r"[\r\n]+|(?<=[。；;])", text)
        for candidate in candidates:
            title = re.sub(r"^[\s\-•*\d.、()（）]+", "", candidate).strip()
            if not 8 <= len(title) <= 240:
                continue
            normalized = re.sub(r"\s+", "", title).casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            priority = (
                "must"
                if re.search(r"必须|不得|应当|否决|强制|shall|must", title, re.I)
                else "should"
            )
            excerpt = title[:160]
            requirements.append(
                {
                    "id": f"req-doc-{len(requirements) + 1}",
                    "title": title,
                    "priority": priority,
                    "status": "open",
                    "evidence_ref": str(document.get("id") or ""),
                    "source_document_id": str(document.get("id") or ""),
                    "source_name": document.get("name"),
                    "source_excerpt": excerpt,
                }
            )
            if len(requirements) >= limit:
                return requirements
    return requirements


def solution_value_metrics(
    projects: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    deliveries: list[dict[str, Any]],
) -> dict[str, Any]:
    completed = [
        item for item in projects if item.get("status") in {"sent", "won", "lost"}
    ]
    won = [item for item in projects if item.get("status") == "won"]
    generated = [item for item in projects if int(item.get("current_version") or 0) > 0]
    readiness_values = [
        float(
            ((item.get("workspace") or {}).get("quality") or {}).get("completion") or 0
        )
        for item in projects
    ]
    usage = [
        ((item.get("workspace") or {}).get("generation") or {}).get("usage") or {}
        for item in projects
    ]
    tokens = sum(int(row.get("total_tokens") or row.get("total") or 0) for row in usage)
    costs = sum(float(row.get("cost_usd") or 0) for row in usage)
    accepted = sum(1 for item in feedback if item.get("change_type") == "accepted")
    edited = sum(1 for item in feedback if item.get("change_type") == "edited")
    decision_count = accepted + edited
    return {
        "projects": len(projects),
        "generated_projects": len(generated),
        "delivered_projects": len(completed),
        "won_projects": len(won),
        "win_rate": round(len(won) / len(completed) * 100, 1) if completed else 0,
        "average_readiness": (
            round(sum(readiness_values) / len(readiness_values), 1)
            if readiness_values
            else 0
        ),
        "feedback_events": len(feedback),
        "acceptance_rate": (
            round(accepted / decision_count * 100, 1) if decision_count else 0
        ),
        "delivery_events": len(deliveries),
        "total_tokens": tokens,
        "estimated_cost_usd": round(costs, 4),
    }
