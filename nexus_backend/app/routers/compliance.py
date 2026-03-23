"""Compliance and audit API endpoints (GDPR, DSAR, audit export)."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.audit_logger import audit_logger

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compliance", tags=["Compliance"])


@router.get("/audit/export")
async def export_audit_logs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    format: str = "json",  # noqa: A002
    days: int = 30,
):
    """Export audit logs in JSON or CSV format."""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "Organization context required")

        start_date = datetime.utcnow() - timedelta(days=days)
        logs = await audit_logger.query_logs(
            start_date=start_date,
            org_id=org_id,
            limit=10000,
        )

        if format == "csv":
            csv_content = _to_csv(logs)
            return PlainTextResponse(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=audit_logs_{days}d.csv"},
            )

        return api_success(
            data={
                "logs": logs,
                "count": len(logs),
                "period_days": days,
                "exported_at": datetime.utcnow().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Audit export failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合规检查操作失败")


@router.get("/dsar/{target_user_id}")
async def data_subject_access_request(
    target_user_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """GDPR Data Subject Access Request — get all data for a user."""
    try:
        client = getattr(req.state, "db", None)

        # P2 Security: DSAR only allowed for self or by admin of same org
        if target_user_id != user_id:
            if not client:
                raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "Database unavailable for permission check")
            requester = await client.table("users").select("role, org_id").eq("id", user_id).maybe_single().execute()
            target = await client.table("users").select("org_id").eq("id", target_user_id).maybe_single().execute()
            req_role = requester.data.get("role") if requester.data else None
            req_org = requester.data.get("org_id") if requester.data else None
            tgt_org = target.data.get("org_id") if target.data else None
            if req_role not in ("admin", "boss") or req_org != tgt_org:
                raise api_error(
                    ErrorCode.AUTH_PERMISSION_DENIED, "DSAR for other users requires admin role in same organization"
                )

        report = {"user_id": target_user_id, "export_date": datetime.utcnow().isoformat()}

        # Audit logs
        audit_logs = await audit_logger.query_logs(user_id=target_user_id, limit=10000)
        report["audit_logs"] = audit_logs
        report["audit_log_count"] = len(audit_logs)

        # User profile data
        if client:
            try:
                user_res = await client.table("users").select("*").eq("id", target_user_id).maybe_single().execute()
                report["profile"] = user_res.data if user_res.data else {}
            except Exception:
                report["profile"] = {}

            # Documents
            try:
                docs_res = (
                    await client.table("documents")
                    .select("id, name, created_at, updated_at")
                    .eq("owner_id", target_user_id)
                    .execute()
                )
                report["documents"] = docs_res.data or []
            except Exception:
                report["documents"] = []

        return api_success(data=report)
    except Exception as e:
        logger.error(f"DSAR failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "合规检查操作失败")


@router.get("/retention")
async def data_retention_policy(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get current data retention policy information."""
    return api_success(
        data={
            "policies": [
                {
                    "data_type": "audit_logs",
                    "retention_days": 365,
                    "description": "Audit logs are retained for 1 year",
                },
                {
                    "data_type": "chat_history",
                    "retention_days": 90,
                    "description": "Chat history is retained for 90 days",
                },
                {
                    "data_type": "documents",
                    "retention_days": None,
                    "description": "Documents are retained until manually deleted",
                },
                {
                    "data_type": "token_usage",
                    "retention_days": 180,
                    "description": "Usage data is retained for 6 months",
                },
            ],
            "gdpr_supported": True,
            "dsar_endpoint": "/api/compliance/dsar/{user_id}",
        }
    )


def _to_csv(logs: list) -> str:
    """Convert log entries to CSV format."""
    import csv
    import io

    if not logs:
        return ""

    output = io.StringIO()
    # Use keys from first log entry as headers
    if isinstance(logs[0], dict):
        fieldnames = list(logs[0].keys())
    else:
        return ""

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for log in logs:
        writer.writerow({k: str(v) for k, v in log.items()})

    return output.getvalue()
