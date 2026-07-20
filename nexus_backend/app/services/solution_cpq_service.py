"""Deterministic CPQ calculations for scientific-instrument solutions."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _catalog(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("model_code") or "").strip().casefold(): item
        for item in products
        if item.get("model_code")
    }


def _price_overrides(
    price_book_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in price_book_items:
        key = str(item.get("model_code") or item.get("product_id") or "").casefold()
        if key:
            result[key] = item
    return result


def build_package_quote(
    package: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    price_book_items: list[dict[str, Any]] | None = None,
    tax_rate: float = 0,
    default_discount_percent: float = 0,
) -> dict[str, Any]:
    """Build a quote without calling an LLM.

    A package may provide explicit ``line_items``. For backward compatibility,
    ``product_models`` are converted to quantity-one product lines.
    """

    product_lookup = _catalog(products)
    overrides = _price_overrides(price_book_items or [])
    raw_lines = package.get("line_items") or [
        {"model_code": model, "quantity": 1, "category": "instrument"}
        for model in package.get("product_models") or []
    ]
    lines: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    subtotal = Decimal("0")
    total_cost = Decimal("0")
    max_lead_time = 0
    warranty_months: int | None = None
    approval_reasons: list[str] = []

    for index, raw in enumerate(raw_lines):
        model_code = str(raw.get("model_code") or "").strip()
        product = product_lookup.get(model_code.casefold())
        if not product:
            errors.append(f"型号 {model_code or index + 1} 不在已核验产品目录中")
            continue
        if product.get("validation_status") != "verified":
            errors.append(f"型号 {model_code} 尚未通过产品目录审核")
        if product.get("lifecycle_status") in {"limited", "eol"}:
            warnings.append(
                f"型号 {model_code} 处于 {product.get('lifecycle_status')} 状态"
            )

        override = overrides.get(model_code.casefold()) or overrides.get(
            str(product.get("id") or "").casefold(), {}
        )
        quantity = max(1, int(raw.get("quantity") or 1))
        unit_price = _decimal(
            raw.get("unit_price_override"),
            str(override.get("unit_price") or product.get("list_price") or 0),
        )
        requested_discount = _decimal(
            raw.get("discount_percent"), str(default_discount_percent)
        )
        requested_discount = max(Decimal("0"), min(Decimal("100"), requested_discount))
        max_discount = _decimal(override.get("max_discount_percent"), "0")
        floor_price = _decimal(override.get("floor_price"), "0")
        cost = _decimal(product.get("standard_cost"), "0")
        net_unit_price = unit_price * (
            Decimal("1") - requested_discount / Decimal("100")
        )
        line_total = net_unit_price * quantity
        line_cost = cost * quantity
        subtotal += line_total
        total_cost += line_cost
        if requested_discount > max_discount:
            approval_reasons.append(
                f"{model_code} 折扣 {requested_discount}% 超过授权上限 {max_discount}%"
            )
        if floor_price > 0 and net_unit_price < floor_price:
            approval_reasons.append(f"{model_code} 净价低于区域价格底线")
        minimum_margin = override.get("minimum_margin_percent")
        line_margin = (
            (net_unit_price - cost) / net_unit_price * Decimal("100")
            if net_unit_price > 0 and cost > 0
            else None
        )
        if minimum_margin is not None and line_margin is not None:
            if line_margin < _decimal(minimum_margin):
                approval_reasons.append(f"{model_code} 毛利率低于审批底线")
        lead_time = int(product.get("lead_time_days") or 0)
        max_lead_time = max(max_lead_time, lead_time)
        product_warranty = product.get("warranty_months")
        if product_warranty is not None:
            warranty_months = (
                int(product_warranty)
                if warranty_months is None
                else min(warranty_months, int(product_warranty))
            )
        lines.append(
            {
                "model_code": model_code,
                "product_name": product.get("product_name"),
                "category": raw.get("category") or "instrument",
                "quantity": quantity,
                "currency": product.get("currency") or "CNY",
                "unit_price": _money(unit_price),
                "discount_percent": float(requested_discount),
                "net_unit_price": _money(net_unit_price),
                "line_total": _money(line_total),
                "lead_time_days": lead_time or None,
                "warranty_months": product_warranty,
            }
        )

    tax = subtotal * _decimal(tax_rate)
    total = subtotal + tax
    gross_margin = (
        (subtotal - total_cost) / subtotal * Decimal("100") if subtotal > 0 else None
    )
    currencies = {line["currency"] for line in lines}
    if len(currencies) > 1:
        errors.append("同一报价包含多种币种，请先统一价格册")
    return {
        "package_id": package.get("id"),
        "currency": next(iter(currencies), "CNY"),
        "line_items": lines,
        "subtotal": _money(subtotal),
        "tax_rate": float(_decimal(tax_rate)),
        "tax": _money(tax),
        "total": _money(total),
        "gross_margin_percent": (
            round(float(gross_margin), 2) if gross_margin is not None else None
        ),
        "lead_time_days": max_lead_time or None,
        "warranty_months": warranty_months,
        "approval_required": bool(approval_reasons),
        "approval_reasons": approval_reasons,
        "errors": errors,
        "warnings": warnings,
        "valid": not errors,
    }


def build_workspace_quotes(
    workspace: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    price_book_items: list[dict[str, Any]] | None = None,
    tax_rate: float = 0,
) -> dict[str, Any]:
    quotes = [
        build_package_quote(
            package,
            products,
            price_book_items=price_book_items,
            tax_rate=tax_rate,
        )
        for package in workspace.get("packages") or []
    ]
    return {
        "quotes": quotes,
        "valid": bool(quotes) and all(item["valid"] for item in quotes),
        "approval_required": any(item["approval_required"] for item in quotes),
    }
