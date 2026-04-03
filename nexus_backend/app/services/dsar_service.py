"""
GDPR DSAR (Data Subject Access Request) Service

Handles:
- Data export: Collect all user data across tables, package as JSON
- Data deletion: Anonymize/soft-delete personal data (Right to be Forgotten)
- Audit trail: Generate audit records for all DSAR operations

Covered tables:
- users, conversations, approval_requests, sales_leads,
  documents, audit_logs (retained but anonymized)
"""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Tables containing user personal data
_USER_DATA_TABLES = [
    "users",
    "conversations",
    "approval_requests",
    "sales_leads",
    "documents",
    "audit_logs",
]

# User ID column name per table (most use user_id)
_USER_ID_COLUMNS = {
    "users": "id",
    "conversations": "user_id",
    "approval_requests": "user_id",
    "sales_leads": "user_id",
    "documents": "user_id",
    "audit_logs": "user_id",
}

# Fields that constitute PII and must be anonymized on deletion
_PII_FIELDS = {
    "users": ["name", "email", "phone", "avatar_url", "display_name"],
    "conversations": ["title"],
    "approval_requests": ["details"],
    "sales_leads": ["contact_name", "contact_phone", "contact_email", "notes"],
    "documents": ["title", "content"],
    "audit_logs": [],  # audit_logs are retained but user reference is anonymized
}

# Placeholder for anonymized values
_ANON_PLACEHOLDER = "[GDPR_DELETED]"


class DSARService:
    """Service for processing GDPR Data Subject Access Requests."""

    def __init__(self, supabase_client):
        self.db = supabase_client

    async def export_user_data(self, user_id: str) -> dict[str, Any]:
        """
        Collect all user data across all relevant tables.

        Returns a dict with table names as keys and lists of records as values.
        This is the "data portability" aspect of GDPR Article 20.
        """
        request_id = str(uuid.uuid4())
        export_data: dict[str, Any] = {
            "request_id": request_id,
            "user_id": user_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "tables": {},
        }

        errors: list[str] = []

        # Parallel query across all 6 tables via asyncio.gather
        async def _fetch_table(table: str) -> tuple[str, dict]:
            uid_col = _USER_ID_COLUMNS.get(table, "user_id")
            try:
                resp = await self.db.table(table).select("*").eq(uid_col, user_id).limit(10000).execute()
                rows = resp.data if resp.data else []
                return table, {"count": len(rows), "records": rows}
            except Exception as e:
                logger.warning(f"DSAR export: failed to read table {table}: {e}")
                errors.append(f"{table}: {e}")
                return table, {"count": 0, "records": [], "error": str(e)}

        results = await asyncio.gather(
            *[_fetch_table(t) for t in _USER_DATA_TABLES],
            return_exceptions=False,
        )
        for table_name, table_data in results:
            export_data["tables"][table_name] = table_data

        export_data["errors"] = errors
        export_data["status"] = "completed" if not errors else "completed_with_errors"

        # Log the export action in audit_logs
        await self._log_audit(
            user_id=user_id,
            action="dsar_export",
            details={"request_id": request_id, "tables_exported": list(export_data["tables"].keys())},
        )

        return export_data

    async def delete_user_data(self, user_id: str) -> dict[str, Any]:
        """
        Anonymize/delete user data across all relevant tables.

        Strategy:
        - users: Anonymize PII fields, set status to 'deleted'
        - conversations: Soft-delete (anonymize title, keep structure for audit)
        - approval_requests: Anonymize details, keep for business record
        - sales_leads: Anonymize contact info
        - documents: Anonymize title/content
        - audit_logs: RETAINED but user_id reference anonymized (legal obligation)

        Returns a summary of actions taken.
        """
        request_id = str(uuid.uuid4())
        summary: dict[str, Any] = {
            "request_id": request_id,
            "user_id": user_id,
            "deleted_at": datetime.now(UTC).isoformat(),
            "actions": {},
        }

        errors: list[str] = []

        for table in _USER_DATA_TABLES:
            uid_col = _USER_ID_COLUMNS.get(table, "user_id")
            pii_fields = _PII_FIELDS.get(table, [])

            try:
                if table == "users":
                    # Special handling: anonymize PII + mark as deleted
                    update_data = {field: _ANON_PLACEHOLDER for field in pii_fields}
                    update_data["email"] = f"deleted_{request_id[:8]}@gdpr.invalid"
                    update_data["status"] = "deleted"
                    resp = await self.db.table(table).update(update_data).eq(uid_col, user_id).execute()
                    affected = len(resp.data) if resp.data else 0
                    summary["actions"][table] = {
                        "action": "anonymized",
                        "fields_cleared": pii_fields,
                        "records_affected": affected,
                    }

                elif table == "audit_logs":
                    # Audit logs are RETAINED (legal requirement) but user ref anonymized
                    resp = await (
                        self.db.table(table)
                        .update({"user_id": f"anon_{request_id[:8]}"})
                        .eq(uid_col, user_id)
                        .execute()
                    )
                    affected = len(resp.data) if resp.data else 0
                    summary["actions"][table] = {
                        "action": "user_reference_anonymized",
                        "records_affected": affected,
                        "note": "Audit logs retained per legal obligation, user reference anonymized",
                    }

                elif pii_fields:
                    # Anonymize PII fields in other tables
                    update_data = {field: _ANON_PLACEHOLDER for field in pii_fields}
                    resp = await self.db.table(table).update(update_data).eq(uid_col, user_id).execute()
                    affected = len(resp.data) if resp.data else 0
                    summary["actions"][table] = {
                        "action": "pii_anonymized",
                        "fields_cleared": pii_fields,
                        "records_affected": affected,
                    }

                else:
                    summary["actions"][table] = {
                        "action": "skipped",
                        "reason": "No PII fields defined",
                    }

            except Exception as e:
                logger.error(f"DSAR delete: failed on table {table}: {e}")
                errors.append(f"{table}: {e}")
                summary["actions"][table] = {"action": "failed", "error": str(e)}

        summary["errors"] = errors
        summary["status"] = "completed" if not errors else "completed_with_errors"

        # Log the deletion action
        await self._log_audit(
            user_id=f"anon_{request_id[:8]}",  # Already anonymized
            action="dsar_delete",
            details={
                "request_id": request_id,
                "original_user_id_hash": str(hash(user_id))[-8:],
                "tables_processed": list(summary["actions"].keys()),
            },
        )

        return summary

    async def _log_audit(self, user_id: str, action: str, details: dict[str, Any]) -> None:
        """Write a DSAR audit record."""
        try:
            await self.db.table("audit_logs").insert(
                {
                    "user_id": user_id,
                    "action": action,
                    "details": json.dumps(details, ensure_ascii=False),
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ).execute()
        except Exception as e:
            logger.error(f"Failed to write DSAR audit log: {e}")
