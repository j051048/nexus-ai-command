"""Golden template library for artifact generation.

Templates are stored per tenant and keyed by artifact type x instrument line
x industry.  ``get_optimal_template`` performs the A/B pick: among active
templates matching the request, the one with the best measured quality
(avg score / ready rate / usage) wins.  ``record_template_usage`` updates
the template's measured metrics from real quality events.

The service never mutates a production writing skill; templates are a
separate, versioned, human-curated asset that the generation pipeline can
inject as a skeleton (``build_template_system_prompt``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _metric_score(template: dict[str, Any]) -> float:
    metrics = template.get("metrics") or {}
    avg_score = float(metrics.get("avg_score") or 0)
    ready_rate = float(metrics.get("ready_rate") or 0)
    usage = int(metrics.get("usage_count") or 0)
    return round(
        avg_score * 0.5 + ready_rate * 100 * 0.3 + min(usage, 20) / 20 * 100 * 0.2, 2
    )


def _profile_score(
    template: dict[str, Any],
    *,
    instrument_line: str | None,
    industry: str | None,
) -> float:
    """Prefer exact profiles while retaining tenant-wide fallback templates."""

    template_line = str(template.get("instrument_line") or "").strip()
    template_industry = str(template.get("industry") or "").strip()
    if template_line and template_line != str(instrument_line or "").strip():
        return -1.0
    if template_industry and template_industry != str(industry or "").strip():
        return -1.0
    specificity = 0.0
    if template_line and instrument_line:
        specificity += 12.0
    if template_industry and industry:
        specificity += 8.0
    return _metric_score(template) + specificity


async def list_templates(
    db: Any,
    *,
    organization_id: str,
    artifact_type: str | None = None,
    instrument_line: str | None = None,
    industry: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    try:
        query = (
            db.table("artifact_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("status", status)
        )
        if artifact_type:
            query = query.eq("artifact_type", artifact_type)
        if instrument_line:
            query = query.eq("instrument_line", instrument_line)
        if industry:
            query = query.eq("industry", industry)
        result = await query.order("created_at", desc=True).limit(100).execute()
        return {"ok": True, "templates": result.data or []}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] list failed: %s", exc)
        return {"ok": False, "error": str(exc), "templates": []}


async def get_optimal_template(
    db: Any,
    *,
    organization_id: str,
    artifact_type: str,
    instrument_line: str | None = None,
    industry: str | None = None,
) -> dict[str, Any] | None:
    """Pick the best active template (A/B) for a request profile."""
    try:
        query = (
            db.table("artifact_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("artifact_type", artifact_type)
            .eq("status", "active")
        )
        result = await query.limit(50).execute()
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] optimal lookup failed: %s", exc)
        return None

    candidates = [
        item
        for item in (result.data or [])
        if _profile_score(
            item,
            instrument_line=instrument_line,
            industry=industry,
        )
        >= 0
    ]
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda item: _profile_score(
            item,
            instrument_line=instrument_line,
            industry=industry,
        ),
    )
    return dict(best)


async def save_template(
    db: Any,
    *,
    organization_id: str,
    user_id: str,
    template_key: str,
    artifact_type: str,
    title: str,
    sections: list[str] | None = None,
    content_markdown: str = "",
    instrument_line: str | None = None,
    industry: str | None = None,
    version: str = "1.0.0",
    status: str = "active",
) -> dict[str, Any]:
    payload = {
        "organization_id": organization_id,
        "template_key": template_key,
        "artifact_type": artifact_type,
        "instrument_line": instrument_line,
        "industry": industry,
        "title": title,
        "sections": sections or [],
        "content_markdown": content_markdown,
        "version": version,
        "status": status,
        "created_by": user_id,
    }
    try:
        result = await db.table("artifact_templates").insert(payload).execute()
        return {"ok": True, "template": (result.data or [{}])[0]}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] save failed: %s", exc)
        return {"ok": False, "error": str(exc)}


async def record_template_usage(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    quality: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fold one quality event into the template's A/B metrics."""
    try:
        result = (
            await db.table("artifact_templates")
            .select("metrics")
            .eq("organization_id", organization_id)
            .eq("template_key", template_key)
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] usage metrics read failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    row = (result.data or [None])[0]
    if not row:
        return {"ok": False, "error": "template not found"}
    metrics = dict(row.get("metrics") or {})
    usage = int(metrics.get("usage_count") or 0) + 1
    avg_score = float(metrics.get("avg_score") or 0)
    ready_total = int(metrics.get("ready_total") or 0)
    score = float((quality or {}).get("score") or 0)
    ready = bool((quality or {}).get("ready"))
    new_avg = round((avg_score * (usage - 1) + score) / usage, 2) if usage else 0.0
    new_ready_rate = round((ready_total + int(ready)) / usage, 4) if usage else 0.0
    updated = {
        **metrics,
        "usage_count": usage,
        "avg_score": new_avg,
        "ready_rate": new_ready_rate,
        "ready_total": ready_total + int(ready),
    }
    try:
        await (
            db.table("artifact_templates")
            .update({"metrics": updated})
            .eq("organization_id", organization_id)
            .eq("template_key", template_key)
            .eq("status", "active")
            .execute()
        )
        return {"ok": True, "metrics": updated}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] usage metrics update failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def build_template_system_prompt(template: dict[str, Any] | None, spec: Any) -> str:
    """Return a generation-time skeleton prompt from the winning template."""
    if not template:
        return ""
    sections = list(template.get("sections") or [])
    title = str(template.get("title") or "")
    content = str(template.get("content_markdown") or "")
    lines = ["【黄金模板参考】", f"模板：{title}"]
    if sections:
        lines.append("建议章节骨架：" + " → ".join(sections))
    if content:
        lines.append("参考框架：" + content[:2000])
    lines.append("请基于企业资料与证据，按上述骨架产出定制内容，不要照抄模板文字。")
    return "\n".join(lines)
