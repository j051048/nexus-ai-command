"""
P2 Optimization: Enhanced Audit Logging Service
Provides comprehensive audit trail for all critical operations.
"""

import os
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from fastapi import Request
from app.core.database import supabase


class AuditAction(Enum):
    """Predefined audit actions"""

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_PASSWORD_RESET = "auth.password_reset"

    # User Management
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ROLE_CHANGE = "user.role_change"

    # Approval Operations
    APPROVAL_SUBMIT = "approval.submit"
    APPROVAL_APPROVE = "approval.approve"
    APPROVAL_REJECT = "approval.reject"
    APPROVAL_ESCALATE = "approval.escalate"
    APPROVAL_AUTO = "approval.auto"

    # Document Operations
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_ACCESS = "document.access"
    DOCUMENT_SHARE = "document.share"

    # AI Operations
    AI_CHAT = "ai.chat"
    AI_TOOL_EXECUTE = "ai.tool_execute"
    AI_ANALYSIS = "ai.analysis"

    # Data Access
    DATA_EXPORT = "data.export"
    DATA_BULK_UPDATE = "data.bulk_update"
    DATA_SENSITIVE_ACCESS = "data.sensitive_access"

    # System Operations
    SYSTEM_CONFIG_CHANGE = "system.config_change"
    SYSTEM_ERROR = "system.error"
    SYSTEM_SECURITY_ALERT = "system.security_alert"


@dataclass
class AuditEntry:
    """Represents a single audit log entry"""

    action: str
    actor_user_id: Optional[str] = None
    target_id: Optional[str] = None
    target_table: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    org_id: Optional[str] = None
    status: str = "success"  # success, failed, warning
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "actor_user_id": self.actor_user_id,
            "org_id": self.org_id,
            "target_id": self.target_id,
            "target_table": self.target_table,
            "details_json": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "request_id": self.request_id,
            "status": self.status,
            "error_message": self.error_message,
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class AuditLogger:
    """
    Comprehensive audit logging service.
    Logs all critical operations with full context.
    """

    def __init__(self):
        self._buffer: List[AuditEntry] = []
        self._buffer_size = int(os.getenv("AUDIT_BUFFER_SIZE", "10"))
        self._enabled = os.getenv("AUDIT_LOGGING_ENABLED", "true").lower() == "true"

    async def log(
        self,
        action: str | AuditAction,
        actor_user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        target_id: Optional[str] = None,
        target_table: Optional[str] = None,
        details: Dict[str, Any] = None,
        request: Optional[Request] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        """
        Log an audit entry.

        Args:
            action: The action being logged (AuditAction enum or string)
            actor_user_id: ID of the user performing the action
            target_id: ID of the resource being acted upon
            target_table: Database table of the target resource
            details: Additional details about the action
            request: FastAPI Request object for extracting IP/User-Agent
            status: success, failed, or warning
            error_message: Error message if status is not success
        """
        if not self._enabled:
            return

        action_str = action.value if isinstance(action, AuditAction) else action

        entry = AuditEntry(
            action=action_str,
            actor_user_id=actor_user_id,
            org_id=org_id,
            target_id=target_id,
            target_table=target_table,
            details=self._sanitize_details(details or {}),
            status=status,
            error_message=error_message,
        )

        # Extract request info if available
        if request:
            entry.ip_address = self._get_client_ip(request)
            entry.user_agent = request.headers.get("user-agent", "")[:500]
            entry.request_id = request.headers.get("x-request-id")

        # Add to buffer
        self._buffer.append(entry)

        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            await self._flush()

    async def log_auth(
        self,
        action: AuditAction,
        user_id: str,
        success: bool,
        request: Request = None,
        details: Dict = None,
    ):
        """Convenience method for auth-related logging"""
        await self.log(
            action=action,
            actor_user_id=user_id,
            details=details,
            request=request,
            status="success" if success else "failed",
        )

    async def log_data_access(
        self,
        user_id: str,
        table: str,
        record_id: str,
        access_type: str = "read",
        request: Request = None,
    ):
        """Log data access for compliance"""
        await self.log(
            action=AuditAction.DATA_SENSITIVE_ACCESS,
            actor_user_id=user_id,
            target_id=record_id,
            target_table=table,
            details={"access_type": access_type},
            request=request,
        )

    async def log_approval_action(
        self,
        action: AuditAction,
        user_id: str,
        approval_id: str,
        amount: float = None,
        approval_type: str = None,
        reason: str = None,
        request: Request = None,
    ):
        """Log approval-related actions"""
        await self.log(
            action=action,
            actor_user_id=user_id,
            target_id=approval_id,
            target_table="approval_requests",
            details={"amount": amount, "type": approval_type, "reason": reason},
            request=request,
        )

    async def log_ai_operation(
        self,
        user_id: str,
        operation: str,
        model: str = None,
        tokens_used: int = None,
        tool_name: str = None,
        success: bool = True,
        error: str = None,
    ):
        """Log AI-related operations"""
        await self.log(
            action=AuditAction.AI_TOOL_EXECUTE if tool_name else AuditAction.AI_CHAT,
            actor_user_id=user_id,
            details={
                "operation": operation,
                "model": model,
                "tokens_used": tokens_used,
                "tool_name": tool_name,
            },
            status="success" if success else "failed",
            error_message=error,
        )

    async def _flush(self):
        """Flush buffered entries to database"""
        if not self._buffer or not supabase:
            return

        try:
            entries = [entry.to_dict() for entry in self._buffer]
            await supabase.table("audit_logs").insert(entries).execute()
            self._buffer.clear()
        except Exception as e:
            print(f"Audit log flush failed: {e}")
            # Keep last 100 entries in buffer if flush fails
            self._buffer = self._buffer[-100:]

    async def force_flush(self):
        """Force flush all buffered entries"""
        await self._flush()

    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP from request headers"""
        # Check for forwarded headers (common in proxied setups)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _sanitize_details(self, details: Dict) -> Dict:
        """
        Sanitize details to remove sensitive information.
        Never log passwords, tokens, or full credit card numbers.
        """
        sanitized = {}
        sensitive_keys = {
            "password",
            "passwd",
            "pwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "credit_card",
            "card_number",
            "cvv",
            "ssn",
        }

        for key, value in details.items():
            key_lower = key.lower()

            if any(sk in key_lower for sk in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, str) and len(value) > 1000:
                sanitized[key] = value[:1000] + "...[truncated]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value

        return sanitized

    async def query_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        target_table: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Query audit logs with filters"""
        if not supabase:
            return []

        try:
            query = supabase.table("audit_logs").select("*")

            if user_id:
                query = query.eq("actor_user_id", user_id)
            if action:
                query = query.eq("action", action)
            if target_table:
                query = query.eq("target_table", target_table)
            if start_date:
                query = query.gte("timestamp", start_date.isoformat())
            if end_date:
                query = query.lte("timestamp", end_date.isoformat())

            query = query.order("timestamp", desc=True).limit(limit)

            result = await query.execute()
            return result.data or []
        except Exception as e:
            print(f"Audit log query failed: {e}")
            return []


# Global audit logger instance
audit_logger = AuditLogger()


# Convenience function
async def audit(
    action: str | AuditAction,
    user_id: str = None,
    target_id: str = None,
    details: Dict = None,
    **kwargs,
):
    """Convenience function for logging audit entries"""
    await audit_logger.log(
        action=action,
        actor_user_id=user_id,
        target_id=target_id,
        details=details,
        **kwargs,
    )
